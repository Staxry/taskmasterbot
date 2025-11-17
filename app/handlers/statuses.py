"""
Status handlers module
Обработчики изменения статусов задач
"""
from aiogram import F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.handlers import statuses_router
from app.database import get_db_connection
from app.services.users import get_or_create_user
from app.keyboards.task_keyboards import get_task_keyboard
from app.keyboards.main_menu import get_main_keyboard
from app.states import CompleteTaskStates
from app.logging_config import get_logger
from app.services.notifications import get_all_admins

logger = get_logger(__name__)


@statuses_router.callback_query(F.data.startswith("status_"))
async def callback_update_status(callback: CallbackQuery, state: FSMContext):
    """Обновить статус задачи"""
    parts = callback.data.split('_')
    task_id = int(parts[1])
    new_status = '_'.join(parts[2:])
    
    logger.info(f"🔍 Parsing callback_data: {callback.data} -> parts: {parts} -> task_id: {task_id}, new_status: {new_status}")
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"🔄 Update status for task #{task_id} to {new_status} by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """SELECT t.id, t.title, t.assigned_to_id, t.priority, t.due_date 
               FROM tasks t 
               WHERE t.id = ?""",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            logger.warning(f"⚠️ Task #{task_id} not found")
            await callback.answer("❌ Задача не найдена.", show_alert=True)
            return
        
        old_assigned_to_id = task['assigned_to_id']
        
        if task['assigned_to_id'] != user['id'] and user['role'] != 'admin':
            logger.warning(f"⛔ User {username} tried to update task #{task_id} without permissions")
            await callback.answer("❌ Вы можете обновлять только свои задачи.", show_alert=True)
            return
        
        if new_status in ['completed', 'partially_completed']:
            logger.debug(f"📝 Requesting completion comment for task #{task_id}")
            
            await state.update_data(task_id=task_id, new_status=new_status)
            await state.set_state(CompleteTaskStates.waiting_for_comment)
            
            cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
                [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
            ])
            
            if new_status == 'completed':
                prompt_text = (
                    "✅ <b>Завершение задачи</b>\n\n"
                    "Напишите <b>комментарий</b> о выполненной работе:\n\n"
                    "Например: 'Отчёт подготовлен и отправлен руководству'"
                )
            else:
                prompt_text = (
                    "🔶 <b>Частичное завершение задачи</b>\n\n"
                    "Напишите <b>комментарий</b>:\n"
                    "• Что уже сделано\n"
                    "• Что осталось доделать\n\n"
                    "Например: 'Выполнено 70%. Осталось проверить данные и оформить выводы.'"
                )
            
            try:
                await callback.message.edit_text(
                    prompt_text,
                    parse_mode='HTML',
                    reply_markup=cancel_keyboard
                )
            except Exception:
                await callback.message.delete()
                await callback.message.answer(
                    prompt_text,
                    parse_mode='HTML',
                    reply_markup=cancel_keyboard
                )
            await callback.answer()
            return
        
        logger.debug(f"💾 Updating task #{task_id} status to {new_status}")
        
        if new_status == 'in_progress' and old_assigned_to_id is None:
            logger.info(f"📌 Assigning unassigned task #{task_id} to {username}")
            cur.execute(
                "UPDATE tasks SET status = ?, assigned_to_id = ?, updated_at = datetime('now') WHERE id = ?",
                (new_status, user['id'], task_id)
            )
        else:
            cur.execute(
                "UPDATE tasks SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (new_status, task_id)
            )
        conn.commit()
        
        status_text = {
            'pending': '⏳ Ожидает',
            'in_progress': '🔄 В работе',
            'rejected': '❌ Отклонена'
        }.get(new_status, new_status)
        
        logger.info(f"✅ Task #{task_id} status updated to {new_status}")
        
        if new_status == 'in_progress' and old_assigned_to_id is None:
            logger.info(f"📧 Sending admin notifications for task #{task_id} taken by {username}")
            
            priority_emoji = {
                'urgent': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '🟢'
            }.get(task['priority'], '⚪')
            
            # Форматируем имя исполнителя
            if first_name or last_name:
                executor_display = f"{first_name or ''} {last_name or ''}".strip() + f" (@{username})"
            else:
                executor_display = f"@{username}"
            
            admin_message = (
                f"🔔 <b>Задача взята в работу</b>\n\n"
                f"{priority_emoji} <b>#{task_id}:</b> {task['title']}\n\n"
                f"👤 <b>Исполнитель:</b> {executor_display}\n"
                f"📅 <b>Срок:</b> {task['due_date']}\n\n"
                f"Задача была свободной и взята в работу пользователем."
            )
            
            admins = get_all_admins()
            from app.main import bot
            
            for admin_telegram_id in admins:
                if admin_telegram_id != telegram_id:
                    try:
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="📂 Открыть задачу", callback_data=f"task_{task_id}")]
                        ])
                        
                        await bot.send_message(
                            chat_id=admin_telegram_id,
                            text=admin_message,
                            parse_mode='HTML',
                            reply_markup=keyboard
                        )
                        logger.info(f"✅ Admin notification sent to {admin_telegram_id} for task #{task_id}")
                    except Exception as e:
                        logger.error(f"❌ Failed to send admin notification to {admin_telegram_id}: {e}")
        
        await callback.answer(f"✅ Статус обновлён на: {status_text}", show_alert=True)
        
        cur.execute(
            """SELECT t.id, t.title, t.description, t.status, t.priority, t.due_date, 
                      u.username, u.first_name, u.last_name, t.created_at, t.assigned_to_id, t.completion_comment, t.photo_file_id
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               WHERE t.id = ?""",
            (task_id,)
        )
        updated_task = cur.fetchone()
        
        if updated_task:
            tid = updated_task['id']
            title = updated_task['title']
            description = updated_task['description']
            status = updated_task['status']
            priority = updated_task['priority']
            due_date_raw = updated_task['due_date']
            assigned_username = updated_task.get('username')
            assigned_first_name = updated_task.get('first_name')
            assigned_last_name = updated_task.get('last_name')
            created_at = updated_task['created_at']
            assigned_to_id = updated_task['assigned_to_id']
            completion_comment = updated_task.get('completion_comment')
            photo_file_id = updated_task.get('photo_file_id')
            
            from app.config import format_datetime_for_display
            due_date = format_datetime_for_display(due_date_raw)
            created_at_formatted = format_datetime_for_display(created_at)
            
            if assigned_username:
                if assigned_first_name or assigned_last_name:
                    assignee_display = f"{assigned_first_name or ''} {assigned_last_name or ''}".strip() + f" (@{assigned_username})"
                else:
                    assignee_display = f"@{assigned_username}"
            else:
                assignee_display = "Не назначена"
            
            status_display = {
                'pending': '⏳ Ожидает',
                'in_progress': '🔄 В работе',
                'partially_completed': '🔶 Частично завершена',
                'completed': '✅ Завершена',
                'rejected': '❌ Отклонена'
            }.get(status, status)
            
            priority_display = {
                'urgent': '🔴 Срочно',
                'high': '🟠 Высокий',
                'medium': '🟡 Средний',
                'low': '🟢 Низкий'
            }.get(priority, priority)
            
            text = f"""📋 <b>Задача #{tid}</b>

<b>Название:</b> {title}
<b>Описание:</b> {description or 'Нет описания'}
<b>Статус:</b> {status_display}
<b>Приоритет:</b> {priority_display}
<b>Срок:</b> {due_date}
<b>Назначена:</b> {assignee_display}
<b>Создана:</b> {created_at_formatted}
"""
            
            if status in ['completed', 'partially_completed'] and completion_comment:
                text += f"\n💬 <b>Комментарий:</b>\n{completion_comment}\n"
            
            if status not in ['completed', 'partially_completed']:
                text += "\nВыберите новый статус:"
            
            try:
                await callback.message.edit_text(
                    text,
                    parse_mode='HTML',
                    reply_markup=get_task_keyboard(task_id, status, assigned_to_id, user['id'], user['role'] == 'admin')
                )
            except Exception:
                await callback.message.delete()
                await callback.message.answer(
                    text,
                    parse_mode='HTML',
                    reply_markup=get_task_keyboard(task_id, status, assigned_to_id, user['id'], user['role'] == 'admin')
                )
    
    except Exception as e:
        logger.error(f"❌ Error updating status for task #{task_id}: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка при обновлении статуса: {str(e)}", show_alert=True)
    finally:
        cur.close()
        conn.close()


@statuses_router.callback_query(F.data.startswith("reopen_"))
async def callback_reopen_task(callback: CallbackQuery):
    """Вернуть завершенную задачу в работу (только для админов)"""
    task_id = int(callback.data.split('_')[1])
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"🔄 Reopen task #{task_id} requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to reopen task without admin rights")
        await callback.answer("❌ Только админы могут возвращать задачи в работу", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT status FROM tasks WHERE id = ?",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            logger.warning(f"⚠️ Task #{task_id} not found")
            await callback.answer("❌ Задача не найдена.", show_alert=True)
            return
        
        current_status = task['status']
        
        if current_status not in ['completed', 'partially_completed']:
            logger.warning(f"⚠️ Task #{task_id} is not completed (status: {current_status})")
            await callback.answer("❌ Эта задача не завершена.", show_alert=True)
            return
        
        logger.debug(f"🔄 Reopening task #{task_id}, clearing completion data")
        
        # Получаем данные задачи перед обновлением для уведомления
        cur.execute(
            """SELECT t.id, t.title, t.description, t.priority, t.due_date, t.assigned_to_id,
                      u.telegram_id as assignee_telegram_id, u.username as assignee_username,
                      u.first_name as assignee_first_name, u.last_name as assignee_last_name
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               WHERE t.id = ?""",
            (task_id,)
        )
        task_data = cur.fetchone()
        
        cur.execute(
            """UPDATE tasks 
               SET status = 'in_progress', 
                   completion_comment = NULL, 
                   photo_file_id = NULL, 
                   updated_at = datetime('now') 
               WHERE id = ?""",
            (task_id,)
        )
        conn.commit()
        
        logger.info(f"✅ Admin {username} reopened task #{task_id}")
        
        # Отправляем уведомление исполнителю о возврате задачи
        if task_data and task_data['assigned_to_id'] and task_data['assignee_telegram_id']:
            logger.info(f"📧 Sending notification to assignee about task #{task_id} reopening")
            
            priority_emoji = {
                'urgent': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '🟢'
            }.get(task_data['priority'], '⚪')
            
            # Форматируем имя админа
            if first_name or last_name:
                admin_display = f"{first_name or ''} {last_name or ''}".strip() + f" (@{username})"
            else:
                admin_display = f"@{username}"
            
            assignee_message = (
                f"🔄 <b>Задача возвращена в работу</b>\n\n"
                f"{priority_emoji} <b>#{task_data['id']}:</b> {task_data['title']}\n\n"
                f"👤 <b>Возвращена админом:</b> {admin_display}\n"
                f"📅 <b>Срок:</b> {task_data['due_date']}\n\n"
                f"⚠️ Задача требует повторного выполнения.\n"
                f"Пожалуйста, завершите её снова с учётом замечаний."
            )
            
            from app.main import bot
            
            try:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📂 Открыть задачу", callback_data=f"task_{task_id}")]
                ])
                
                await bot.send_message(
                    chat_id=task_data['assignee_telegram_id'],
                    text=assignee_message,
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
                logger.info(f"✅ Notification sent to {task_data['assignee_username']} about task #{task_id} reopening")
            except Exception as e:
                logger.error(f"❌ Failed to send notification to assignee: {e}")
        
        await callback.answer("✅ Задача возвращена в работу", show_alert=True)
        
        cur.execute(
            """SELECT t.id, t.title, t.description, t.status, t.priority, t.due_date, 
                      u.username, u.first_name, u.last_name, t.created_at, t.assigned_to_id
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               WHERE t.id = ?""",
            (task_id,)
        )
        updated_task = cur.fetchone()
        
        if updated_task:
            tid = updated_task['id']
            title = updated_task['title']
            description = updated_task['description']
            status = updated_task['status']
            priority = updated_task['priority']
            due_date = updated_task['due_date']
            assigned_username = updated_task.get('username')
            assigned_first_name = updated_task.get('first_name')
            assigned_last_name = updated_task.get('last_name')
            created_at = updated_task['created_at']
            assigned_to_id = updated_task['assigned_to_id']
            
            # Форматируем имя назначенного пользователя
            if assigned_username:
                if assigned_first_name or assigned_last_name:
                    assignee_display = f"{assigned_first_name or ''} {assigned_last_name or ''}".strip() + f" (@{assigned_username})"
                else:
                    assignee_display = f"@{assigned_username}"
            else:
                assignee_display = "🆓 Свободна (можно взять)"
            
            status_text = {
                'pending': '⏳ Ожидает',
                'in_progress': '🔄 В работе',
                'partially_completed': '🔶 Частично завершена',
                'completed': '✅ Завершена',
                'rejected': '❌ Отклонена'
            }.get(status, status)
            
            priority_text = {
                'urgent': '🔴 Срочно',
                'high': '🟠 Высокий',
                'medium': '🟡 Средний',
                'low': '🟢 Низкий'
            }.get(priority, priority)
            
            text = f"""📋 <b>Задача #{tid}</b>

<b>Название:</b> {title}
<b>Описание:</b> {description or 'Нет описания'}
<b>Статус:</b> {status_text}
<b>Приоритет:</b> {priority_text}
<b>Срок:</b> {due_date}
<b>Назначена:</b> {assignee_display}
<b>Создана:</b> {created_at}

Выберите новый статус:"""
            
            try:
                await callback.message.edit_text(
                    text,
                    parse_mode='HTML',
                    reply_markup=get_task_keyboard(task_id, status, assigned_to_id, user['id'], user['role'] == 'admin')
                )
            except Exception:
                logger.debug(f"⚠️ Could not edit message, deleting and resending")
                await callback.message.delete()
                await callback.message.answer(
                    text,
                    parse_mode='HTML',
                    reply_markup=get_task_keyboard(task_id, status, assigned_to_id, user['id'], user['role'] == 'admin')
                )
    
    except Exception as e:
        logger.error(f"❌ Error reopening task #{task_id}: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
    finally:
        cur.close()
        conn.close()


@statuses_router.message(CompleteTaskStates.waiting_for_comment)
async def process_completion_comment(message: Message, state: FSMContext):
    """Обработать комментарий о завершении задачи"""
    comment = message.text
    
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    last_name = message.from_user.last_name or ''
    
    logger.info(f"📝 Completion comment received from {username}: {comment[:50]}...")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        logger.error(f"❌ User {username} lost authorization during completion flow")
        await message.answer("❌ Доступ запрещён")
        await state.clear()
        return
    
    await state.update_data(comment=comment)
    await state.set_state(CompleteTaskStates.asking_for_photo)
    
    photo_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, добавить фото", callback_data="photo_yes"),
            InlineKeyboardButton(text="❌ Нет, без фото", callback_data="photo_no")
        ]
    ])
    
    logger.debug(f"📸 Asking for completion photo for task")
    
    await message.answer(
        "📸 <b>Добавить фото к отчёту?</b>\n\n"
        "Фото поможет лучше продемонстрировать результат работы.",
        parse_mode='HTML',
        reply_markup=photo_keyboard
    )
