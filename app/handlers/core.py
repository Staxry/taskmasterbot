"""
Core handlers module
Основные команды и меню бота
"""
from datetime import datetime, timedelta
from aiogram import F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.handlers import core_router
from app.database import get_db_connection
from app.services.users import get_or_create_user
from app.keyboards.main_menu import get_main_keyboard
from app.keyboards.task_keyboards import get_task_keyboard, get_priority_keyboard, get_due_date_keyboard, get_due_time_keyboard
from app.keyboards.user_keyboards import get_users_keyboard
from app.states import CreateTaskStates, AddUserStates, SearchTaskStates
from app.logging_config import get_logger

logger = get_logger(__name__)


@core_router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработка команды /start"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    last_name = message.from_user.last_name or ''
    
    logger.info(f"🎯 /start from {telegram_id} (@{username})")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    
    if not user:
        logger.warning(f"⛔ Access denied for {telegram_id} (@{username}) - not in whitelist")
        await message.answer(
            "❌ <b>Доступ запрещён</b>\n\n"
            "Ваш username не авторизован в системе.\n"
            "Обратитесь к администратору для получения доступа.\n\n"
            f"Ваш username: @{username or 'отсутствует'}",
            parse_mode='HTML'
        )
        return
    
    role_text = "👨‍💼 Администратор" if user['role'] == 'admin' else "👤 Сотрудник"
    
    logger.info(f"✅ User {username} authorized as {user['role']}")
    
    await message.answer(
        f"👋 Привет, {user['username']}!\n\n"
        f"Роль: <b>{role_text}</b>\n\n"
        f"Выберите действие:",
        parse_mode='HTML',
        reply_markup=get_main_keyboard(user['role'])
    )


@core_router.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    """Обработка кнопки Помощь"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"❓ Help requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] == 'admin':
        text = """📋 <b>Доступные команды (Администратор):</b>

🔹 <b>Мои задачи</b> - список ваших задач
🔹 <b>Все задачи</b> - все задачи в системе
🔹 <b>Создать задачу</b> - добавить новую задачу
🔹 <b>Добавить админа</b> - добавить администратора
🔹 <b>Добавить сотрудника</b> - добавить сотрудника
🔹 Нажмите на задачу для просмотра деталей
🔹 Используйте кнопки для изменения статуса"""
    else:
        text = """📋 <b>Доступные команды (Сотрудник):</b>

🔹 <b>Мои задачи</b> - список ваших задач
🔹 Нажмите на задачу для просмотра деталей
🔹 Используйте кнопки для изменения статуса

<b>Статусы:</b>
⏳ Ожидает | 🔄 В работе | ✅ Завершена | ❌ Отклонена"""
    
    await callback.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=get_main_keyboard(user['role'])
    )
    await callback.answer()


@core_router.callback_query(F.data == "add_admin")
async def callback_add_admin(callback: CallbackQuery, state: FSMContext):
    """Начать добавление администратора"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"➕ Add admin requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user or user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to add admin without permissions")
        await callback.answer("❌ Только администраторы могут добавлять пользователей", show_alert=True)
        return
    
    await state.update_data(target_role='admin')
    await state.set_state(AddUserStates.waiting_for_username)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    
    logger.debug(f"📝 Starting add admin flow for {username}")
    
    await callback.message.edit_text(
        "👨‍💼 <b>Добавление администратора</b>\n\n"
        "Введите <b>username</b> нового администратора (без @):\n\n"
        "Например: <code>ivan_petrov</code>",
        parse_mode='HTML',
        reply_markup=cancel_keyboard
    )
    await callback.answer()


@core_router.callback_query(F.data == "add_employee")
async def callback_add_employee(callback: CallbackQuery, state: FSMContext):
    """Начать добавление сотрудника"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"➕ Add employee requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user or user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to add employee without permissions")
        await callback.answer("❌ Только администраторы могут добавлять пользователей", show_alert=True)
        return
    
    await state.update_data(target_role='employee')
    await state.set_state(AddUserStates.waiting_for_username)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    
    logger.debug(f"📝 Starting add employee flow for {username}")
    
    await callback.message.edit_text(
        "👤 <b>Добавление сотрудника</b>\n\n"
        "Введите <b>username</b> нового сотрудника (без @):\n\n"
        "Например: <code>maria_ivanova</code>",
        parse_mode='HTML',
        reply_markup=cancel_keyboard
    )
    await callback.answer()


@core_router.message(AddUserStates.waiting_for_username)
async def process_add_user(message: Message, state: FSMContext):
    """Обработка username для добавления пользователя"""
    new_username = message.text.strip().replace('@', '')
    
    logger.info(f"📥 Processing add user: {new_username}")
    
    if not new_username:
        logger.warning(f"⚠️ Empty username provided")
        await message.answer("❌ Username не может быть пустым. Попробуйте ещё раз:")
        return
    
    data = await state.get_data()
    target_role = data.get('target_role', 'employee')
    
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    last_name = message.from_user.last_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        logger.error(f"❌ User {username} lost authorization during add user flow")
        await message.answer("❌ Доступ запрещён")
        await state.clear()
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        logger.debug(f"💾 Adding {new_username} as {target_role} to whitelist")
        
        cur.execute(
            """INSERT INTO allowed_users (username, role, added_by_id, created_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT (username) 
               DO UPDATE SET role = EXCLUDED.role, added_by_id = EXCLUDED.added_by_id""",
            (new_username, target_role, user['id'])
        )
        conn.commit()
        
        role_text = "👨‍💼 Администратор" if target_role == 'admin' else "👤 Сотрудник"
        
        logger.info(f"✅ {username} added {new_username} as {target_role}")
        
        await message.answer(
            f"✅ <b>Пользователь добавлен!</b>\n\n"
            f"Username: @{new_username}\n"
            f"Роль: {role_text}\n\n"
            f"Теперь пользователь @{new_username} может отправить /start боту для авторизации.",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user['role'])
        )
        
        await state.clear()
    
    except Exception as e:
        logger.error(f"❌ Error adding user {new_username}: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при добавлении пользователя: {str(e)}",
            reply_markup=get_main_keyboard(user['role'])
        )
        await state.clear()
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data == "my_tasks")
async def callback_my_tasks(callback: CallbackQuery):
    """Обработка кнопки Мои задачи (страница 1)"""
    await show_my_tasks_page(callback, page=1)


@core_router.callback_query(F.data.startswith("my_tasks_page_"))
async def callback_my_tasks_page(callback: CallbackQuery):
    """Навигация по страницам моих задач"""
    page = int(callback.data.split('_')[-1])
    await show_my_tasks_page(callback, page=page)


async def show_my_tasks_page(callback: CallbackQuery, page: int = 1):
    """Показать страницу моих задач с пагинацией"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"📋 My tasks page {page} requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Подсчёт общего количества
        if user['role'] == 'admin':
            cur.execute("SELECT COUNT(*) as count FROM tasks")
        else:
            cur.execute(
                "SELECT COUNT(*) as count FROM tasks WHERE assigned_to_id = ? OR assigned_to_id IS NULL",
                (user['id'],)
            )
        result = cur.fetchone()
        total_count = result["count"] if result else 0
        
        # Пагинация
        page_size = 10
        offset = (page - 1) * page_size
        total_pages = (total_count + page_size - 1) // page_size
        
        # Получение задач для страницы с именем исполнителя
        if user['role'] == 'admin':
            logger.debug(f"📊 Fetching tasks for admin {username}, page {page}")
            cur.execute(
                """SELECT t.id, t.title, t.status, t.priority, t.due_date, t.assigned_to_id, u.username as assignee_name
                   FROM tasks t
                   LEFT JOIN users u ON t.assigned_to_id = u.id
                   ORDER BY t.created_at DESC
                   LIMIT ? OFFSET ?""",
                (page_size, offset)
            )
        else:
            logger.debug(f"📊 Fetching tasks for employee {username}, page {page}")
            cur.execute(
                """SELECT t.id, t.title, t.status, t.priority, t.due_date, t.assigned_to_id, u.username as assignee_name
                   FROM tasks t
                   LEFT JOIN users u ON t.assigned_to_id = u.id
                   WHERE t.assigned_to_id = ? OR t.assigned_to_id IS NULL
                   ORDER BY t.created_at DESC
                   LIMIT ? OFFSET ?""",
                (user['id'], page_size, offset)
            )
        tasks = cur.fetchall()
        
        logger.info(f"📊 Found {len(tasks)} tasks on page {page}/{total_pages} for {username}")
        
        if total_count == 0:
            try:
                await callback.message.edit_text(
                    "📋 У вас пока нет задач.",
                    reply_markup=get_main_keyboard(user['role'])
                )
            except Exception:
                await callback.message.delete()
                await callback.message.answer(
                    "📋 У вас пока нет задач.",
                    reply_markup=get_main_keyboard(user['role'])
                )
            await callback.answer()
            return
        
        buttons = []
        
        status_emoji = {
            'pending': '⏳',
            'in_progress': '🔄',
            'partially_completed': '🔶',
            'completed': '✅',
            'rejected': '❌'
        }
        
        priority_emoji = {
            'urgent': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢'
        }
        
        # Кнопки задач
        for task in tasks:
            task_id = task['id']
            title = task['title']
            status = task['status']
            priority = task['priority']
            assigned_to_id = task.get('assigned_to_id')
            assignee_name = task.get('assignee_name')
            emoji_status = status_emoji.get(status, '📌')
            emoji_priority = priority_emoji.get(priority, '📌')
            
            if assigned_to_id is None:
                button_text = f"🆓 {emoji_priority} {title[:20]}"
            else:
                button_text = f"{emoji_status} {emoji_priority} {title[:25]}"
            
            buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"task_{task_id}"
                )
            ])
        
        # Кнопки пагинации
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"my_tasks_page_{page-1}"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="▶️ Вперёд", callback_data=f"my_tasks_page_{page+1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        text = f"📋 <b>Выберите задачу:</b>\n\nСтраница {page}/{total_pages} (всего {total_count})"
        
        try:
            await callback.message.edit_text(
                text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer(
                text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        await callback.answer()
    
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data == "all_tasks")
async def callback_all_tasks(callback: CallbackQuery):
    """Обработка кнопки Все задачи (страница 1)"""
    await show_all_tasks_page(callback, page=1)


@core_router.callback_query(F.data.startswith("all_tasks_page_"))
async def callback_all_tasks_page(callback: CallbackQuery):
    """Навигация по страницам всех задач"""
    page = int(callback.data.split('_')[-1])
    await show_all_tasks_page(callback, page=page)


async def show_all_tasks_page(callback: CallbackQuery, page: int = 1):
    """Показать страницу всех задач с пагинацией"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"📊 All tasks page {page} requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to view all tasks without admin rights")
        await callback.answer("❌ Только администраторы могут просматривать все задачи.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Подсчёт общего количества
        cur.execute("SELECT COUNT(*) as count FROM tasks")
        result = cur.fetchone()
        total_count = result["count"] if result else 0
        
        # Пагинация
        page_size = 10
        offset = (page - 1) * page_size
        total_pages = (total_count + page_size - 1) // page_size
        
        logger.debug(f"📊 Fetching all tasks for admin {username}, page {page}/{total_pages}")
        
        cur.execute(
            """SELECT t.id, t.title, t.status, t.priority, u.username, u.first_name, u.last_name
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               ORDER BY t.created_at DESC
               LIMIT ? OFFSET ?""",
            (page_size, offset)
        )
        tasks = cur.fetchall()
        
        logger.info(f"📊 Found {len(tasks)} tasks on page {page}/{total_pages}")
        
        if total_count == 0:
            await callback.message.edit_text(
                "📋 В системе пока нет задач.",
                reply_markup=get_main_keyboard(user['role'])
            )
            await callback.answer()
            return
        
        buttons = []
        
        status_emoji = {
            'pending': '⏳',
            'in_progress': '🔄',
            'partially_completed': '🔶',
            'completed': '✅',
            'rejected': '❌'
        }
        
        priority_emoji = {
            'urgent': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢'
        }
        
        # Кнопки задач
        for task in tasks:
            task_id = task['id']
            title = task['title']
            status = task['status']
            priority = task['priority']
            assigned_username = task.get('username')
            assigned_first_name = task.get('first_name')
            assigned_last_name = task.get('last_name')
            emoji_status = status_emoji.get(status, '📌')
            emoji_priority = priority_emoji.get(priority, '📌')
            
            if assigned_username:
                # Полное имя в формате "Имя Фамилия (@username)"
                if assigned_first_name or assigned_last_name:
                    user_display = f"{assigned_first_name or ''} {assigned_last_name or ''}".strip() + f" (@{assigned_username})"
                else:
                    user_display = f"@{assigned_username}"
                # Обрезаем только название задачи, НЕ имя пользователя
                title_short = title[:8]
                button_text = f"{emoji_status} {emoji_priority} {title_short} - {user_display}"
            else:
                button_text = f"{emoji_status} {emoji_priority} {title[:20]}"
            buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"task_{task_id}"
                )
            ])
        
        # Кнопки пагинации
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"all_tasks_page_{page-1}"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="▶️ Вперёд", callback_data=f"all_tasks_page_{page+1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        text = f"📋 <b>Все задачи в системе:</b>\n\nСтраница {page}/{total_pages} (всего {total_count})"
        
        await callback.message.edit_text(
            text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
        await callback.answer()
    
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data.startswith("task_") & ~F.data.in_({"task_photo_yes", "task_photo_no"}))
async def callback_task_details(callback: CallbackQuery):
    """Показать детали задачи"""
    task_id = int(callback.data.split('_')[1])
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"📂 Task #{task_id} details requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """SELECT t.id, t.title, t.description, t.status, t.priority, t.due_date, 
                      u.username, u.first_name, u.last_name, t.created_at, t.assigned_to_id, 
                      t.completion_comment, t.photo_file_id, t.task_photo_file_id
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               WHERE t.id = ?""",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            logger.warning(f"⚠️ Task #{task_id} not found")
            await callback.answer("❌ Задача не найдена.", show_alert=True)
            return
        
        tid = task['id']
        title = task['title']
        description = task['description']
        status = task['status']
        priority = task['priority']
        due_date = task['due_date']
        assigned_username = task.get('username')
        assigned_first_name = task.get('first_name')
        assigned_last_name = task.get('last_name')
        created_at = task['created_at']
        assigned_to_id = task['assigned_to_id']
        completion_comment = task.get('completion_comment')
        photo_file_id = task.get('photo_file_id')
        task_photo_file_id = task.get('task_photo_file_id')
        
        logger.debug(f"📊 Task #{tid}: status={status}, assigned_to={assigned_username}, has_photo={bool(photo_file_id)}, has_task_photo={bool(task_photo_file_id)}")
        
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
        
        # Форматируем имя назначенного пользователя
        if assigned_username:
            if assigned_first_name or assigned_last_name:
                assignee_display = f"{assigned_first_name or ''} {assigned_last_name or ''}".strip() + f" (@{assigned_username})"
            else:
                assignee_display = f"@{assigned_username}"
        else:
            assignee_display = "🆓 Свободна (можно взять)"
        
        text = f"""📋 <b>Задача #{tid}</b>

<b>Название:</b> {title}
<b>Описание:</b> {description or 'Нет описания'}
<b>Статус:</b> {status_text}
<b>Приоритет:</b> {priority_text}
<b>Срок:</b> {due_date}
<b>Назначена:</b> {assignee_display}
<b>Создана:</b> {created_at}
"""
        
        if task_photo_file_id:
            text += "<b>📸 Фото:</b> Есть (нажмите кнопку ниже)\n"
        
        if status in ['completed', 'partially_completed'] and completion_comment:
            text += f"\n\n💬 <b>Комментарий:</b>\n{completion_comment}"
        
        if assigned_to_id is None:
            text += "\n\n💡 Эта задача свободна - любой сотрудник может взять её в работу!"
        elif status not in ['completed', 'partially_completed']:
            text += "\n\nВыберите новый статус:"
        
        has_task_photo = bool(task_photo_file_id)
        
        if status in ['completed', 'partially_completed'] and photo_file_id:
            logger.debug(f"📸 Sending task #{tid} with completion photo")
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=photo_file_id,
                caption=text,
                parse_mode='HTML',
                reply_markup=get_task_keyboard(task_id, status, assigned_to_id, user['id'], user['role'] == 'admin', has_task_photo)
            )
        else:
            try:
                await callback.message.edit_text(
                    text,
                    parse_mode='HTML',
                    reply_markup=get_task_keyboard(task_id, status, assigned_to_id, user['id'], user['role'] == 'admin', has_task_photo)
                )
            except Exception:
                logger.debug(f"⚠️ Could not edit message, deleting and resending")
                await callback.message.delete()
                await callback.message.answer(
                    text,
                    parse_mode='HTML',
                    reply_markup=get_task_keyboard(task_id, status, assigned_to_id, user['id'], user['role'] == 'admin', has_task_photo)
                )
        
        await callback.answer()
    
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data.startswith("view_task_photo_"))
async def callback_view_task_photo(callback: CallbackQuery):
    """Просмотреть фото задачи"""
    task_id = int(callback.data.split('_')[-1])
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"📸 Task photo view requested for task #{task_id} by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """SELECT t.id, t.title, t.task_photo_file_id, t.status, t.assigned_to_id
               FROM tasks t
               WHERE t.id = ?""",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            logger.warning(f"⚠️ Task #{task_id} not found for photo view")
            await callback.answer("❌ Задача не найдена.", show_alert=True)
            return
        
        task_photo_file_id = task.get('task_photo_file_id')
        title = task['title']
        status = task['status']
        assigned_to_id = task['assigned_to_id']
        
        if not task_photo_file_id:
            logger.warning(f"⚠️ Task #{task_id} has no photo")
            await callback.answer("❌ У этой задачи нет прикреплённого фото.", show_alert=True)
            return
        
        logger.info(f"📸 Sending task photo for task #{task_id}")
        
        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К задаче", callback_data=f"task_{task_id}")]
        ])
        
        await callback.message.answer_photo(
            photo=task_photo_file_id,
            caption=f"📸 <b>Фото к задаче #{task_id}</b>\n\n<b>Название:</b> {title}",
            parse_mode='HTML',
            reply_markup=back_keyboard
        )
        
        await callback.answer()
        logger.info(f"✅ Task photo sent for task #{task_id}")
    
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data.startswith("take_"))
async def callback_take_task(callback: CallbackQuery):
    """Взять задачу в работу"""
    task_id = int(callback.data.split('_')[1])
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"✋ Take task #{task_id} requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] == 'admin':
        logger.warning(f"⛔ Admin {username} tried to take task #{task_id}")
        await callback.answer("❌ Админы не могут брать задачи в работу. Используйте назначение через создание задачи.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """SELECT id, title, description, priority, due_date, assigned_to_id, created_by_id, task_photo_file_id 
               FROM tasks WHERE id = ?""",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            logger.warning(f"⚠️ Task #{task_id} not found")
            await callback.answer("❌ Задача не найдена.", show_alert=True)
            return
        
        task_id_db = task['id']
        title = task['title']
        description = task['description']
        priority = task['priority']
        due_date = task['due_date']
        assigned_to_id = task['assigned_to_id']
        created_by_id = task['created_by_id']
        task_photo_file_id = task['task_photo_file_id']
        
        logger.info(f"📋 Task #{task_id_db} info: assigned_to={assigned_to_id}, has_photo={bool(task_photo_file_id)}")
        
        if assigned_to_id is not None:
            logger.warning(f"⚠️ Task #{task_id} already assigned to user {assigned_to_id}")
            await callback.answer("❌ Эта задача уже назначена другому сотруднику.", show_alert=True)
            return
        
        cur.execute(
            "UPDATE tasks SET assigned_to_id = ?, status = 'in_progress', updated_at = datetime('now') WHERE id = ?",
            (user['id'], task_id)
        )
        conn.commit()
        
        logger.info(f"✅ Task #{task_id} assigned to {username} (id={user['id']})")
        
        await callback.answer("✅ Задача взята в работу!", show_alert=True)
        
        if created_by_id:
            cur.execute(
                "SELECT telegram_id, username, first_name, last_name FROM users WHERE id = ?",
                (created_by_id,)
            )
            creator = cur.fetchone()
            
            if creator:
                creator_telegram_id = creator['telegram_id']
                creator_username = creator['username']
                
                # Форматируем имя исполнителя
                if first_name or last_name:
                    executor_display = f"{first_name or ''} {last_name or ''}".strip() + f" (@{username})"
                else:
                    executor_display = f"@{username}"
                
                priority_text = {
                    'urgent': '🔴 Срочно',
                    'high': '🟠 Высокий',
                    'medium': '🟡 Средний',
                    'low': '🟢 Низкий'
                }.get(priority, priority)
                
                notification_text = f"""✋ <b>Задачу взяли в работу!</b>

<b>Задача #{task_id}</b>
<b>Название:</b> {title}
<b>Описание:</b> {description or 'Нет описания'}
<b>Приоритет:</b> {priority_text}
<b>Срок:</b> 📅 {due_date}
<b>Исполнитель:</b> {executor_display}
<b>Статус:</b> 🔄 В работе

Нажмите кнопку ниже для просмотра задачи."""
                
                task_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📂 Открыть задачу", callback_data=f"task_{task_id}")]
                ])
                
                try:
                    if task_photo_file_id:
                        logger.info(f"📸 Sending notification WITH photo to admin {creator_username}")
                        await callback.message.bot.send_photo(
                            chat_id=creator_telegram_id,
                            photo=task_photo_file_id,
                            caption=notification_text,
                            parse_mode='HTML',
                            reply_markup=task_keyboard
                        )
                    else:
                        logger.info(f"📝 Sending notification WITHOUT photo to admin {creator_username}")
                        await callback.message.bot.send_message(
                            chat_id=creator_telegram_id,
                            text=notification_text,
                            parse_mode='HTML',
                            reply_markup=task_keyboard
                        )
                    logger.info(f"✅ Task assignment notification sent to {creator_username}")
                except Exception as notif_error:
                    logger.warning(f"⚠️ Could not send notification: {notif_error}")
        
        await callback.message.edit_text(
            f"✅ <b>Задача взята в работу!</b>\n\n"
            f"Задача: {title}\n"
            f"Теперь она назначена на вас.\n\n"
            f"Используйте 📋 Мои задачи для просмотра.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Мои задачи", callback_data="my_tasks")],
                [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
            ])
        )
        
        logger.info(f"✅ {username} took task #{task_id} in progress")
    
    except Exception as e:
        logger.error(f"❌ Error taking task #{task_id}: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data == "create_task")
async def callback_create_task(callback: CallbackQuery, state: FSMContext):
    """Начать создание задачи"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"➕ Create task requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to create task without admin rights")
        await callback.answer("❌ Только администраторы могут создавать задачи.", show_alert=True)
        return
    
    await state.set_state(CreateTaskStates.waiting_for_title)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    
    logger.debug(f"📝 Starting create task flow for {username}")
    
    await callback.message.edit_text(
        "➕ <b>Создание задачи</b>\n\n"
        "Введите <b>название задачи</b>:",
        parse_mode='HTML',
        reply_markup=cancel_keyboard
    )
    await callback.answer()


@core_router.message(CreateTaskStates.waiting_for_title)
async def process_task_title(message: Message, state: FSMContext):
    """Получить название задачи"""
    logger.info(f"📝 Task title received: {message.text[:30]}...")
    
    await state.update_data(title=message.text)
    await state.set_state(CreateTaskStates.waiting_for_description)
    
    skip_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_description")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    
    await message.answer(
        "Введите <b>описание задачи</b> (или нажмите Пропустить):",
        parse_mode='HTML',
        reply_markup=skip_keyboard
    )


@core_router.callback_query(F.data == "skip_description", CreateTaskStates.waiting_for_description)
async def skip_description(callback: CallbackQuery, state: FSMContext):
    """Пропустить описание"""
    logger.debug("⏭ Task description skipped")
    
    await state.update_data(description="")
    await state.set_state(CreateTaskStates.waiting_for_priority)
    
    await callback.message.edit_text(
        "Выберите <b>приоритет задачи</b>:",
        parse_mode='HTML',
        reply_markup=get_priority_keyboard()
    )
    await callback.answer()


@core_router.message(CreateTaskStates.waiting_for_description)
async def process_task_description(message: Message, state: FSMContext):
    """Получить описание задачи"""
    logger.info(f"📝 Task description received: {message.text[:30]}...")
    
    await state.update_data(description=message.text)
    await state.set_state(CreateTaskStates.waiting_for_priority)
    
    await message.answer(
        "Выберите <b>приоритет задачи</b>:",
        parse_mode='HTML',
        reply_markup=get_priority_keyboard()
    )


@core_router.callback_query(F.data.startswith("priority_"))
async def process_priority(callback: CallbackQuery, state: FSMContext):
    """Обработать выбор приоритета и перейти к выбору срока"""
    priority = callback.data.split('_')[1]
    
    logger.info(f"📊 Task priority selected: {priority}")
    
    await state.update_data(priority=priority)
    await state.set_state(CreateTaskStates.waiting_for_due_date)
    
    await callback.message.edit_text(
        "📅 <b>Выберите срок выполнения задачи:</b>",
        parse_mode='HTML',
        reply_markup=get_due_date_keyboard()
    )
    await callback.answer()


@core_router.callback_query(F.data.startswith("due_"))
async def process_due_date(callback: CallbackQuery, state: FSMContext):
    """Обработать выбор срока и перейти к выбору времени"""
    due_date = callback.data.split('_', 1)[1]
    
    if due_date == "manual":
        logger.debug("✍️ Manual due date input requested")
        await state.set_state(CreateTaskStates.waiting_for_manual_due_date)
        await callback.message.edit_text(
            "✍️ <b>Введите дату вручную</b>\n\n"
            "Формат: <code>ГГГГ-ММ-ДД</code> (например: 2024-12-31)\n"
            "Или: <code>ДД.ММ.ГГГГ</code> (например: 31.12.2024)",
            parse_mode='HTML'
        )
        await callback.answer()
        return
    
    logger.info(f"📅 Task due date selected: {due_date}")
    
    await state.update_data(due_date=due_date)
    await state.set_state(CreateTaskStates.waiting_for_due_time)
    
    await callback.message.edit_text(
        f"⏰ <b>Выберите время завершения задачи</b>\n\n"
        f"Дата: <code>{due_date}</code>",
        parse_mode='HTML',
        reply_markup=get_due_time_keyboard()
    )
    await callback.answer()


@core_router.message(CreateTaskStates.waiting_for_manual_due_date)
async def process_manual_due_date(message: Message, state: FSMContext):
    """Обработать ручной ввод даты"""
    date_text = message.text.strip()
    
    logger.info(f"📅 Manual due date input: {date_text}")
    
    due_date = None
    try:
        if '-' in date_text:
            parsed_date = datetime.strptime(date_text, '%Y-%m-%d')
            due_date = parsed_date.strftime('%Y-%m-%d')
        elif '.' in date_text:
            parsed_date = datetime.strptime(date_text, '%d.%m.%Y')
            due_date = parsed_date.strftime('%Y-%m-%d')
        else:
            raise ValueError("Неизвестный формат")
    except ValueError as e:
        logger.warning(f"⚠️ Invalid date format: {date_text} - {e}")
        await message.answer(
            "❌ <b>Неверный формат даты!</b>\n\n"
            "Используйте один из форматов:\n"
            "• <code>ГГГГ-ММ-ДД</code> (например: 2024-12-31)\n"
            "• <code>ДД.ММ.ГГГГ</code> (например: 31.12.2024)\n\n"
            "Попробуйте ещё раз:",
            parse_mode='HTML'
        )
        return
    
    logger.info(f"✅ Manual due date parsed: {due_date}")
    
    await state.update_data(due_date=due_date)
    await state.set_state(CreateTaskStates.waiting_for_due_time)
    
    await message.answer(
        f"⏰ <b>Выберите время завершения задачи</b>\n\n"
        f"Дата: <code>{due_date}</code>",
        parse_mode='HTML',
        reply_markup=get_due_time_keyboard()
    )


@core_router.callback_query(F.data.startswith("time_"))
async def process_due_time(callback: CallbackQuery, state: FSMContext):
    """Обработать выбор времени и перейти к выбору исполнителя"""
    time_value = callback.data.split('_', 1)[1]
    
    if time_value == "manual":
        logger.debug("✍️ Manual time input requested")
        await state.set_state(CreateTaskStates.waiting_for_manual_due_time)
        await callback.message.edit_text(
            "✍️ <b>Введите время вручную</b>\n\n"
            "Формат: <code>ЧЧ:ММ</code> (например: 15:30 или 09:00)\n\n"
            "Время указывается в часовом поясе <b>Europe/Moscow (UTC+3)</b>",
            parse_mode='HTML'
        )
        await callback.answer()
        return
    
    logger.info(f"⏰ Task due time selected: {time_value}")
    
    await state.update_data(due_time=time_value)
    await state.set_state(CreateTaskStates.waiting_for_assignee)
    
    data = await state.get_data()
    due_date = data.get('due_date', 'не указана')
    
    await callback.message.edit_text(
        f"👥 <b>Выберите исполнителя задачи:</b>\n\n"
        f"📅 Срок: <code>{due_date} {time_value}</code>",
        parse_mode='HTML',
        reply_markup=get_users_keyboard()
    )
    await callback.answer()


@core_router.message(CreateTaskStates.waiting_for_manual_due_time)
async def process_manual_due_time(message: Message, state: FSMContext):
    """Обработать ручной ввод времени"""
    time_text = message.text.strip()
    
    logger.info(f"⏰ Manual due time input: {time_text}")
    
    try:
        parsed_time = datetime.strptime(time_text, '%H:%M')
        due_time = parsed_time.strftime('%H:%M')
    except ValueError as e:
        logger.warning(f"⚠️ Invalid time format: {time_text} - {e}")
        await message.answer(
            "❌ <b>Неверный формат времени!</b>\n\n"
            "Используйте формат <code>ЧЧ:ММ</code>\n"
            "Примеры: 15:30, 09:00, 23:59\n\n"
            "Попробуйте ещё раз:",
            parse_mode='HTML'
        )
        return
    
    logger.info(f"✅ Manual due time parsed: {due_time}")
    
    await state.update_data(due_time=due_time)
    await state.set_state(CreateTaskStates.waiting_for_assignee)
    
    data = await state.get_data()
    due_date = data.get('due_date', 'не указана')
    
    await message.answer(
        f"👥 <b>Выберите исполнителя задачи:</b>\n\n"
        f"📅 Срок: <code>{due_date} {due_time}</code>",
        parse_mode='HTML',
        reply_markup=get_users_keyboard()
    )


@core_router.callback_query(F.data.startswith("assignee_"))
async def process_assignee(callback: CallbackQuery, state: FSMContext):
    """Выбрать исполнителя и спросить про фото"""
    assignee_str = callback.data.split('_')[1]
    
    if assignee_str == "none":
        assignee_id = None
        logger.info("👤 No assignee selected (free task)")
    else:
        assignee_id = int(assignee_str)
        logger.info(f"👤 Assignee selected: user_id={assignee_id}")
    
    await state.update_data(assignee_id=assignee_id)
    await state.set_state(CreateTaskStates.asking_for_task_photo)
    
    photo_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, добавить фото", callback_data="task_photo_yes"),
            InlineKeyboardButton(text="❌ Нет, без фото", callback_data="task_photo_no")
        ]
    ])
    
    await callback.message.edit_text(
        "📸 <b>Добавить фото к задаче?</b>\n\n"
        "Фото поможет лучше объяснить задачу исполнителю.",
        parse_mode='HTML',
        reply_markup=photo_keyboard
    )
    await callback.answer()


@core_router.callback_query(F.data == "delete_task_menu")
async def callback_delete_task_menu(callback: CallbackQuery):
    """Показать список незавершённых задач для удаления"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"🗑️ Delete task menu requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to delete tasks without admin rights")
        await callback.answer("❌ Только администраторы могут удалять задачи.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        logger.debug("📊 Fetching uncompleted tasks for deletion")
        
        cur.execute(
            """SELECT t.id, t.title, t.status, t.priority, u.username, u.first_name, u.last_name
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               WHERE t.status != 'completed'
               ORDER BY t.created_at DESC
               LIMIT 20"""
        )
        tasks = cur.fetchall()
        
        logger.info(f"📊 Found {len(tasks)} uncompleted tasks")
        
        if not tasks:
            await callback.message.edit_text(
                "📋 Нет незавершённых задач для удаления.",
                reply_markup=get_main_keyboard(user['role'])
            )
            await callback.answer()
            return
        
        buttons = []
        
        status_emoji = {
            'pending': '⏳',
            'in_progress': '🔄',
            'rejected': '❌'
        }
        
        priority_emoji = {
            'urgent': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢'
        }
        
        for task in tasks:
            task_id = task['id']
            title = task['title']
            status = task['status']
            priority = task['priority']
            assigned_username = task.get('username')
            assigned_first_name = task.get('first_name')
            assigned_last_name = task.get('last_name')
            emoji_status = status_emoji.get(status, '📌')
            emoji_priority = priority_emoji.get(priority, '📌')
            
            if assigned_username:
                # Полное имя в формате "Имя Фамилия (@username)"
                if assigned_first_name or assigned_last_name:
                    user_display = f"{assigned_first_name or ''} {assigned_last_name or ''}".strip() + f" (@{assigned_username})"
                else:
                    user_display = f"@{assigned_username}"
                # Обрезаем только название задачи, НЕ имя пользователя
                title_short = title[:8]
                button_text = f"{emoji_status} {emoji_priority} {title_short} - {user_display}"
            else:
                button_text = f"{emoji_status} {emoji_priority} {title[:25]}"
            buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"delete_confirm_{task_id}"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(
            f"🗑️ <b>Выберите задачу для удаления:</b>\n\n"
            f"Показаны незавершённые задачи ({len(tasks)})\n"
            f"⚠️ Внимание: удаление необратимо!",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        await callback.answer()
    
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data.startswith("delete_confirm_"))
async def callback_delete_confirm(callback: CallbackQuery):
    """Удалить задачу после подтверждения"""
    task_id = int(callback.data.split('_')[2])
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"🗑️ Delete task #{task_id} confirmation by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to delete task without admin rights")
        await callback.answer("❌ Только администраторы могут удалять задачи.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT title FROM tasks WHERE id = ?",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            logger.warning(f"⚠️ Task #{task_id} not found for deletion")
            await callback.answer("❌ Задача не найдена.", show_alert=True)
            return
        
        task_title = task['title']
        
        cur.execute(
            "DELETE FROM tasks WHERE id = ?",
            (task_id,)
        )
        conn.commit()
        
        logger.info(f"✅ Task #{task_id} ({task_title}) deleted by {username}")
        
        await callback.message.edit_text(
            f"✅ <b>Задача удалена!</b>\n\n"
            f"ID: {task_id}\n"
            f"Название: {task_title}\n\n"
            f"Задача полностью удалена из системы.",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user['role'])
        )
        await callback.answer("✅ Задача удалена", show_alert=True)
    
    except Exception as e:
        logger.error(f"❌ Error deleting task #{task_id}: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при удалении задачи", show_alert=True)
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data == "remove_admin")
async def callback_remove_admin(callback: CallbackQuery):
    """Показать список админов для удаления"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"🗑️ Remove admin requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to remove admin without permissions")
        await callback.answer("❌ Только администраторы могут удалять пользователей.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT id, username FROM users WHERE role = 'admin' AND telegram_id != ? ORDER BY username",
            (telegram_id,)
        )
        admins = cur.fetchall()
        
        logger.info(f"📊 Found {len(admins)} other admins")
        
        if not admins:
            await callback.message.edit_text(
                "👨‍💼 <b>Нет других администраторов для удаления</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
                ])
            )
            await callback.answer()
            return
        
        buttons = []
        for admin in admins:
            admin_id = admin['id']
            admin_username = admin['username']
            buttons.append([
                InlineKeyboardButton(
                    text=f"🗑️ @{admin_username}",
                    callback_data=f"confirmremove_{admin_id}_admin"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")])
        
        await callback.message.edit_text(
            "👨‍💼 <b>Выберите администратора для удаления:</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        await callback.answer()
    
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data == "remove_employee")
async def callback_remove_employee(callback: CallbackQuery):
    """Показать список сотрудников для удаления"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"🗑️ Remove employee requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to remove employee without permissions")
        await callback.answer("❌ Только администраторы могут удалять пользователей.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT id, username FROM users ORDER BY username"
        )
        employees = cur.fetchall()
        
        logger.info(f"📊 Found {len(employees)} users")
        
        if not employees:
            await callback.message.edit_text(
                "👤 <b>Нет сотрудников для удаления</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
                ])
            )
            await callback.answer()
            return
        
        buttons = []
        for emp in employees:
            buttons.append([
                InlineKeyboardButton(
                    text=f"🗑️ @{emp['username']}",
                    callback_data=f"confirmremove_{emp['id']}_employee"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")])
        
        await callback.message.edit_text(
            "👤 <b>Выберите сотрудника для удаления:</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        await callback.answer()
    
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data.startswith("confirmremove_"))
async def callback_confirm_remove_user(callback: CallbackQuery):
    """Подтверждение удаления пользователя"""
    parts = callback.data.split('_')
    user_id_to_remove = int(parts[1])
    user_type = parts[2]
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"🗑️ Confirm remove user {user_id_to_remove} ({user_type}) by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to remove user without permissions")
        await callback.answer("❌ Только администраторы могут удалять пользователей.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT username, role FROM users WHERE id = ?",
            (user_id_to_remove,)
        )
        user_to_remove = cur.fetchone()
        
        if not user_to_remove:
            logger.warning(f"⚠️ User {user_id_to_remove} not found for removal")
            await callback.answer("❌ Пользователь не найден.", show_alert=True)
            return
        
        username_to_remove = user_to_remove['username']
        role_to_remove = user_to_remove['role']
        
        logger.debug(f"🗑️ Removing user: {username_to_remove} ({role_to_remove})")
        
        cur.execute("DELETE FROM users WHERE id = ?", (user_id_to_remove,))
        cur.execute("DELETE FROM allowed_users WHERE username = ?", (username_to_remove,))
        cur.execute("UPDATE tasks SET assigned_to_id = NULL WHERE assigned_to_id = ?", (user_id_to_remove,))
        
        conn.commit()
        
        role_text = "👨‍💼 Администратор" if role_to_remove == 'admin' else "👤 Сотрудник"
        
        logger.info(f"✅ Admin {username} removed user {username_to_remove} ({role_to_remove})")
        
        await callback.message.edit_text(
            f"✅ <b>Пользователь удалён!</b>\n\n"
            f"Username: @{username_to_remove}\n"
            f"Роль: {role_text}\n\n"
            f"Задачи, которые были назначены на этого пользователя, теперь свободны.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
            ])
        )
        await callback.answer()
    
    except Exception as e:
        logger.error(f"❌ Error removing user {user_id_to_remove}: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка при удалении: {str(e)}", show_alert=True)
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data == "dashboard")
async def callback_dashboard(callback: CallbackQuery):
    """Показать дашборд со статистикой"""
    from app.services.statistics import get_dashboard_statistics
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"📈 Dashboard requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user or user['role'] != 'admin':
        await callback.answer("❌ Только администраторы могут просматривать статистику", show_alert=True)
        return
    
    stats = get_dashboard_statistics(user['role'])
    
    if not stats:
        await callback.answer("❌ Не удалось получить статистику", show_alert=True)
        return
    
    # Форматирование текста статистики
    text = "📈 <b>Дашборд статистики</b>\n\n"
    
    text += "📊 <b>Общая информация:</b>\n"
    text += f"▫️ Всего задач: <b>{stats['total_tasks']}</b>\n"
    text += f"▫️ Активных: <b>{stats['active_tasks']}</b>\n"
    text += f"▫️ Завершённых: <b>{stats['by_status']['completed']}</b>\n"
    text += f"▫️ Просрочено: <b>{stats['overdue_tasks']}</b> ⚠️\n\n"
    
    text += "📋 <b>По статусам:</b>\n"
    text += f"⏳ Ожидает: {stats['by_status']['pending']}\n"
    text += f"🔄 В работе: {stats['by_status']['in_progress']}\n"
    text += f"🔶 Частично: {stats['by_status']['partially_completed']}\n"
    text += f"✅ Завершено: {stats['by_status']['completed']}\n"
    text += f"❌ Отклонено: {stats['by_status']['rejected']}\n\n"
    
    if stats.get('by_priority'):
        text += "🎯 <b>По приоритетам (активные):</b>\n"
        priority_emoji = {'urgent': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}
        for priority, count in stats['by_priority'].items():
            emoji = priority_emoji.get(priority, '📌')
            text += f"{emoji} {priority.capitalize()}: {count}\n"
        text += "\n"
    
    text += f"📅 Создано сегодня: {stats['today_created']}\n"
    text += f"✅ Завершено за неделю: {stats['completed_last_week']}\n\n"
    
    if stats.get('top_performers'):
        text += "🏆 <b>Топ исполнителей:</b>\n"
        for i, performer in enumerate(stats['top_performers'][:3], 1):
            medals = {1: '🥇', 2: '🥈', 3: '🥉'}
            medal = medals.get(i, '🏅')
            
            username = performer['username']
            first_name = performer.get('first_name')
            last_name = performer.get('last_name')
            count = performer['task_count']
            
            # Форматируем имя исполнителя
            if first_name or last_name:
                user_display = f"{first_name or ''} {last_name or ''}".strip() + f" (@{username})"
            else:
                user_display = f"@{username}"
            
            text += f"{medal} {user_display}: {count} задач\n"
    
    # Кнопки для экспорта
    buttons = [
        [InlineKeyboardButton(text="📊 Полный отчёт Excel", callback_data="export_full")],
        [InlineKeyboardButton(text="📈 Отчёт по статусам", callback_data="export_status")],
        [InlineKeyboardButton(text="👥 Отчёт по исполнителям", callback_data="export_users")],
        [InlineKeyboardButton(text="🔄 Обновить данные", callback_data="dashboard")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    try:
        await callback.message.edit_text(
            text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer(
            text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    
    await callback.answer()


@core_router.callback_query(F.data.startswith("export_"))
async def callback_export_report(callback: CallbackQuery):
    """Генерация и отправка Excel отчёта"""
    from app.services.statistics import generate_excel_report
    from aiogram.types import BufferedInputFile
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    report_type = callback.data.split('_')[1]  # full, status, users
    
    logger.info(f"📊 Excel export requested by {username}: {report_type}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user or user['role'] != 'admin':
        await callback.answer("❌ Только администраторы могут экспортировать отчёты", show_alert=True)
        return
    
    await callback.answer("📊 Генерирую отчёт... Пожалуйста, подождите.", show_alert=False)
    
    try:
        # Генерация отчёта
        logger.info(f"🔄 Starting report generation: {report_type}")
        excel_file = generate_excel_report(report_type)
        
        # Определение имени файла
        report_names = {
            'full': 'Полный_отчёт',
            'status': 'Отчёт_по_статусам',
            'users': 'Отчёт_по_исполнителям'
        }
        filename = f"{report_names.get(report_type, 'Отчёт')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        # Отправка файла
        document = BufferedInputFile(excel_file.read(), filename=filename)
        
        await callback.message.answer_document(
            document=document,
            caption=f"📊 <b>Excel отчёт готов!</b>\n\n"
                    f"Тип: {report_names.get(report_type, 'Отчёт')}\n"
                    f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            parse_mode='HTML'
        )
        
        logger.info(f"✅ Excel report sent successfully to {username}")
        
    except Exception as e:
        logger.error(f"❌ Error generating/sending Excel report: {e}", exc_info=True)
        await callback.message.answer(
            "❌ Произошла ошибка при генерации отчёта. Попробуйте позже.",
            reply_markup=get_main_keyboard(user['role'])
        )


@core_router.callback_query(F.data == "search_tasks")
async def callback_search_tasks(callback: CallbackQuery, state: FSMContext):
    """Начать поиск задач"""
    from app.states import SearchTaskStates
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"🔍 Search tasks requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    await state.set_state(SearchTaskStates.waiting_for_query)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    
    try:
        await callback.message.edit_text(
            "🔍 <b>Поиск задач</b>\n\n"
            "Введите текст для поиска (название или описание задачи):\n\n"
            "Например: <code>отчёт</code> или <code>дизайн сайта</code>",
            parse_mode='HTML',
            reply_markup=cancel_keyboard
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer(
            "🔍 <b>Поиск задач</b>\n\n"
            "Введите текст для поиска (название или описание задачи):\n\n"
            "Например: <code>отчёт</code> или <code>дизайн сайта</code>",
            parse_mode='HTML',
            reply_markup=cancel_keyboard
        )
    await callback.answer()


@core_router.message(SearchTaskStates.waiting_for_query)
async def process_search_query(message: Message, state: FSMContext):
    """Обработка поискового запроса"""
    from app.states import SearchTaskStates
    
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    last_name = message.from_user.last_name or ''
    
    query = message.text.strip()
    
    logger.info(f"🔍 Search query from {username}: '{query}'")
    
    if len(query) < 2:
        await message.answer(
            "❌ Запрос слишком короткий. Введите минимум 2 символа."
        )
        return
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await message.answer("❌ Доступ запрещён")
        await state.clear()
        return
    
    await state.update_data(search_query=query)
    await state.clear()
    
    await show_search_results_page(message, user, query, page=1)


async def show_search_results_page(message: Message, user: dict, query: str, page: int = 1):
    """Показать страницу результатов поиска"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        search_pattern = f"%{query}%"
        
        # Подсчёт общего количества
        if user['role'] == 'admin':
            cur.execute(
                """SELECT COUNT(*) as count FROM tasks 
                   WHERE title LIKE ? OR description LIKE ?""",
                (search_pattern, search_pattern)
            )
        else:
            cur.execute(
                """SELECT COUNT(*) as count FROM tasks 
                   WHERE (title LIKE ? OR description LIKE ?)
                   AND (assigned_to_id = ? OR assigned_to_id IS NULL)""",
                (search_pattern, search_pattern, user['id'])
            )
        result = cur.fetchone()
        total_count = result["count"] if result else 0
        
        if total_count == 0:
            await message.answer(
                f"🔍 По запросу «{query}» ничего не найдено.",
                reply_markup=get_main_keyboard(user['role'])
            )
            return
        
        # Пагинация
        page_size = 10
        offset = (page - 1) * page_size
        total_pages = (total_count + page_size - 1) // page_size
        
        # Получение задач с именем исполнителя
        if user['role'] == 'admin':
            cur.execute(
                """SELECT t.id, t.title, t.status, t.priority, t.due_date, t.assigned_to_id, u.username as assignee_name
                   FROM tasks t
                   LEFT JOIN users u ON t.assigned_to_id = u.id
                   WHERE t.title LIKE ? OR t.description LIKE ?
                   ORDER BY t.created_at DESC
                   LIMIT ? OFFSET ?""",
                (search_pattern, search_pattern, page_size, offset)
            )
        else:
            cur.execute(
                """SELECT t.id, t.title, t.status, t.priority, t.due_date, t.assigned_to_id, u.username as assignee_name
                   FROM tasks t
                   LEFT JOIN users u ON t.assigned_to_id = u.id
                   WHERE (t.title LIKE ? OR t.description LIKE ?)
                   AND (t.assigned_to_id = ? OR t.assigned_to_id IS NULL)
                   ORDER BY t.created_at DESC
                   LIMIT ? OFFSET ?""",
                (search_pattern, search_pattern, user['id'], page_size, offset)
            )
        tasks = cur.fetchall()
        
        logger.info(f"🔍 Found {len(tasks)} tasks on page {page}/{total_pages} for query '{query}'")
        
        buttons = []
        
        status_emoji = {
            'pending': '⏳',
            'in_progress': '🔄',
            'partially_completed': '🔶',
            'completed': '✅',
            'rejected': '❌'
        }
        
        priority_emoji = {
            'urgent': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢'
        }
        
        # Кнопки задач
        for task in tasks:
            task_id = task['id']
            title = task['title']
            status = task['status']
            priority = task['priority']
            assigned_to_id = task.get('assigned_to_id')
            assignee_name = task.get('assignee_name')
            emoji_status = status_emoji.get(status, '📌')
            emoji_priority = priority_emoji.get(priority, '📌')
            
            if assigned_to_id is None:
                button_text = f"🆓 {emoji_priority} {title[:20]}"
            else:
                button_text = f"{emoji_status} {emoji_priority} {title[:25]}"
            
            buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"task_{task_id}"
                )
            ])
        
        # Кнопки пагинации (для будущей реализации)
        # nav_buttons = []
        # if page > 1:
        #     nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"search_page_{page-1}"))
        # if page < total_pages:
        #     nav_buttons.append(InlineKeyboardButton(text="▶️ Вперёд", callback_data=f"search_page_{page+1}"))
        # if nav_buttons:
        #     buttons.append(nav_buttons)
        
        buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        text = f"🔍 <b>Результаты поиска:</b> «{query}»\n\nНайдено: {total_count}"
        if total_pages > 1:
            text += f"\n\nСтраница {page}/{total_pages}"
        
        await message.answer(
            text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена текущей операции"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    
    logger.info(f"❌ Cancel operation by {username}")
    
    await state.clear()
    
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    try:
        await callback.message.delete()
    except Exception:
        logger.debug("⚠️ Could not delete message during cancel")
    
    await callback.message.answer(
        "❌ Операция отменена.\n\nВыберите действие:",
        reply_markup=get_main_keyboard(user['role'])
    )
    await callback.answer()


@core_router.callback_query(F.data == "back_to_main")
async def callback_back_to_main(callback: CallbackQuery, state: FSMContext):
    """Вернуться в главное меню"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"🔙 Back to main menu by {username}")
    
    await state.clear()
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    try:
        await callback.message.delete()
    except Exception:
        logger.debug("⚠️ Could not delete message during back_to_main")
    
    role_text = "👨‍💼 Администратор" if user['role'] == 'admin' else "👤 Сотрудник"
    
    await callback.message.answer(
        f"👋 Привет, {user['username']}!\n\n"
        f"Роль: <b>{role_text}</b>\n\n"
        f"Выберите действие:",
        parse_mode='HTML',
        reply_markup=get_main_keyboard(user['role'])
    )
    await callback.answer()


@core_router.message(F.text)
async def handle_unauthorized(message: Message):
    """Обработка текстовых сообщений от неавторизованных пользователей"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    last_name = message.from_user.last_name or ''
    
    logger.info(f"📨 Text message from {telegram_id} (@{username}): {message.text[:30] if message.text else 'no text'}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    
    if not user:
        logger.warning(f"⛔ Unauthorized access attempt by {telegram_id} (@{username})")
        await message.answer(
            "❌ <b>Доступ запрещён</b>\n\n"
            "Ваш username не авторизован в системе.\n"
            "Обратитесь к администратору для получения доступа.\n\n"
            f"Ваш username: @{username or 'отсутствует'}",
            parse_mode='HTML'
        )
