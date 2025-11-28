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
from app.states import CompleteTaskStates, ChangeAssigneeStates, ReopenTaskStates
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
                      u.username, u.first_name, u.last_name, t.created_at, t.assigned_to_id, 
                      t.completion_comment, t.photo_file_id, t.task_photo_file_id
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
            task_photo_file_id = updated_task.get('task_photo_file_id')
            
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
            
            if task_photo_file_id:
                text += "<b>📸 Фото:</b> Есть (нажмите кнопку ниже)\n"
            
            if status in ['completed', 'partially_completed'] and completion_comment:
                text += f"\n💬 <b>Комментарий:</b>\n{completion_comment}\n"
            
            if status not in ['completed', 'partially_completed']:
                text += "\nВыберите новый статус:"
            
            has_task_photo = bool(task_photo_file_id)
            
            try:
                await callback.message.edit_text(
                    text,
                    parse_mode='HTML',
                    reply_markup=get_task_keyboard(task_id, status, assigned_to_id, user['id'], user['role'] == 'admin', has_task_photo)
                )
            except Exception:
                await callback.message.delete()
                await callback.message.answer(
                    text,
                    parse_mode='HTML',
                    reply_markup=get_task_keyboard(task_id, status, assigned_to_id, user['id'], user['role'] == 'admin', has_task_photo)
                )
    
    except Exception as e:
        logger.error(f"❌ Error updating status for task #{task_id}: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка при обновлении статуса: {str(e)}", show_alert=True)
    finally:
        cur.close()
        conn.close()


@statuses_router.callback_query(F.data.startswith("reopen_"))
async def callback_reopen_task(callback: CallbackQuery, state: FSMContext):
    """Начать процесс возврата задачи с комментарием (только для админов)"""
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
            "SELECT status, title FROM tasks WHERE id = ?",
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
        
        # Сохраняем task_id в состояние и запрашиваем комментарий
        await state.update_data(task_id=task_id)
        await state.set_state(ReopenTaskStates.waiting_for_comment)
        
        cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ])
        
        message_text = (
            f"💬 <b>Возврат задачи #{task_id}</b>\n\n"
            f"<b>Задача:</b> {task['title']}\n\n"
            f"📝 Напишите комментарий для исполнителя:\n"
            f"Опишите, что нужно доделать или скорректировать."
        )
        
        # Пытаемся редактировать сообщение, если не получается - отправляем новое
        try:
            await callback.message.edit_text(
                message_text,
                parse_mode='HTML',
                reply_markup=cancel_keyboard
            )
        except Exception:
            logger.debug("⚠️ Could not edit message, sending new one")
            await callback.message.delete()
            await callback.message.answer(
                message_text,
                parse_mode='HTML',
                reply_markup=cancel_keyboard
            )
        
        await callback.answer()
        logger.debug(f"🔄 Requesting reopen comment for task #{task_id}")
    
    except Exception as e:
        logger.error(f"❌ Error starting reopen process: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
    finally:
        cur.close()
        conn.close()


@statuses_router.message(ReopenTaskStates.waiting_for_comment)
async def process_reopen_comment(message: Message, state: FSMContext):
    """Обработать комментарий админа при возврате задачи"""
    comment = message.text
    
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    last_name = message.from_user.last_name or ''
    
    logger.info(f"💬 Reopen comment received from {username}: {comment[:50]}...")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        logger.error(f"❌ User {username} lost authorization during reopen flow")
        await message.answer("❌ Доступ запрещён")
        await state.clear()
        return
    
    if user['role'] != 'admin':
        await message.answer("❌ Только админы могут возвращать задачи")
        await state.clear()
        return
    
    data = await state.get_data()
    task_id = data.get('task_id')
    
    if not task_id:
        await message.answer("❌ Ошибка: задача не найдена")
        await state.clear()
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Получаем данные задачи
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
        
        if not task_data:
            logger.warning(f"⚠️ Task #{task_id} not found")
            await message.answer("❌ Задача не найдена")
            await state.clear()
            return
        
        # Возвращаем задачу в работу
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
        
        logger.info(f"✅ Admin {username} reopened task #{task_id} with comment")
        
        # Форматируем имя админа
        if first_name or last_name:
            admin_display = f"{first_name or ''} {last_name or ''}".strip() + f" (@{username})"
        else:
            admin_display = f"@{username}"
        
        # Отправляем уведомление исполнителю с комментарием админа
        if task_data['assigned_to_id'] and task_data['assignee_telegram_id']:
            logger.info(f"📧 Sending reopening notification with comment to {task_data['assignee_username']}")
            
            priority_emoji = {
                'urgent': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '🟢'
            }.get(task_data['priority'], '⚪')
            
            priority_text = {
                'urgent': '🔴 Срочно',
                'high': '🟠 Высокий',
                'medium': '🟡 Средний',
                'low': '🟢 Низкий'
            }.get(task_data['priority'], task_data['priority'])
            
            assignee_message = f"""🔄 <b>Задача возвращена в работу</b>

{priority_emoji} <b>#{task_data['id']}:</b> {task_data['title']}
<b>Приоритет:</b> {priority_text}
📅 <b>Срок:</b> {task_data['due_date']}

👤 <b>Возвращена админом:</b> {admin_display}

💬 <b>Комментарий администратора:</b>
{comment}

⚠️ Пожалуйста, учтите замечания и завершите задачу снова."""
            
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
        
        # Подтверждение админу
        await message.answer(
            f"✅ <b>Задача #{task_id} возвращена в работу!</b>\n\n"
            f"Исполнитель получил уведомление с вашим комментарием.",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user['role'])
        )
        
        await state.clear()
        logger.debug(f"✅ Task #{task_id} reopening completed")
    
    except Exception as e:
        logger.error(f"❌ Error reopening task #{task_id}: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка при возврате задачи: {str(e)}")
        await state.clear()
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


@statuses_router.callback_query(F.data.startswith("change_assignee_"))
async def callback_change_assignee(callback: CallbackQuery, state: FSMContext):
    """Начать процесс смены исполнителя (только для админов)"""
    task_id = int(callback.data.split('_')[2])
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"👤 Change assignee for task #{task_id} requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to change assignee without admin rights")
        await callback.answer("❌ Только админы могут менять исполнителей", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Получаем всех пользователей (админов и сотрудников)
        cur.execute(
            """SELECT id, username, first_name, last_name, role 
               FROM users 
               WHERE role IN ('admin', 'employee')
               ORDER BY role DESC, username"""
        )
        users = cur.fetchall()
        
        if not users:
            logger.warning("⚠️ No users found in system")
            await callback.answer("❌ В системе нет пользователей", show_alert=True)
            return
        
        # Сохраняем task_id в состояние
        await state.update_data(task_id=task_id)
        await state.set_state(ChangeAssigneeStates.waiting_for_selection)
        
        # Формируем клавиатуру с пользователями
        buttons = []
        for user_data in users:
            user_id = user_data['id']
            user_username = user_data['username']
            user_first_name = user_data['first_name']
            user_last_name = user_data['last_name']
            user_role = user_data['role']
            
            # Форматируем имя пользователя
            if user_first_name or user_last_name:
                display_name = f"{user_first_name or ''} {user_last_name or ''}".strip()
                full_display = f"{display_name} (@{user_username})"
            else:
                full_display = f"@{user_username}"
            
            # Добавляем иконку роли
            role_icon = "👨‍💼" if user_role == 'admin' else "👤"
            button_text = f"{role_icon} {full_display}"
            
            buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"select_assignee_{task_id}_{user_id}"
            )])
        
        # Добавляем опцию "Без исполнителя"
        buttons.append([InlineKeyboardButton(
            text="🆓 Без исполнителя (свободная задача)",
            callback_data=f"select_assignee_{task_id}_none"
        )])
        
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(
            f"👤 <b>Выберите нового исполнителя для задачи #{task_id}:</b>",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        await callback.answer()
        
        logger.debug(f"📋 Showing {len(users)} users for assignee selection")
    
    except Exception as e:
        logger.error(f"❌ Error showing assignee list: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
    finally:
        cur.close()
        conn.close()


@statuses_router.callback_query(F.data.startswith("select_assignee_"))
async def callback_select_assignee(callback: CallbackQuery, state: FSMContext):
    """Назначить нового исполнителя задачи"""
    parts = callback.data.split('_')
    task_id = int(parts[2])
    new_assignee = parts[3]  # user_id или 'none'
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"👤 Assigning task #{task_id} to {new_assignee} by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        await state.clear()
        return
    
    if user['role'] != 'admin':
        await callback.answer("❌ Только админы могут менять исполнителей", show_alert=True)
        await state.clear()
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Получаем текущую информацию о задаче
        cur.execute(
            """SELECT t.id, t.title, t.description, t.priority, t.due_date, t.assigned_to_id,
                      old_user.telegram_id as old_assignee_telegram_id, 
                      old_user.username as old_assignee_username,
                      old_user.first_name as old_assignee_first_name,
                      old_user.last_name as old_assignee_last_name
               FROM tasks t
               LEFT JOIN users old_user ON t.assigned_to_id = old_user.id
               WHERE t.id = ?""",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            logger.warning(f"⚠️ Task #{task_id} not found")
            await callback.answer("❌ Задача не найдена", show_alert=True)
            await state.clear()
            return
        
        old_assignee_id = task['assigned_to_id']
        old_assignee_telegram_id = task.get('old_assignee_telegram_id')
        old_assignee_username = task.get('old_assignee_username')
        old_assignee_first_name = task.get('old_assignee_first_name')
        old_assignee_last_name = task.get('old_assignee_last_name')
        
        # Определяем нового исполнителя
        if new_assignee == 'none':
            new_assignee_id = None
            new_assignee_telegram_id = None
            new_assignee_username = None
            new_assignee_display = "🆓 Без исполнителя"
        else:
            new_assignee_id = int(new_assignee)
            
            # Если старый == новый, ничего не меняем
            if old_assignee_id == new_assignee_id:
                await callback.answer("⚠️ Это уже текущий исполнитель", show_alert=True)
                await state.clear()
                return
            
            # Получаем данные нового исполнителя
            cur.execute(
                "SELECT telegram_id, username, first_name, last_name FROM users WHERE id = ?",
                (new_assignee_id,)
            )
            new_user = cur.fetchone()
            
            if not new_user:
                logger.warning(f"⚠️ New assignee user #{new_assignee_id} not found")
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                await state.clear()
                return
            
            new_assignee_telegram_id = new_user['telegram_id']
            new_assignee_username = new_user['username']
            new_assignee_first_name = new_user['first_name']
            new_assignee_last_name = new_user['last_name']
            
            # Форматируем имя нового исполнителя
            if new_assignee_first_name or new_assignee_last_name:
                new_assignee_display = f"{new_assignee_first_name or ''} {new_assignee_last_name or ''}".strip() + f" (@{new_assignee_username})"
            else:
                new_assignee_display = f"@{new_assignee_username}"
        
        # Обновляем исполнителя в БД
        cur.execute(
            "UPDATE tasks SET assigned_to_id = ?, updated_at = datetime('now') WHERE id = ?",
            (new_assignee_id, task_id)
        )
        conn.commit()
        
        logger.info(f"✅ Task #{task_id} reassigned: {old_assignee_id} -> {new_assignee_id}")
        
        # Форматируем имя админа
        if first_name or last_name:
            admin_display = f"{first_name or ''} {last_name or ''}".strip() + f" (@{username})"
        else:
            admin_display = f"@{username}"
        
        # Уведомление старому исполнителю (если был)
        if old_assignee_telegram_id:
            try:
                # Форматируем имя старого исполнителя
                if old_assignee_first_name or old_assignee_last_name:
                    old_display = f"{old_assignee_first_name or ''} {old_assignee_last_name or ''}".strip() + f" (@{old_assignee_username})"
                else:
                    old_display = f"@{old_assignee_username}"
                
                priority_text = {
                    'urgent': '🔴 Срочно',
                    'high': '🟠 Высокий',
                    'medium': '🟡 Средний',
                    'low': '🟢 Низкий'
                }.get(task['priority'], task['priority'])
                
                old_notification = f"""ℹ️ <b>Задача переназначена</b>

<b>Задача #{task_id}:</b> {task['title']}
<b>Приоритет:</b> {priority_text}

Вы были сняты с этой задачи.
<b>Админ:</b> {admin_display}
<b>Новый исполнитель:</b> {new_assignee_display}"""
                
                await callback.message.bot.send_message(
                    chat_id=old_assignee_telegram_id,
                    text=old_notification,
                    parse_mode='HTML'
                )
                logger.debug(f"📨 Sent unassignment notification to {old_assignee_username}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to notify old assignee: {e}")
        
        # Уведомление новому исполнителю (если есть)
        if new_assignee_telegram_id:
            try:
                priority_text = {
                    'urgent': '🔴 Срочно',
                    'high': '🟠 Высокий',
                    'medium': '🟡 Средний',
                    'low': '🟢 Низкий'
                }.get(task['priority'], task['priority'])
                
                new_notification = f"""👤 <b>Вам назначена задача!</b>

<b>Задача #{task_id}:</b> {task['title']}
<b>Описание:</b> {task['description'] or 'Нет описания'}
<b>Приоритет:</b> {priority_text}
<b>Срок:</b> 📅 {task['due_date']}
<b>Назначил:</b> {admin_display}

Используйте /start для просмотра задачи."""
                
                task_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📂 Открыть задачу", callback_data=f"task_{task_id}")]
                ])
                
                await callback.message.bot.send_message(
                    chat_id=new_assignee_telegram_id,
                    text=new_notification,
                    parse_mode='HTML',
                    reply_markup=task_keyboard
                )
                logger.debug(f"📨 Sent assignment notification to {new_assignee_username}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to notify new assignee: {e}")
        
        # Подтверждение админу
        await callback.message.edit_text(
            f"✅ <b>Исполнитель изменён!</b>\n\n"
            f"Задача #{task_id}\n"
            f"Новый исполнитель: {new_assignee_display}",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user['role'])
        )
        await callback.answer()
        await state.clear()
    
    except Exception as e:
        logger.error(f"❌ Error changing assignee: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
        await state.clear()
    finally:
        cur.close()
        conn.close()
