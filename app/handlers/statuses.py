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
    
    logger.info(f"🔄 Update status for task #{task_id} to {new_status} by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT assigned_to_id FROM tasks WHERE id = %s",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            logger.warning(f"⚠️ Task #{task_id} not found")
            await callback.answer("❌ Задача не найдена.", show_alert=True)
            return
        
        if task[0] != user['id'] and user['role'] != 'admin':
            logger.warning(f"⛔ User {username} tried to update task #{task_id} without permissions")
            await callback.answer("❌ Вы можете обновлять только свои задачи.", show_alert=True)
            return
        
        if new_status in ['completed', 'partially_completed']:
            logger.debug(f"📝 Requesting completion comment for task #{task_id}")
            
            await state.update_data(task_id=task_id, new_status=new_status)
            await state.set_state(CompleteTaskStates.waiting_for_comment)
            
            cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
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
            
            await callback.message.edit_text(
                prompt_text,
                parse_mode='HTML',
                reply_markup=cancel_keyboard
            )
            await callback.answer()
            return
        
        logger.debug(f"💾 Updating task #{task_id} status to {new_status}")
        
        cur.execute(
            "UPDATE tasks SET status = %s, updated_at = NOW() WHERE id = %s",
            (new_status, task_id)
        )
        conn.commit()
        
        status_text = {
            'pending': '⏳ Ожидает',
            'in_progress': '🔄 В работе',
            'rejected': '❌ Отклонена'
        }.get(new_status, new_status)
        
        logger.info(f"✅ Task #{task_id} status updated to {new_status}")
        
        await callback.answer(f"✅ Статус обновлён на: {status_text}", show_alert=True)
        
        cur.execute(
            """SELECT t.id, t.title, t.description, t.status, t.priority, t.due_date, 
                      u.username, t.created_at, t.assigned_to_id, t.completion_comment, t.photo_file_id
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               WHERE t.id = %s""",
            (task_id,)
        )
        updated_task = cur.fetchone()
        
        if updated_task:
            tid, title, description, status, priority, due_date, assigned_username, created_at, assigned_to_id, completion_comment, photo_file_id = updated_task
            
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
<b>Назначена:</b> @{assigned_username or 'Не назначена'}
<b>Создана:</b> {created_at.strftime('%Y-%m-%d %H:%M')}
"""
            
            if status in ['completed', 'partially_completed'] and completion_comment:
                text += f"\n💬 <b>Комментарий:</b>\n{completion_comment}\n"
            
            if status not in ['completed', 'partially_completed']:
                text += "\nВыберите новый статус:"
            
            await callback.message.edit_text(
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
    
    logger.info(f"🔄 Reopen task #{task_id} requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name)
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
            "SELECT status FROM tasks WHERE id = %s",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            logger.warning(f"⚠️ Task #{task_id} not found")
            await callback.answer("❌ Задача не найдена.", show_alert=True)
            return
        
        current_status = task[0]
        
        if current_status not in ['completed', 'partially_completed']:
            logger.warning(f"⚠️ Task #{task_id} is not completed (status: {current_status})")
            await callback.answer("❌ Эта задача не завершена.", show_alert=True)
            return
        
        logger.debug(f"🔄 Reopening task #{task_id}, clearing completion data")
        
        cur.execute(
            """UPDATE tasks 
               SET status = 'in_progress', 
                   completion_comment = NULL, 
                   photo_file_id = NULL, 
                   updated_at = NOW() 
               WHERE id = %s""",
            (task_id,)
        )
        conn.commit()
        
        logger.info(f"✅ Admin {username} reopened task #{task_id}")
        
        await callback.answer("✅ Задача возвращена в работу", show_alert=True)
        
        cur.execute(
            """SELECT t.id, t.title, t.description, t.status, t.priority, t.due_date, 
                      u.username, t.created_at, t.assigned_to_id
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               WHERE t.id = %s""",
            (task_id,)
        )
        updated_task = cur.fetchone()
        
        if updated_task:
            tid, title, description, status, priority, due_date, assigned_username, created_at, assigned_to_id = updated_task
            
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
<b>Назначена:</b> @{assigned_username or '🆓 Свободна (можно взять)'}
<b>Создана:</b> {created_at.strftime('%Y-%m-%d %H:%M')}

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
    
    logger.info(f"📝 Completion comment received from {username}: {comment[:50]}...")
    
    user = get_or_create_user(telegram_id, username, first_name)
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
