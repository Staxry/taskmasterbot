"""
Photo handlers module
Обработчики фотографий при создании и завершении задач
"""
import asyncio
from datetime import datetime, timedelta
from aiogram import F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.handlers import photos_router
from app.database import get_db_connection
from app.services.users import get_or_create_user
from app.keyboards.main_menu import get_main_keyboard
from app.keyboards.task_keyboards import is_mobile_device
from app.states import CompleteTaskStates, CreateTaskStates
from app.logging_config import get_logger
from app.config import get_now, combine_datetime, TIMEZONE, TIMEZONE_ABBR

logger = get_logger(__name__)

# Словарь для хранения задач отложенного показа меню
# Формат: {key: (task, timestamp)}
_pending_photo_menus = {}


@photos_router.callback_query(F.data == "photo_yes")
async def callback_photo_yes(callback: CallbackQuery, state: FSMContext):
    """Пользователь хочет добавить фото при завершении"""
    logger.info(f"📸 User {callback.from_user.username} wants to add completion photo")
    
    # Инициализируем список фото в state
    await state.update_data(completion_photos=[])
    await state.set_state(CompleteTaskStates.waiting_for_photo)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Завершить без фото", callback_data="photo_no")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    
    try:
        await callback.message.edit_text(
            "📸 <b>Загрузите фото</b>\n\n"
            "Отправьте фотографии результата работы.\n"
            "Можно отправить несколько фото подряд.\n\n"
            "После загрузки всех фото нажмите 'Завершить без фото' для завершения задачи.",
            parse_mode='HTML',
            reply_markup=cancel_keyboard
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer(
            "📸 <b>Загрузите фото</b>\n\n"
            "Отправьте фотографии результата работы.\n"
            "Можно отправить несколько фото подряд.\n\n"
            "После загрузки всех фото нажмите 'Завершить без фото' для завершения задачи.",
            parse_mode='HTML',
            reply_markup=cancel_keyboard
        )
    await callback.answer()


@photos_router.callback_query(F.data == "photo_continue")
async def callback_photo_continue(callback: CallbackQuery, state: FSMContext):
    """Продолжить добавление фото при завершении"""
    user_id = str(callback.from_user.id)
    key = f"completion_{user_id}"
    
    # Отменяем задачу показа меню, если она есть
    if key in _pending_photo_menus:
        old_task, _ = _pending_photo_menus[key]
        if old_task and not old_task.done():
            old_task.cancel()
        del _pending_photo_menus[key]
    
    logger.info(f"➕ User {callback.from_user.username} continuing to add completion photos")
    
    # Просто подтверждаем и остаемся в состоянии waiting_for_photo
    await callback.answer("📸 Отправьте еще фото", show_alert=False)
    
    # Удаляем сообщение с меню
    try:
        await callback.message.delete()
    except Exception:
        pass


@photos_router.callback_query(F.data == "photo_no")
async def callback_photo_no(callback: CallbackQuery, state: FSMContext):
    """Завершить задачу с фото или без"""
    user_id = str(callback.from_user.id)
    key = f"completion_{user_id}"
    
    # Отменяем задачу показа меню, если она есть
    if key in _pending_photo_menus:
        old_task, _ = _pending_photo_menus[key]
        if old_task and not old_task.done():
            old_task.cancel()
        del _pending_photo_menus[key]
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        await state.clear()
        return
    
    data = await state.get_data()
    task_id = data.get('task_id')
    new_status = data.get('new_status')
    comment = data.get('comment')
    completion_photos = data.get('completion_photos', [])
    
    logger.info(f"💾 Completing task #{task_id} with status {new_status}, photos: {len(completion_photos)}")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Определяем первое фото для сохранения в старое поле (для обратной совместимости)
        first_photo = completion_photos[0] if completion_photos else None
        
        cur.execute(
            "UPDATE tasks SET status = ?, completion_comment = ?, photo_file_id = ?, updated_at = datetime('now') WHERE id = ?",
            (new_status, comment, first_photo, task_id)
        )
        
        # Сохраняем все фото в таблицу task_photos
        if completion_photos:
            for photo_file_id in completion_photos:
                cur.execute(
                    "INSERT INTO task_photos (task_id, photo_file_id) VALUES (?, ?)",
                    (task_id, photo_file_id)
                )
            logger.info(f"📸 Saved {len(completion_photos)} completion photos to task_photos")
        
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
            
            if completion_photos:
                if new_status == 'completed':
                    confirmation = f"✅ <b>Задача завершена!</b>\n\n📸 Фото ({len(completion_photos)} шт.) и комментарий сохранены.\nСоздатель задачи получит уведомление (фото можно посмотреть в задаче)."
                else:
                    confirmation = f"🔶 <b>Задача частично завершена!</b>\n\n📸 Фото ({len(completion_photos)} шт.) и комментарий сохранены.\nСоздатель задачи получит уведомление о прогрессе (фото можно посмотреть в задаче)."
            else:
                if new_status == 'completed':
                    confirmation = "✅ <b>Задача завершена!</b>\n\nКомментарий сохранён.\nСоздатель задачи получит уведомление."
                else:
                    confirmation = "🔶 <b>Задача частично завершена!</b>\n\nКомментарий сохранён.\nСоздатель задачи получит уведомление о прогрессе."
            
            await callback.message.answer(
                confirmation,
                parse_mode='HTML',
                reply_markup=get_main_keyboard(user['role'], is_mobile_device())
            )
            
            logger.info(f"✅ Task #{task_id_val} completed with status {new_status}")
            
            if created_by_id and creator_telegram_id:
                try:
                    # Форматируем дату (SQLite возвращает строку)
                    due_date_str = due_date if due_date else 'не указан'
                    
                    # Форматируем имя исполнителя
                    if first_name or last_name:
                        executor_display = f"{first_name or ''} {last_name or ''}".strip() + f" (@{username})"
                    else:
                        executor_display = f"@{username}"
                    
                    task_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📂 Открыть задачу", callback_data=f"task_{task_id_val}")]
                    ])
                    
                    # Отправляем только текстовое уведомление без фото
                    # Фото можно посмотреть через кнопку "Открыть задачу"
                    if new_status == 'completed':
                        notification_text = f"""✅ <b>Задача завершена!</b>

<b>Задача #{task_id_val}</b>
<b>Название:</b> {title}
<b>Приоритет:</b> {priority_text}
<b>Срок был:</b> 📅 {due_date_str} ({TIMEZONE_ABBR})

<b>Исполнитель:</b> {executor_display}
<b>Комментарий:</b> {comment}"""
                        
                        if completion_photos:
                            notification_text += f"\n\n📸 Фото результата: {len(completion_photos)} шт. (можно посмотреть в задаче)"
                        
                        notification_text += "\n\nНажмите кнопку ниже для просмотра задачи."
                    else:
                        notification_text = f"""🔶 <b>Задача частично завершена!</b>

<b>Задача #{task_id_val}</b>
<b>Название:</b> {title}
<b>Приоритет:</b> {priority_text}
<b>Срок:</b> 📅 {due_date_str} ({TIMEZONE_ABBR})

<b>Исполнитель:</b> {executor_display}
<b>Отчёт о прогрессе:</b> {comment}"""
                        
                        if completion_photos:
                            notification_text += f"\n\n📸 Фото результата: {len(completion_photos)} шт. (можно посмотреть в задаче)"
                        
                        notification_text += "\n\nЗадача ещё в работе. Нажмите кнопку ниже для просмотра."
                    
                    logger.info(f"📨 Sending completion notification to {creator_username} (photos: {len(completion_photos) if completion_photos else 0})")
                    
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


async def show_completion_menu_after_delay(message: Message, state: FSMContext, delay: float = 2.0):
    """Показать меню завершения после задержки (если не пришло новое фото)"""
    user_id = str(message.from_user.id)
    key = f"completion_{user_id}"
    
    # Сохраняем ссылку на текущую задачу для проверки после задержки
    import asyncio
    current_task = asyncio.current_task()
    
    logger.info(f"⏳ Completion menu task started for user {user_id}, key: {key}, delay: {delay}s")
    
    # Ждем задержку
    logger.info(f"⏳ Waiting {delay} seconds before showing completion menu...")
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        logger.info(f"⏭ Completion menu task was cancelled during sleep")
        if key in _pending_photo_menus:
            stored_task, _ = _pending_photo_menus[key]
            if stored_task == current_task:
                del _pending_photo_menus[key]
        raise
    
    logger.info(f"⏰ Delay finished, checking if completion menu should be shown...")
    
    # Проверяем, что это все еще актуальная задача (не была заменена новой)
    if key not in _pending_photo_menus:
        logger.info(f"⏭ Skipping completion menu - key not found (was replaced by new photo)")
        return
    
    stored_task, _ = _pending_photo_menus.get(key, (None, None))
    if stored_task != current_task:
        logger.info(f"⏭ Skipping completion menu - task was replaced")
        return
    
    # Удаляем задачу из словаря
    if key in _pending_photo_menus:
        del _pending_photo_menus[key]
    
    data = await state.get_data()
    completion_photos = data.get('completion_photos', [])
    photo_count = len(completion_photos)
    
    # Показываем меню завершения
    finish_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Завершить задачу", callback_data="photo_no")],
        [InlineKeyboardButton(text="➕ Добавить еще фото", callback_data="photo_continue")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    
    await message.answer(
        f"📸 <b>Фото загружено!</b>\n\n"
        f"Всего фото: {photo_count}\n\n"
        f"Выберите действие:",
        parse_mode='HTML',
        reply_markup=finish_keyboard
    )
    
    logger.info(f"✅ Completion menu shown, total photos: {photo_count}")


@photos_router.message(CompleteTaskStates.waiting_for_photo, F.photo)
async def process_completion_photo(message: Message, state: FSMContext):
    """Обработать загруженное фото при завершении"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    last_name = message.from_user.last_name or ''
    
    photo_file_id = message.photo[-1].file_id
    
    logger.info(f"📸 Completion photo received from {username}, file_id: {photo_file_id}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        logger.error(f"❌ User {username} lost authorization during completion photo upload")
        await message.answer("❌ Доступ запрещён")
        await state.clear()
        return
    
    data = await state.get_data()
    completion_photos = data.get('completion_photos', [])
    
    # Добавляем фото в список
    completion_photos.append(photo_file_id)
    await state.update_data(completion_photos=completion_photos)
    
    photo_count = len(completion_photos)
    logger.info(f"✅ Completion photo {photo_count} added, total: {photo_count}")
    
    # Показываем только короткое подтверждение
    await message.answer(
        f"✅ Фото {photo_count} добавлено",
        parse_mode='HTML'
    )
    
    # Запускаем задачу для показа меню после задержки
    user_id = str(message.from_user.id)
    key = f"completion_{user_id}"
    import time
    task_timestamp = time.time()
    task_menu = asyncio.create_task(
        show_completion_menu_after_delay(message, state, delay=2.0)
    )
    _pending_photo_menus[key] = (task_menu, task_timestamp)


@photos_router.callback_query(F.data == "task_photo_yes")
async def callback_task_photo_yes(callback: CallbackQuery, state: FSMContext):
    """Пользователь хочет добавить фото к задаче при создании"""
    logger.info(f"📸 User {callback.from_user.username} wants to add task creation photo")
    
    await state.set_state(CreateTaskStates.waiting_for_task_photo)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Завершить добавление фото", callback_data="task_photo_no")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    
    try:
        await callback.message.edit_text(
            "📸 <b>Загрузите фото</b>\n\n"
            "Отправьте фотографию к задаче.\n"
            "Можно отправить несколько фото подряд.\n"
            "Нажмите 'Завершить добавление фото' когда закончите.",
            parse_mode='HTML',
            reply_markup=cancel_keyboard
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer(
            "📸 <b>Загрузите фото</b>\n\n"
            "Отправьте фотографию к задаче.\n"
            "Можно отправить несколько фото подряд.\n"
            "Нажмите 'Завершить добавление фото' когда закончите.",
            parse_mode='HTML',
            reply_markup=cancel_keyboard
        )
    await callback.answer()


@photos_router.callback_query(F.data == "task_photo_no")
async def callback_task_photo_no(callback: CallbackQuery, state: FSMContext):
    """Завершить добавление фото и создать задачу"""
    user_id = str(callback.from_user.id)
    data = await state.get_data()
    task_id = data.get('task_id')
    
    # Отменяем задачу показа меню, если она есть
    if task_id:
        key = f"{user_id}_{task_id}"
        if key in _pending_photo_menus:
            old_task, _ = _pending_photo_menus[key]
            if old_task and not old_task.done():
                old_task.cancel()
            del _pending_photo_menus[key]
    
    # Если задача уже создана (были фото), просто завершаем процесс
    if task_id:
        logger.info(f"✅ User {callback.from_user.username} finished adding photos to task #{task_id}")
        await finish_task_creation(callback, state, task_id)
    else:
        # Если фото не было, создаем задачу без фото
        logger.info(f"📝 User {callback.from_user.username} creating task without photo")
        await create_task_with_photo(callback, state, None)


@photos_router.callback_query(F.data == "task_photo_continue")
async def callback_task_photo_continue(callback: CallbackQuery, state: FSMContext):
    """Продолжить добавление фото"""
    user_id = str(callback.from_user.id)
    data = await state.get_data()
    task_id = data.get('task_id')
    
    # Отменяем задачу показа меню, если она есть
    if task_id:
        key = f"{user_id}_{task_id}"
        if key in _pending_photo_menus:
            old_task, _ = _pending_photo_menus[key]
            if old_task and not old_task.done():
                old_task.cancel()
            del _pending_photo_menus[key]
    
    logger.info(f"➕ User {callback.from_user.username} continuing to add photos to task #{task_id}")
    
    # Просто подтверждаем и остаемся в состоянии waiting_for_task_photo
    await callback.answer("📸 Отправьте еще фото", show_alert=False)
    
    # Удаляем сообщение с меню
    try:
        await callback.message.delete()
    except Exception:
        pass


@photos_router.message(CreateTaskStates.waiting_for_task_photo, F.photo)
async def process_task_photo(message: Message, state: FSMContext):
    """Обработать загруженное фото задачи при создании"""
    photo_file_id = message.photo[-1].file_id
    logger.info(f"📸 Task creation photo received from {message.from_user.username}, file_id: {photo_file_id}")
    
    data = await state.get_data()
    task_id = data.get('task_id')
    
    # Если задача уже создана, просто добавляем фото
    if task_id:
        await add_photo_to_task(message, state, task_id, photo_file_id)
    else:
        # Создаем задачу с первым фото
        await create_task_with_photo(message, state, photo_file_id)


async def show_task_photo_menu_after_delay(message: Message, state: FSMContext, task_id: int, delay: float = 3.0):
    """Показать меню с кнопками после задержки при создании задачи (если не пришло новое фото)"""
    user_id = str(message.from_user.id)
    key = f"{user_id}_{task_id}"
    
    # Сохраняем timestamp для проверки актуальности задачи
    import time
    task_timestamp = time.time()
    
    logger.info(f"⏳ Task photo menu task started for user {user_id}, task {task_id}, key: {key}, delay: {delay}s, timestamp={task_timestamp}")
    
    # Ждем задержку
    logger.info(f"⏳ Waiting {delay} seconds before showing menu for task #{task_id}...")
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        logger.info(f"⏭ Task photo menu task was cancelled during sleep for task #{task_id}")
        if key in _pending_photo_menus:
            stored_task, stored_timestamp = _pending_photo_menus[key]
            if stored_timestamp == task_timestamp:
                del _pending_photo_menus[key]
        raise
    
    logger.info(f"⏰ Delay finished for task #{task_id}, checking if menu should be shown...")
    
    # Проверяем, что это все еще актуальная задача (не была заменена новой)
    if key not in _pending_photo_menus:
        logger.info(f"⏭ Skipping task photo menu - key not found (was replaced by new photo)")
        return
    
    stored_task, stored_timestamp = _pending_photo_menus.get(key, (None, None))
    if stored_timestamp != task_timestamp:
        logger.info(f"⏭ Skipping task photo menu - task was replaced (stored timestamp={stored_timestamp}, current timestamp={task_timestamp})")
        return
    
    # Удаляем задачу из словаря
    if key in _pending_photo_menus:
        del _pending_photo_menus[key]
    logger.info(f"✅ Task photo menu will be shown for task #{task_id}")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Подсчитываем количество фото
        cur.execute("SELECT COUNT(*) as count FROM task_photos WHERE task_id = ?", (task_id,))
        photo_count = cur.fetchone()['count']
        
        # Получаем информацию о задаче
        cur.execute("SELECT id, title FROM tasks WHERE id = ?", (task_id,))
        task = cur.fetchone()
        task_title = task['title'] if task else f"#{task_id}"
        
        # Показываем итоговое меню
        menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Завершить добавление фото", callback_data="task_photo_no"),
                InlineKeyboardButton(text="➕ Добавить еще", callback_data="task_photo_continue")
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ])
        
        # Используем bot напрямую, чтобы не зависеть от объекта message
        try:
            from app.main import bot
            chat_id = message.chat.id
            
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ <b>Задача создана!</b>\n\n"
                     f"ID: {task_id}\n"
                     f"📸 Добавлено фото: {photo_count} шт.\n\n"
                     f"Выберите действие:",
                parse_mode='HTML',
                reply_markup=menu_keyboard
            )
            logger.info(f"✅ Task photo menu shown for task #{task_id}, total photos: {photo_count}")
        except Exception as e:
            logger.error(f"❌ Error showing task photo menu: {e}", exc_info=True)
        
    except Exception as e:
        logger.error(f"❌ Error showing task photo menu: {e}", exc_info=True)
    finally:
        cur.close()
        conn.close()


async def show_photo_menu_after_delay(message: Message, state: FSMContext, task_id: int, delay: float = 2.0):
    """Показать меню с кнопками после задержки (если не пришло новое фото)"""
    user_id = str(message.from_user.id)
    key = f"{user_id}_{task_id}"
    
    # Отменяем предыдущую задачу, если она есть
    if key in _pending_photo_menus:
        old_task, _ = _pending_photo_menus[key]
        if old_task and not old_task.done():
            old_task.cancel()
        logger.debug(f"🔄 Cancelled previous photo menu task for user {user_id}, task {task_id}")
    
    # Ждем задержку
    await asyncio.sleep(delay)
    
    # Проверяем, не была ли задача отменена
    if key in _pending_photo_menus:
        stored_task, _ = _pending_photo_menus[key]
        if stored_task and stored_task.cancelled():
            logger.debug(f"⏭ Skipping photo menu - task was cancelled")
            del _pending_photo_menus[key]
            return
    
    # Удаляем задачу из словаря
    if key in _pending_photo_menus:
        del _pending_photo_menus[key]
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Подсчитываем количество фото
        cur.execute("SELECT COUNT(*) as count FROM task_photos WHERE task_id = ?", (task_id,))
        photo_count = cur.fetchone()['count']
        
        # Показываем итоговое меню
        menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Завершить добавление фото", callback_data="task_photo_no"),
                InlineKeyboardButton(text="➕ Добавить еще", callback_data="task_photo_continue")
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ])
        
        await message.answer(
            f"📸 <b>Фото загружено!</b>\n\n"
            f"Всего фото к задаче: {photo_count}\n\n"
            f"Выберите действие:",
            parse_mode='HTML',
            reply_markup=menu_keyboard
        )
        
        logger.info(f"✅ Photo menu shown for task #{task_id}, total photos: {photo_count}")
        
    except Exception as e:
        logger.error(f"❌ Error showing photo menu: {e}", exc_info=True)
    finally:
        cur.close()
        conn.close()


async def add_photo_to_task(message: Message, state: FSMContext, task_id: int, photo_file_id: str):
    """Добавить фото к уже созданной задаче"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    
    logger.info(f"📸 Adding additional photo to task #{task_id} from {username}")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Проверяем, существует ли задача
        cur.execute("SELECT id, title FROM tasks WHERE id = ?", (task_id,))
        task = cur.fetchone()
        
        if not task:
            logger.error(f"❌ Task #{task_id} not found")
            await message.answer("❌ Задача не найдена")
            await state.clear()
            return
        
        # Добавляем фото в таблицу task_photos
        cur.execute(
            "INSERT INTO task_photos (task_id, photo_file_id) VALUES (?, ?)",
            (task_id, photo_file_id)
        )
        conn.commit()
        
        # Подсчитываем количество фото
        cur.execute("SELECT COUNT(*) as count FROM task_photos WHERE task_id = ?", (task_id,))
        photo_count = cur.fetchone()['count']
        
        logger.info(f"✅ Photo added to task #{task_id}, total photos: {photo_count}")
        
        # Показываем только короткое подтверждение без кнопок
        await message.answer(
            f"✅ Фото {photo_count} добавлено",
            parse_mode='HTML'
        )
        
        # Запускаем задачу для показа меню после задержки
        # При создании задачи всегда используем show_task_photo_menu_after_delay
        # (так как мы в состоянии CreateTaskStates.waiting_for_task_photo)
        user_id = str(message.from_user.id)
        key = f"{user_id}_{task_id}"
        logger.info(f"🔄 Starting task photo menu task for user {user_id}, task {task_id}, key: {key} (additional photo)")
        
        # Отменяем предыдущую задачу, если она есть
        if key in _pending_photo_menus:
            old_task, _ = _pending_photo_menus[key]
            if old_task and not old_task.done():
                old_task.cancel()
            logger.info(f"🔄 Cancelled previous menu task for key: {key}")
        
        import time
        task_timestamp = time.time()
        task_menu = asyncio.create_task(
            show_task_photo_menu_after_delay(message, state, task_id, delay=3.0)
        )
        _pending_photo_menus[key] = (task_menu, task_timestamp)
        logger.info(f"✅ Task photo menu task added to pending menus, key: {key}, total pending: {len(_pending_photo_menus)}")
        
    except Exception as e:
        logger.error(f"❌ Error adding photo to task #{task_id}: {e}", exc_info=True)
        await message.answer("❌ Ошибка при добавлении фото")
    finally:
        cur.close()
        conn.close()


async def finish_task_creation(callback: CallbackQuery, state: FSMContext, task_id: int):
    """Завершить создание задачи и отправить уведомления"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"✅ Finishing task creation for task #{task_id} by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        await state.clear()
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Получаем информацию о задаче
        cur.execute("""
            SELECT t.id, t.title, t.description, t.priority, t.due_date, 
                   t.assigned_to_id, t.created_by_id,
                   u.username as assignee_username, u.telegram_id as assignee_telegram_id,
                   u.first_name as assignee_first_name, u.last_name as assignee_last_name
            FROM tasks t
            LEFT JOIN users u ON t.assigned_to_id = u.id
            WHERE t.id = ?
        """, (task_id,))
        task = cur.fetchone()
        
        if not task:
            logger.error(f"❌ Task #{task_id} not found")
            await callback.answer("❌ Задача не найдена", show_alert=True)
            await state.clear()
            return
        
        # Получаем все фото задачи
        cur.execute("SELECT photo_file_id FROM task_photos WHERE task_id = ? ORDER BY created_at", (task_id,))
        photos = cur.fetchall()
        photo_file_ids = [p['photo_file_id'] for p in photos]
        
        title = task['title']
        description = task['description']
        priority = task['priority']
        due_datetime = task['due_date']
        assignee_id = task['assigned_to_id']
        assignee_username = task.get('assignee_username')
        assignee_telegram_id = task.get('assignee_telegram_id')
        assignee_first_name = task.get('assignee_first_name')
        assignee_last_name = task.get('assignee_last_name')
        
        priority_text = {
            'urgent': '🔴 Срочно',
            'high': '🟠 Высокий',
            'medium': '🟡 Средний',
            'low': '🟢 Низкий'
        }.get(priority, priority)
        
        # Форматируем дату
        if isinstance(due_datetime, str):
            due_datetime_str = due_datetime
        else:
            due_datetime_str = due_datetime.strftime('%d.%m.%Y %H:%M')
        
        success_msg = f"✅ <b>Задача создана успешно!</b>\n\n"
        success_msg += f"ID: {task_id}\n"
        success_msg += f"Название: {title}\n"
        success_msg += f"Приоритет: {priority_text}\n"
        success_msg += f"Срок: 📅 {due_datetime_str} ({TIMEZONE_ABBR})\n"
        
        if assignee_username:
            if assignee_first_name or assignee_last_name:
                assignee_display = f"{assignee_first_name or ''} {assignee_last_name or ''}".strip() + f" (@{assignee_username})"
            else:
                assignee_display = f"@{assignee_username}"
            success_msg += f"Исполнитель: {assignee_display}\n"
        else:
            success_msg += f"Исполнитель: 🆓 Не назначена (свободная)\n"
        
        success_msg += f"Статус: ⏳ Ожидает\n"
        
        if photo_file_ids:
            success_msg += f"\n📸 Фото прикреплено: {len(photo_file_ids)} шт."
        
        if assignee_username:
            success_msg += f"\n\n📨 Уведомление отправлено исполнителю"
        elif assignee_id is None:
            success_msg += f"\n\n📢 Уведомления отправлены всем пользователям"
        
        await callback.message.edit_text(
            success_msg,
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user['role'])
        )
        await callback.answer()
        
        await state.clear()
        
        # Отправляем уведомления
        if assignee_telegram_id:
            try:
                if first_name or last_name:
                    creator_display = f"{first_name or ''} {last_name or ''}".strip() + f" (@{username})"
                else:
                    creator_display = f"@{username}"
                
                notification_text = f"""📋 <b>Вам назначена новая задача!</b>

<b>Задача #{task_id}</b>
<b>Название:</b> {title}
<b>Описание:</b> {description or 'Нет описания'}
<b>Приоритет:</b> {priority_text}
<b>Срок:</b> 📅 {due_datetime_str} ({TIMEZONE_ABBR})
<b>Создал:</b> {creator_display}
<b>Статус:</b> ⏳ Ожидает

Используйте /start для просмотра задачи."""
                
                task_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📂 Открыть задачу", callback_data=f"task_{task_id}")]
                ])
                
                if photo_file_ids:
                    # Сначала отправляем все фото без подписи
                    logger.info(f"📨 Sending {len(photo_file_ids)} photo(s) first, then notification to {assignee_username}")
                    for photo_id in photo_file_ids:
                        await callback.message.bot.send_photo(
                            chat_id=assignee_telegram_id,
                            photo=photo_id
                        )
                    # Потом отправляем текстовое сообщение с описанием задачи и кнопкой
                    await callback.message.bot.send_message(
                        chat_id=assignee_telegram_id,
                        text=notification_text,
                        parse_mode='HTML',
                        reply_markup=task_keyboard
                    )
                else:
                    logger.info(f"📨 Sending notification WITHOUT photo to {assignee_username}")
                    await callback.message.bot.send_message(
                        chat_id=assignee_telegram_id,
                        text=notification_text,
                        parse_mode='HTML',
                        reply_markup=task_keyboard
                    )
                logger.info(f"✅ Notification sent to {assignee_username} (task #{task_id})")
            except Exception as notif_error:
                logger.warning(f"⚠️ Could not send notification to {assignee_username}: {notif_error}")
        
        # Уведомления для свободных задач
        if assignee_id is None:
            logger.info(f"📢 Task #{task_id} created without assignee, notifying all users")
            
            cur.execute("SELECT telegram_id, username FROM users WHERE role IN ('admin', 'employee')")
            all_users = cur.fetchall()
            
            priority_emoji = {
                'urgent': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '🟢'
            }.get(priority, '⚪')
            
            priority_text_notification = {
                'urgent': '🔴 Срочно',
                'high': '🟠 Высокий',
                'medium': '🟡 Средний',
                'low': '🟢 Низкий'
            }.get(priority, priority)
            
            if first_name or last_name:
                creator_display = f"{first_name or ''} {last_name or ''}".strip() + f" (@{username})"
            else:
                creator_display = f"@{username}"
            
            broadcast_message = f"""🆓 <b>Новая свободная задача!</b>

{priority_emoji} <b>#{task_id}:</b> {title}
📝 <b>Описание:</b> {description or 'Нет описания'}
<b>Приоритет:</b> {priority_text_notification}
📅 <b>Срок:</b> {due_datetime_str} ({TIMEZONE_ABBR})
👤 <b>Создал:</b> {creator_display}

⚡ Задача доступна для выполнения. Кто-то может взять её в работу!"""
            
            task_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📂 Открыть задачу", callback_data=f"task_{task_id}")]
            ])
            
            notification_count = 0
            for user_data in all_users:
                if user_data['telegram_id'] == telegram_id:
                    continue
                
                try:
                    if photo_file_ids:
                        # Сначала отправляем все фото без подписи
                        for photo_id in photo_file_ids:
                            await callback.message.bot.send_photo(
                                chat_id=user_data['telegram_id'],
                                photo=photo_id
                            )
                        # Потом отправляем текстовое сообщение с описанием задачи и кнопкой
                        await callback.message.bot.send_message(
                            chat_id=user_data['telegram_id'],
                            text=broadcast_message,
                            parse_mode='HTML',
                            reply_markup=task_keyboard
                        )
                    else:
                        await callback.message.bot.send_message(
                            chat_id=user_data['telegram_id'],
                            text=broadcast_message,
                            parse_mode='HTML',
                            reply_markup=task_keyboard
                        )
                    notification_count += 1
                except Exception as e:
                    logger.warning(f"⚠️ Failed to send notification to {user_data['username']}: {e}")
            
            logger.info(f"📧 Sent {notification_count} notifications about new free task #{task_id}")
        
        logger.info(f"✅ Task creation complete: '{title}' by {username}")
    
    except Exception as e:
        logger.error(f"❌ Error finishing task creation: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при завершении создания задачи", show_alert=True)
    finally:
        cur.close()
        conn.close()


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
        last_name = callback_or_message.from_user.last_name or ''
    else:
        telegram_id = str(callback_or_message.from_user.id)
        username = callback_or_message.from_user.username
        first_name = callback_or_message.from_user.first_name or ''
        last_name = callback_or_message.from_user.last_name or ''
    
    logger.info(f"➕ Creating task by {username}, has_photo={bool(photo_file_id)}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        logger.error(f"❌ User {username} lost authorization during task creation")
        if is_message:
            await callback_or_message.answer("❌ Доступ запрещён")
        else:
            await callback_or_message.answer("❌ Доступ запрещён", show_alert=True)
        await state.clear()
        return
    
    data = await state.get_data()
    title = data.get('title', '').strip() if data.get('title') else ''
    description = data.get('description', '')
    priority = data.get('priority', 'medium')
    
    # Валидация: проверяем, что title не пустой
    if not title:
        logger.error(f"❌ Attempt to create task with empty title by {username}")
        if is_message:
            await callback_or_message.answer("❌ Ошибка: название задачи не может быть пустым. Пожалуйста, начните создание задачи заново.")
        else:
            await callback_or_message.answer("❌ Ошибка: название задачи не может быть пустым.", show_alert=True)
        await state.clear()
        return
    
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
                "SELECT username, telegram_id, first_name, last_name FROM users WHERE id = ?",
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
            assignee_first_name = assignee.get('first_name')
            assignee_last_name = assignee.get('last_name')
        else:
            assignee_username = None
            assignee_telegram_id = None
            assignee_first_name = None
            assignee_last_name = None
        
        logger.info(f"💾 Inserting task into database")
        
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
                photo_file_id  # Сохраняем первое фото в старое поле для обратной совместимости
            )
        )
        task_id = cur.lastrowid
        
        # Если есть фото, сохраняем его в новую таблицу task_photos
        if photo_file_id:
            cur.execute(
                "INSERT INTO task_photos (task_id, photo_file_id) VALUES (?, ?)",
                (task_id, photo_file_id)
            )
            logger.info(f"📸 First photo saved to task_photos for task #{task_id}")
        
        cur.close()  # Закрываем курсор перед commit
        conn.commit()
        
        # Сохраняем task_id в state для возможности добавления дополнительных фото
        await state.update_data(task_id=task_id)
        
        # Получаем созданную задачу с новым курсором
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title FROM tasks WHERE id = ?",
            (task_id,)
        )
        task = cur.fetchone()
        
        logger.info(f"✅ Task #{task_id} created successfully, has_photo={bool(photo_file_id)}")
        
        # Если фото нет, сразу завершаем создание и отправляем уведомления
        if not photo_file_id:
            # Завершаем создание задачи без фото
            await finish_task_creation_without_photos(callback_or_message, state, task_id, user, 
                                                      title, description, priority, due_datetime,
                                                      assignee_id, assignee_username, assignee_telegram_id,
                                                      assignee_first_name, assignee_last_name,
                                                      first_name, last_name, username, is_message)
            return
        
        # Если есть фото, остаемся в состоянии waiting_for_task_photo для добавления еще фото
        # Не показываем сообщение сразу - используем механизм с задержкой для массовой загрузки
        if is_message:
            # Показываем только короткое подтверждение
            await callback_or_message.answer(
                f"✅ Фото 1 добавлено",
                parse_mode='HTML'
            )
            
            # Запускаем задачу для показа меню после задержки
            user_id = str(callback_or_message.from_user.id)
            key = f"{user_id}_{task_id}"
            logger.info(f"🔄 Starting task photo menu task for user {user_id}, task {task_id}, key: {key}")
            
            # Отменяем предыдущую задачу, если она есть
            if key in _pending_photo_menus:
                old_task, _ = _pending_photo_menus[key]
                if old_task and not old_task.done():
                    old_task.cancel()
                logger.info(f"🔄 Cancelled previous menu task for key: {key}")
            
            import time
            task_timestamp = time.time()
            task_menu = asyncio.create_task(
                show_task_photo_menu_after_delay(callback_or_message, state, task_id, delay=3.0)
            )
            _pending_photo_menus[key] = (task_menu, task_timestamp)
            logger.info(f"✅ Task photo menu task added to pending menus, key: {key}, total pending: {len(_pending_photo_menus)}")
        else:
            # Для callback тоже используем механизм с задержкой
            # Но сначала нужно отправить сообщение пользователю
            try:
                await callback_or_message.message.delete()
            except Exception:
                pass
            
            await callback_or_message.message.answer(
                f"✅ Фото 1 добавлено",
                parse_mode='HTML'
            )
            
            # Запускаем задачу для показа меню после задержки
            user_id = str(callback_or_message.from_user.id)
            key = f"{user_id}_{task_id}"
            logger.info(f"🔄 Starting task photo menu task for user {user_id}, task {task_id}, key: {key} (callback)")
            
            # Отменяем предыдущую задачу, если она есть
            if key in _pending_photo_menus:
                old_task, _ = _pending_photo_menus[key]
                if old_task and not old_task.done():
                    old_task.cancel()
                logger.info(f"🔄 Cancelled previous menu task for key: {key}")
            
            import time
            task_timestamp = time.time()
            task_menu = asyncio.create_task(
                show_task_photo_menu_after_delay(callback_or_message.message, state, task_id, delay=3.0)
            )
            _pending_photo_menus[key] = (task_menu, task_timestamp)
            logger.info(f"✅ Task photo menu task added to pending menus, key: {key}, total pending: {len(_pending_photo_menus)}")
            await callback_or_message.answer()
    
    except Exception as e:
        logger.error(f"❌ Error creating task: {e}", exc_info=True)
        if is_message:
            await callback_or_message.answer("❌ Ошибка при создании задачи")
        else:
            await callback_or_message.answer("❌ Ошибка при создании задачи", show_alert=True)
    finally:
        cur.close()
        conn.close()


async def finish_task_creation_without_photos(callback_or_message, state: FSMContext, task_id: int, user: dict,
                                              title: str, description: str, priority: str, due_datetime,
                                              assignee_id, assignee_username, assignee_telegram_id,
                                              assignee_first_name, assignee_last_name,
                                              first_name, last_name, username, is_message):
    """Завершить создание задачи без фото и отправить уведомления"""
    from datetime import datetime
    
    priority_text = {
        'urgent': '🔴 Срочно',
        'high': '🟠 Высокий',
        'medium': '🟡 Средний',
        'low': '🟢 Низкий'
    }.get(priority, priority)
    
    # Форматируем дату
    if isinstance(due_datetime, str):
        due_datetime_str = due_datetime
    else:
        due_datetime_str = due_datetime.strftime('%d.%m.%Y %H:%M')
    
    success_msg = f"✅ <b>Задача создана успешно!</b>\n\n"
    success_msg += f"ID: {task_id}\n"
    success_msg += f"Название: {title}\n"
    success_msg += f"Приоритет: {priority_text}\n"
    success_msg += f"Срок: 📅 {due_datetime_str} ({TIMEZONE_ABBR})\n"
    
    if assignee_username:
        if assignee_first_name or assignee_last_name:
            assignee_display = f"{assignee_first_name or ''} {assignee_last_name or ''}".strip() + f" (@{assignee_username})"
        else:
            assignee_display = f"@{assignee_username}"
        success_msg += f"Исполнитель: {assignee_display}\n"
    else:
        success_msg += f"Исполнитель: 🆓 Не назначена (свободная)\n"
    
    success_msg += f"Статус: ⏳ Ожидает\n"
    
    if assignee_username:
        success_msg += f"\n\n📨 Уведомление отправлено исполнителю"
    elif assignee_id is None:
        success_msg += f"\n\n📢 Уведомления отправлены всем пользователям"
    
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
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Отправляем уведомления исполнителю
        if assignee_telegram_id:
            try:
                if first_name or last_name:
                    creator_display = f"{first_name or ''} {last_name or ''}".strip() + f" (@{username})"
                else:
                    creator_display = f"@{username}"
                
                notification_text = f"""📋 <b>Вам назначена новая задача!</b>

<b>Задача #{task_id}</b>
<b>Название:</b> {title}
<b>Описание:</b> {description or 'Нет описания'}
<b>Приоритет:</b> {priority_text}
<b>Срок:</b> 📅 {due_datetime_str} ({TIMEZONE_ABBR})
<b>Создал:</b> {creator_display}
<b>Статус:</b> ⏳ Ожидает

Используйте /start для просмотра задачи."""
                
                task_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📂 Открыть задачу", callback_data=f"task_{task_id}")]
                ])
                
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
        
        # Уведомления для свободных задач
        if assignee_id is None:
            logger.info(f"📢 Task #{task_id} created without assignee, notifying all users")
            
            cur.execute("SELECT telegram_id, username FROM users WHERE role IN ('admin', 'employee')")
            all_users = cur.fetchall()
            
            priority_emoji = {
                'urgent': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '🟢'
            }.get(priority, '⚪')
            
            priority_text_notification = {
                'urgent': '🔴 Срочно',
                'high': '🟠 Высокий',
                'medium': '🟡 Средний',
                'low': '🟢 Низкий'
            }.get(priority, priority)
            
            if first_name or last_name:
                creator_display = f"{first_name or ''} {last_name or ''}".strip() + f" (@{username})"
            else:
                creator_display = f"@{username}"
            
            broadcast_message = f"""🆓 <b>Новая свободная задача!</b>

{priority_emoji} <b>#{task_id}:</b> {title}
📝 <b>Описание:</b> {description or 'Нет описания'}
<b>Приоритет:</b> {priority_text_notification}
📅 <b>Срок:</b> {due_datetime_str} ({TIMEZONE_ABBR})
👤 <b>Создал:</b> {creator_display}

⚡ Задача доступна для выполнения. Кто-то может взять её в работу!"""
            
            task_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📂 Открыть задачу", callback_data=f"task_{task_id}")]
            ])
            
            notification_count = 0
            telegram_id_str = str(callback_or_message.from_user.id) if is_message else str(callback_or_message.from_user.id)
            
            for user_data in all_users:
                if user_data['telegram_id'] == telegram_id_str:
                    continue
                
                try:
                    if is_message:
                        await callback_or_message.bot.send_message(
                            chat_id=user_data['telegram_id'],
                            text=broadcast_message,
                            parse_mode='HTML',
                            reply_markup=task_keyboard
                        )
                    else:
                        await callback_or_message.message.bot.send_message(
                            chat_id=user_data['telegram_id'],
                            text=broadcast_message,
                            parse_mode='HTML',
                            reply_markup=task_keyboard
                        )
                    notification_count += 1
                except Exception as e:
                    logger.warning(f"⚠️ Failed to send notification to {user_data['username']}: {e}")
            
            logger.info(f"📧 Sent {notification_count} notifications about new free task #{task_id}")
        
        logger.info(f"✅ Task creation complete: '{title}' by {username}")
    
    except Exception as e:
        logger.error(f"❌ Error sending notifications: {e}", exc_info=True)
    finally:
        cur.close()
        conn.close()
