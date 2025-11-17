"""
Photo handlers module
Обработчики фотографий при создании и завершении задач
"""
from datetime import datetime, timedelta
from aiogram import F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.handlers import photos_router
from app.database import get_db_connection
from app.services.users import get_or_create_user
from app.keyboards.main_menu import get_main_keyboard
from app.states import CompleteTaskStates, CreateTaskStates
from app.logging_config import get_logger
from app.config import get_now, combine_datetime, TIMEZONE

logger = get_logger(__name__)


@photos_router.callback_query(F.data == "photo_yes")
async def callback_photo_yes(callback: CallbackQuery, state: FSMContext):
    """Пользователь хочет добавить фото при завершении"""
    logger.info(f"📸 User {callback.from_user.username} wants to add completion photo")
    
    await state.set_state(CompleteTaskStates.waiting_for_photo)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="photo_no")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    
    try:
        await callback.message.edit_text(
            "📸 <b>Загрузите фото</b>\n\n"
            "Отправьте фотографию результата работы.\n"
            "Можно отправить одно фото.",
            parse_mode='HTML',
            reply_markup=cancel_keyboard
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer(
            "📸 <b>Загрузите фото</b>\n\n"
            "Отправьте фотографию результата работы.\n"
            "Можно отправить одно фото.",
            parse_mode='HTML',
            reply_markup=cancel_keyboard
        )
    await callback.answer()


@photos_router.callback_query(F.data == "photo_no")
async def callback_photo_no(callback: CallbackQuery, state: FSMContext):
    """Пользователь не хочет добавлять фото при завершении"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    logger.info(f"📝 User {username} completing task without photo")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        await state.clear()
        return
    
    data = await state.get_data()
    task_id = data.get('task_id')
    new_status = data.get('new_status')
    comment = data.get('comment')
    
    logger.info(f"💾 Completing task #{task_id} with status {new_status} without photo")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "UPDATE tasks SET status = ?, completion_comment = ?, updated_at = datetime('now') WHERE id = ?",
            (new_status, comment, task_id)
        )
        conn.commit()
        
        logger.debug(f"📊 Fetching task info for notifications")
        
        cur.execute(
            """SELECT t.id, t.title, t.description, t.priority, t.due_date, 
                      t.created_by_id, c.username as creator_username, c.telegram_id as creator_telegram_id
               FROM tasks t
               LEFT JOIN users c ON t.created_by_id = c.id
               WHERE t.id = ?""",
            (task_id,)
        )
        task_info = cur.fetchone()
        
        if task_info:
            task_id_val = task_info['id']
            title = task_info['title']
            description = task_info['description']
            priority = task_info['priority']
            due_date = task_info['due_date']
            created_by_id = task_info['created_by_id']
            creator_username = task_info.get('creator_username')
            creator_telegram_id = task_info.get('creator_telegram_id')
            
            priority_text = {
                'urgent': '🔴 Срочно',
                'high': '🟠 Высокий',
                'medium': '🟡 Средний',
                'low': '🟢 Низкий'
            }.get(priority, priority)
            
            if new_status == 'completed':
                confirmation = "✅ <b>Задача завершена!</b>\n\nКомментарий сохранён.\nСоздатель задачи получит уведомление."
            else:
                confirmation = "🔶 <b>Задача частично завершена!</b>\n\nКомментарий сохранён.\nСоздатель задачи получит уведомление о прогрессе."
            
            await callback.message.answer(
                confirmation,
                parse_mode='HTML',
                reply_markup=get_main_keyboard(user['role'])
            )
            
            logger.info(f"✅ Task #{task_id_val} completed with status {new_status}")
            
            if created_by_id and creator_telegram_id:
                try:
                    # Форматируем дату (SQLite возвращает строку)
                    due_date_str = due_date if due_date else 'не указан'
                    
                    if new_status == 'completed':
                        notification_text = f"""✅ <b>Задача завершена!</b>

<b>Задача #{task_id_val}</b>
<b>Название:</b> {title}
<b>Приоритет:</b> {priority_text}
<b>Срок был:</b> 📅 {due_date_str} (МСК)

<b>Исполнитель:</b> @{username}
<b>Комментарий:</b> {comment}

Нажмите кнопку ниже для просмотра задачи."""
                    else:
                        notification_text = f"""🔶 <b>Задача частично завершена!</b>

<b>Задача #{task_id_val}</b>
<b>Название:</b> {title}
<b>Приоритет:</b> {priority_text}
<b>Срок:</b> 📅 {due_date_str} (МСК)

<b>Исполнитель:</b> @{username}
<b>Отчёт о прогрессе:</b> {comment}

Задача ещё в работе. Нажмите кнопку ниже для просмотра."""
                    
                    task_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📂 Открыть задачу", callback_data=f"task_{task_id_val}")]
                    ])
                    
                    logger.info(f"📨 Sending completion notification to {creator_username}")
                    
                    await callback.message.bot.send_message(
                        chat_id=creator_telegram_id,
                        text=notification_text,
                        parse_mode='HTML',
                        reply_markup=task_keyboard
                    )
                    logger.info(f"✅ Completion notification sent to {creator_username} (task #{task_id_val})")
                except Exception as notif_error:
                    logger.warning(f"⚠️ Could not send completion notification: {notif_error}")
        
        await state.clear()
        logger.info(f"✅ Task #{task_id} completed by {username} with comment")
    
    except Exception as e:
        logger.error(f"❌ Error completing task #{task_id}: {e}", exc_info=True)
        await callback.message.answer("❌ Ошибка при завершении задачи", reply_markup=get_main_keyboard(user['role']))
    finally:
        cur.close()
        conn.close()


@photos_router.message(CompleteTaskStates.waiting_for_photo, F.photo)
async def process_completion_photo(message: Message, state: FSMContext):
    """Обработать загруженное фото при завершении"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    
    photo_file_id = message.photo[-1].file_id
    
    logger.info(f"📸 Completion photo received from {username}, file_id: {photo_file_id}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        logger.error(f"❌ User {username} lost authorization during completion photo upload")
        await message.answer("❌ Доступ запрещён")
        await state.clear()
        return
    
    data = await state.get_data()
    task_id = data.get('task_id')
    new_status = data.get('new_status')
    comment = data.get('comment')
    
    logger.info(f"💾 Completing task #{task_id} with status {new_status} WITH photo")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "UPDATE tasks SET status = ?, completion_comment = ?, photo_file_id = ?, updated_at = datetime('now') WHERE id = ?",
            (new_status, comment, photo_file_id, task_id)
        )
        conn.commit()
        
        logger.debug(f"📊 Fetching task info for notifications")
        
        cur.execute(
            """SELECT t.id, t.title, t.description, t.priority, t.due_date, 
                      t.created_by_id, c.username as creator_username, c.telegram_id as creator_telegram_id
               FROM tasks t
               LEFT JOIN users c ON t.created_by_id = c.id
               WHERE t.id = ?""",
            (task_id,)
        )
        task_info = cur.fetchone()
        
        if task_info:
            task_id_val = task_info['id']
            title = task_info['title']
            description = task_info['description']
            priority = task_info['priority']
            due_date = task_info['due_date']
            created_by_id = task_info['created_by_id']
            creator_username = task_info.get('creator_username')
            creator_telegram_id = task_info.get('creator_telegram_id')
            
            priority_text = {
                'urgent': '🔴 Срочно',
                'high': '🟠 Высокий',
                'medium': '🟡 Средний',
                'low': '🟢 Низкий'
            }.get(priority, priority)
            
            if new_status == 'completed':
                confirmation = "✅ <b>Задача завершена!</b>\n\n📸 Фото и комментарий сохранены.\nСоздатель задачи получит уведомление."
            else:
                confirmation = "🔶 <b>Задача частично завершена!</b>\n\n📸 Фото и комментарий сохранены.\nСоздатель задачи получит уведомление о прогрессе."
            
            await message.answer(
                confirmation,
                parse_mode='HTML',
                reply_markup=get_main_keyboard(user['role'])
            )
            
            logger.info(f"✅ Task #{task_id_val} completed with status {new_status} and photo")
            
            if created_by_id and creator_telegram_id:
                try:
                    # Форматируем дату (SQLite возвращает строку)
                    due_date_str = due_date if due_date else 'не указан'
                    
                    if new_status == 'completed':
                        caption = f"""✅ <b>Задача завершена!</b>

<b>Задача #{task_id_val}</b>
<b>Название:</b> {title}
<b>Приоритет:</b> {priority_text}
<b>Срок был:</b> 📅 {due_date_str} (МСК)

<b>Исполнитель:</b> @{username}
<b>Комментарий:</b> {comment}

Нажмите кнопку ниже для просмотра задачи."""
                    else:
                        caption = f"""🔶 <b>Задача частично завершена!</b>

<b>Задача #{task_id_val}</b>
<b>Название:</b> {title}
<b>Приоритет:</b> {priority_text}
<b>Срок:</b> 📅 {due_date_str} (МСК)

<b>Исполнитель:</b> @{username}
<b>Отчёт о прогрессе:</b> {comment}

Задача ещё в работе. Нажмите кнопку ниже для просмотра."""
                    
                    task_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📂 Открыть задачу", callback_data=f"task_{task_id_val}")]
                    ])
                    
                    logger.info(f"📨 Sending completion notification WITH photo to {creator_username}")
                    
                    await message.bot.send_photo(
                        chat_id=creator_telegram_id,
                        photo=photo_file_id,
                        caption=caption,
                        parse_mode='HTML',
                        reply_markup=task_keyboard
                    )
                    logger.info(f"✅ Completion notification with photo sent to {creator_username} (task #{task_id_val})")
                except Exception as notif_error:
                    logger.warning(f"⚠️ Could not send completion notification: {notif_error}")
        
        await state.clear()
        logger.info(f"✅ Task #{task_id} completed by {username} with comment and photo")
    
    except Exception as e:
        logger.error(f"❌ Error completing task #{task_id} with photo: {e}", exc_info=True)
        await message.answer("❌ Ошибка при завершении задачи", reply_markup=get_main_keyboard(user['role']))
    finally:
        cur.close()
        conn.close()


@photos_router.callback_query(F.data == "task_photo_yes")
async def callback_task_photo_yes(callback: CallbackQuery, state: FSMContext):
    """Пользователь хочет добавить фото к задаче при создании"""
    logger.info(f"📸 User {callback.from_user.username} wants to add task creation photo")
    
    await state.set_state(CreateTaskStates.waiting_for_task_photo)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="task_photo_no")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    
    try:
        await callback.message.edit_text(
            "📸 <b>Загрузите фото</b>\n\n"
            "Отправьте фотографию к задаче.\n"
            "Можно отправить одно фото.",
            parse_mode='HTML',
            reply_markup=cancel_keyboard
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer(
            "📸 <b>Загрузите фото</b>\n\n"
            "Отправьте фотографию к задаче.\n"
            "Можно отправить одно фото.",
            parse_mode='HTML',
            reply_markup=cancel_keyboard
        )
    await callback.answer()


@photos_router.callback_query(F.data == "task_photo_no")
async def callback_task_photo_no(callback: CallbackQuery, state: FSMContext):
    """Создать задачу без фото"""
    logger.info(f"📝 User {callback.from_user.username} creating task without photo")
    await create_task_with_photo(callback, state, None)


@photos_router.message(CreateTaskStates.waiting_for_task_photo, F.photo)
async def process_task_photo(message: Message, state: FSMContext):
    """Обработать загруженное фото задачи при создании"""
    photo_file_id = message.photo[-1].file_id
    logger.info(f"📸 Task creation photo received from {message.from_user.username}, file_id: {photo_file_id}")
    
    await create_task_with_photo(message, state, photo_file_id)


async def create_task_with_photo(callback_or_message, state: FSMContext, photo_file_id=None):
    """
    Создать задачу с фото или без
    
    Вспомогательная функция для создания задачи с опциональным фото.
    Используется как при создании задачи с фото, так и без него.
    """
    is_message = isinstance(callback_or_message, Message)
    
    if is_message:
        telegram_id = str(callback_or_message.from_user.id)
        username = callback_or_message.from_user.username
        first_name = callback_or_message.from_user.first_name or ''
    else:
        telegram_id = str(callback_or_message.from_user.id)
        username = callback_or_message.from_user.username
        first_name = callback_or_message.from_user.first_name or ''
    
    logger.info(f"➕ Creating task by {username}, has_photo={bool(photo_file_id)}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        logger.error(f"❌ User {username} lost authorization during task creation")
        if is_message:
            await callback_or_message.answer("❌ Доступ запрещён")
        else:
            await callback_or_message.answer("❌ Доступ запрещён", show_alert=True)
        await state.clear()
        return
    
    data = await state.get_data()
    title = data.get('title', '')
    description = data.get('description', '')
    priority = data.get('priority', 'medium')
    
    # Получаем дату и время, по умолчанию + 7 дней 23:59
    due_date_str = data.get('due_date')
    due_time_str = data.get('due_time', '23:59')
    
    if not due_date_str:
        # По умолчанию: через 7 дней
        default_due = get_now() + timedelta(days=7)
        due_date_str = default_due.strftime('%Y-%m-%d')
    
    # Комбинируем дату и время в TIMESTAMP с часовым поясом
    due_datetime = combine_datetime(due_date_str, due_time_str)
    assignee_id = data.get('assignee_id')
    
    logger.debug(f"📋 Task data: title={title[:30]}, priority={priority}, due_datetime={due_datetime}, assignee_id={assignee_id}")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if assignee_id:
            cur.execute(
                "SELECT username, telegram_id FROM users WHERE id = ?",
                (assignee_id,)
            )
            assignee = cur.fetchone()
            
            if not assignee:
                logger.error(f"❌ Assignee {assignee_id} not found")
                if is_message:
                    await callback_or_message.answer("❌ Исполнитель не найден")
                else:
                    await callback_or_message.answer("❌ Исполнитель не найден", show_alert=True)
                await state.clear()
                return
            
            assignee_username = assignee['username']
            assignee_telegram_id = assignee['telegram_id']
        else:
            assignee_username = None
            assignee_telegram_id = None
        
        logger.info(f"💾 Inserting task into database with photo_file_id={photo_file_id}")
        
        cur.execute(
            """INSERT INTO tasks 
               (title, description, priority, status, due_date, assigned_to_id, created_by_id, task_photo_file_id, created_at, updated_at)
               VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (
                title,
                description,
                priority,
                due_datetime,
                assignee_id,
                user['id'],
                photo_file_id
            )
        )
        task_id = cur.lastrowid
        cur.close()  # Закрываем курсор перед commit
        conn.commit()
        
        # Получаем созданную задачу с новым курсором
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, task_photo_file_id FROM tasks WHERE id = ?",
            (task_id,)
        )
        task = cur.fetchone()
        saved_photo_id = task['task_photo_file_id'] if task else None
        
        logger.info(f"✅ Task #{task_id} created successfully, saved_photo={saved_photo_id}")
        
        priority_text = {
            'urgent': '🔴 Срочно',
            'high': '🟠 Высокий',
            'medium': '🟡 Средний',
            'low': '🟢 Низкий'
        }.get(priority, priority)
        
        success_msg = f"✅ <b>Задача создана успешно!</b>\n\n"
        success_msg += f"ID: {task_id}\n"
        success_msg += f"Название: {title}\n"
        success_msg += f"Приоритет: {priority_text}\n"
        success_msg += f"Срок: 📅 {due_datetime.strftime('%d.%m.%Y %H:%M')} (МСК)\n"
        
        if assignee_username:
            success_msg += f"Исполнитель: @{assignee_username}\n"
        else:
            success_msg += f"Исполнитель: 🆓 Не назначена (свободная)\n"
        
        success_msg += f"Статус: ⏳ Ожидает\n"
        
        if photo_file_id:
            success_msg += f"\n📸 Фото прикреплено"
        
        if assignee_username:
            success_msg += f"\n\n📨 Уведомление отправлено исполнителю"
        
        if is_message:
            await callback_or_message.answer(
                success_msg,
                parse_mode='HTML',
                reply_markup=get_main_keyboard(user['role'])
            )
        else:
            await callback_or_message.message.edit_text(
                success_msg,
                parse_mode='HTML',
                reply_markup=get_main_keyboard(user['role'])
            )
            await callback_or_message.answer()
        
        await state.clear()
        
        if assignee_telegram_id:
            try:
                notification_text = f"""📋 <b>Вам назначена новая задача!</b>

<b>Задача #{task_id}</b>
<b>Название:</b> {title}
<b>Описание:</b> {description or 'Нет описания'}
<b>Приоритет:</b> {priority_text}
<b>Срок:</b> 📅 {due_datetime.strftime('%d.%m.%Y %H:%M')} (МСК)
<b>Создал:</b> @{username}
<b>Статус:</b> ⏳ Ожидает

Используйте /start для просмотра задачи."""
                
                task_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📂 Открыть задачу", callback_data=f"task_{task_id}")]
                ])
                
                if photo_file_id:
                    logger.info(f"📨 Sending notification WITH photo to {assignee_username}")
                    if is_message:
                        await callback_or_message.bot.send_photo(
                            chat_id=assignee_telegram_id,
                            photo=photo_file_id,
                            caption=notification_text,
                            parse_mode='HTML',
                            reply_markup=task_keyboard
                        )
                    else:
                        await callback_or_message.message.bot.send_photo(
                            chat_id=assignee_telegram_id,
                            photo=photo_file_id,
                            caption=notification_text,
                            parse_mode='HTML',
                            reply_markup=task_keyboard
                        )
                else:
                    logger.info(f"📨 Sending notification WITHOUT photo to {assignee_username}")
                    if is_message:
                        await callback_or_message.bot.send_message(
                            chat_id=assignee_telegram_id,
                            text=notification_text,
                            parse_mode='HTML',
                            reply_markup=task_keyboard
                        )
                    else:
                        await callback_or_message.message.bot.send_message(
                            chat_id=assignee_telegram_id,
                            text=notification_text,
                            parse_mode='HTML',
                            reply_markup=task_keyboard
                        )
                logger.info(f"✅ Notification sent to {assignee_username} (task #{task_id})")
            except Exception as notif_error:
                logger.warning(f"⚠️ Could not send notification to {assignee_username}: {notif_error}")
        
        logger.info(f"✅ Task creation complete: '{title}' by {username}")
    
    except Exception as e:
        logger.error(f"❌ Error creating task: {e}", exc_info=True)
        if is_message:
            await callback_or_message.answer("❌ Ошибка при создании задачи")
        else:
            await callback_or_message.answer("❌ Ошибка при создании задачи", show_alert=True)
    finally:
        cur.close()
        conn.close()
