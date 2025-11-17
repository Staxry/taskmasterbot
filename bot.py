#!/usr/bin/env python3
import os
import asyncio
import logging
import psycopg2
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


class CreateTaskStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_priority = State()
    waiting_for_due_date = State()
    waiting_for_assignee = State()
    asking_for_task_photo = State()
    waiting_for_task_photo = State()


class AddUserStates(StatesGroup):
    waiting_for_username = State()
    waiting_for_role = State()


class CompleteTaskStates(StatesGroup):
    waiting_for_comment = State()
    asking_for_photo = State()
    waiting_for_photo = State()


def get_db_connection():
    """Создать подключение к PostgreSQL"""
    return psycopg2.connect(DATABASE_URL)


def check_user_allowed(username: str):
    """Проверить, разрешён ли пользователь в системе"""
    if not username:
        return None
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT username, role FROM allowed_users WHERE username = %s",
            (username,)
        )
        result = cur.fetchone()
        
        if result:
            return {'username': result[0], 'role': result[1]}
        return None
    finally:
        cur.close()
        conn.close()


def get_or_create_user(telegram_id: str, username: str, first_name: str):
    """Получить пользователя или создать нового (только если в whitelist)"""
    if not username:
        return None
    
    # Проверяем whitelist
    allowed = check_user_allowed(username)
    if not allowed:
        return None
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT id, telegram_id, username, role FROM users WHERE telegram_id = %s",
            (telegram_id,)
        )
        user = cur.fetchone()
        
        if user:
            # Обновляем роль если изменилась
            if user[3] != allowed['role']:
                cur.execute(
                    "UPDATE users SET role = %s WHERE telegram_id = %s",
                    (allowed['role'], telegram_id)
                )
                conn.commit()
                logger.info(f"Updated role for {username}: {allowed['role']}")
            
            return {
                'id': user[0],
                'telegram_id': user[1],
                'username': user[2],
                'role': allowed['role']
            }
        else:
            # Создаём нового пользователя с ролью из whitelist
            cur.execute(
                """INSERT INTO users (telegram_id, username, role, created_at, updated_at) 
                   VALUES (%s, %s, %s, NOW(), NOW()) 
                   RETURNING id, telegram_id, username, role""",
                (telegram_id, username, allowed['role'])
            )
            conn.commit()
            new_user = cur.fetchone()
            logger.info(f"✅ Created new user: {username} as {allowed['role']}")
            return {
                'id': new_user[0],
                'telegram_id': new_user[1],
                'username': new_user[2],
                'role': new_user[3]
            }
    finally:
        cur.close()
        conn.close()


def get_main_keyboard(role: str):
    """Главное меню с кнопками"""
    buttons = [
        [InlineKeyboardButton(text="📋 Мои задачи", callback_data="my_tasks")],
    ]
    
    if role == 'admin':
        buttons.append([InlineKeyboardButton(text="📊 Все задачи", callback_data="all_tasks")])
        buttons.append([InlineKeyboardButton(text="➕ Создать задачу", callback_data="create_task")])
        buttons.append([InlineKeyboardButton(text="🗑️ Удалить задачу", callback_data="delete_task_menu")])
        buttons.append([
            InlineKeyboardButton(text="➕👨‍💼 Добавить админа", callback_data="add_admin"),
            InlineKeyboardButton(text="➕👤 Добавить сотрудника", callback_data="add_employee")
        ])
        buttons.append([
            InlineKeyboardButton(text="🗑️👨‍💼 Удалить админа", callback_data="remove_admin"),
            InlineKeyboardButton(text="🗑️👤 Удалить сотрудника", callback_data="remove_employee")
        ])
    
    buttons.append([InlineKeyboardButton(text="❓ Помощь", callback_data="help")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_task_keyboard(task_id: int, current_status: str, assigned_to_id: int = None, user_id: int = None, is_admin: bool = False):
    """Клавиатура для работы с задачей"""
    buttons = []
    
    # Если задача не назначена и пользователь не админ - показываем кнопку "Взять в работу"
    if assigned_to_id is None and not is_admin:
        buttons.append([InlineKeyboardButton(text="✋ Взять в работу", callback_data=f"take_{task_id}")])
        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="my_tasks")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    statuses = {
        'pending': '⏳ Ожидает',
        'in_progress': '🔄 В работе',
        'partially_completed': '🔶 Частично завершена',
        'completed': '✅ Завершена',
        'rejected': '❌ Отклонена'
    }
    
    status_buttons = []
    for status, label in statuses.items():
        if status != current_status:
            status_buttons.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"status_{task_id}_{status}"
                )
            )
    
    for i in range(0, len(status_buttons), 2):
        buttons.append(status_buttons[i:i+2])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="my_tasks")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_priority_keyboard():
    """Клавиатура для выбора приоритета"""
    buttons = [
        [
            InlineKeyboardButton(text="🔴 Срочно", callback_data="priority_urgent"),
            InlineKeyboardButton(text="🟠 Высокий", callback_data="priority_high")
        ],
        [
            InlineKeyboardButton(text="🟡 Средний", callback_data="priority_medium"),
            InlineKeyboardButton(text="🟢 Низкий", callback_data="priority_low")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_due_date_keyboard():
    """Клавиатура для выбора срока выполнения"""
    today = datetime.now()
    
    buttons = [
        [
            InlineKeyboardButton(text="📅 Сегодня", callback_data=f"due_{today.strftime('%Y-%m-%d')}"),
            InlineKeyboardButton(text="📅 Завтра", callback_data=f"due_{(today + timedelta(days=1)).strftime('%Y-%m-%d')}")
        ],
        [
            InlineKeyboardButton(text="📅 Через 3 дня", callback_data=f"due_{(today + timedelta(days=3)).strftime('%Y-%m-%d')}"),
            InlineKeyboardButton(text="📅 Через неделю", callback_data=f"due_{(today + timedelta(days=7)).strftime('%Y-%m-%d')}")
        ],
        [
            InlineKeyboardButton(text="📅 Через 2 недели", callback_data=f"due_{(today + timedelta(days=14)).strftime('%Y-%m-%d')}"),
            InlineKeyboardButton(text="📅 Через месяц", callback_data=f"due_{(today + timedelta(days=30)).strftime('%Y-%m-%d')}")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_users_keyboard():
    """Клавиатура для выбора исполнителя"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """SELECT id, username, role FROM users 
               ORDER BY role DESC, username ASC"""
        )
        users = cur.fetchall()
        
        buttons = []
        
        for user_id, username, role in users:
            role_emoji = "👨‍💼" if role == "admin" else "👤"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{role_emoji} @{username}",
                    callback_data=f"assignee_{user_id}"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    finally:
        cur.close()
        conn.close()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Обработка команды /start"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    
    logger.info(f"🎯 /start from {telegram_id} (@{username})")
    
    # Проверяем авторизацию
    user = get_or_create_user(telegram_id, username, first_name)
    
    if not user:
        await message.answer(
            "❌ <b>Доступ запрещён</b>\n\n"
            "Ваш username не авторизован в системе.\n"
            "Обратитесь к администратору для получения доступа.\n\n"
            f"Ваш username: @{username or 'отсутствует'}",
            parse_mode='HTML'
        )
        return
    
    role_text = "👨‍💼 Администратор" if user['role'] == 'admin' else "👤 Сотрудник"
    
    await message.answer(
        f"👋 Привет, {user['username']}!\n\n"
        f"Роль: <b>{role_text}</b>\n\n"
        f"Выберите действие:",
        parse_mode='HTML',
        reply_markup=get_main_keyboard(user['role'])
    )


@dp.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    """Обработка кнопки Помощь"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
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


@dp.callback_query(F.data == "add_admin")
async def callback_add_admin(callback: CallbackQuery, state: FSMContext):
    """Начать добавление администратора"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user or user['role'] != 'admin':
        await callback.answer("❌ Только администраторы могут добавлять пользователей", show_alert=True)
        return
    
    await state.update_data(target_role='admin')
    await state.set_state(AddUserStates.waiting_for_username)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    
    await callback.message.edit_text(
        "👨‍💼 <b>Добавление администратора</b>\n\n"
        "Введите <b>username</b> нового администратора (без @):\n\n"
        "Например: <code>ivan_petrov</code>",
        parse_mode='HTML',
        reply_markup=cancel_keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "add_employee")
async def callback_add_employee(callback: CallbackQuery, state: FSMContext):
    """Начать добавление сотрудника"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user or user['role'] != 'admin':
        await callback.answer("❌ Только администраторы могут добавлять пользователей", show_alert=True)
        return
    
    await state.update_data(target_role='employee')
    await state.set_state(AddUserStates.waiting_for_username)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    
    await callback.message.edit_text(
        "👤 <b>Добавление сотрудника</b>\n\n"
        "Введите <b>username</b> нового сотрудника (без @):\n\n"
        "Например: <code>maria_ivanova</code>",
        parse_mode='HTML',
        reply_markup=cancel_keyboard
    )
    await callback.answer()


@dp.message(AddUserStates.waiting_for_username)
async def process_add_user_username(message: Message, state: FSMContext):
    """Обработка username для добавления пользователя"""
    new_username = message.text.strip().replace('@', '')
    
    if not new_username:
        await message.answer("❌ Username не может быть пустым. Попробуйте ещё раз:")
        return
    
    data = await state.get_data()
    target_role = data.get('target_role', 'employee')
    
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await message.answer("❌ Доступ запрещён")
        await state.clear()
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Добавляем пользователя в whitelist
        cur.execute(
            """INSERT INTO allowed_users (username, role, added_by_id, created_at)
               VALUES (%s, %s, %s, NOW())
               ON CONFLICT (username) 
               DO UPDATE SET role = EXCLUDED.role, added_by_id = EXCLUDED.added_by_id""",
            (new_username, target_role, user['id'])
        )
        conn.commit()
        
        role_text = "👨‍💼 Администратор" if target_role == 'admin' else "👤 Сотрудник"
        
        await message.answer(
            f"✅ <b>Пользователь добавлен!</b>\n\n"
            f"Username: @{new_username}\n"
            f"Роль: {role_text}\n\n"
            f"Теперь пользователь @{new_username} может отправить /start боту для авторизации.",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user['role'])
        )
        
        await state.clear()
        logger.info(f"✅ {username} added {new_username} as {target_role}")
    
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        await message.answer(
            f"❌ Ошибка при добавлении пользователя: {str(e)}",
            reply_markup=get_main_keyboard(user['role'])
        )
        await state.clear()
    finally:
        cur.close()
        conn.close()


@dp.callback_query(F.data == "my_tasks")
async def callback_my_tasks(callback: CallbackQuery):
    """Обработка кнопки Мои задачи"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Сотрудники видят:
        # 1. Задачи назначенные им (assigned_to_id = user.id)
        # 2. Задачи без исполнителя (assigned_to_id IS NULL)
        if user['role'] == 'admin':
            # Админы видят все задачи
            cur.execute(
                """SELECT id, title, status, priority, due_date, assigned_to_id
                   FROM tasks 
                   ORDER BY created_at DESC
                   LIMIT 20"""
            )
        else:
            # Сотрудники видят свои задачи + неназначенные
            cur.execute(
                """SELECT id, title, status, priority, due_date, assigned_to_id
                   FROM tasks 
                   WHERE assigned_to_id = %s OR assigned_to_id IS NULL
                   ORDER BY created_at DESC
                   LIMIT 20""",
                (user['id'],)
            )
        tasks = cur.fetchall()
        
        if not tasks:
            await callback.message.edit_text(
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
        
        for task in tasks[:10]:
            task_id, title, status, priority, due_date, assigned_to_id = task
            emoji_status = status_emoji.get(status, '📌')
            emoji_priority = priority_emoji.get(priority, '📌')
            
            # Добавляем индикатор если задача не назначена
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
        
        buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(
            "📋 <b>Выберите задачу:</b>",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        await callback.answer()
    
    finally:
        cur.close()
        conn.close()


@dp.callback_query(F.data == "all_tasks")
async def callback_all_tasks(callback: CallbackQuery):
    """Обработка кнопки Все задачи"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        await callback.answer("❌ Только администраторы могут просматривать все задачи.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """SELECT t.id, t.title, t.status, t.priority, u.username
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               ORDER BY t.created_at DESC
               LIMIT 20"""
        )
        tasks = cur.fetchall()
        
        if not tasks:
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
        
        for task in tasks[:10]:
            task_id, title, status, priority, assigned_username = task
            emoji_status = status_emoji.get(status, '📌')
            emoji_priority = priority_emoji.get(priority, '📌')
            
            button_text = f"{emoji_status} {emoji_priority} {title[:20]}"
            buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"task_{task_id}"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(
            f"📋 <b>Все задачи в системе ({len(tasks)}):</b>",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        await callback.answer()
    
    finally:
        cur.close()
        conn.close()


@dp.callback_query(F.data.startswith("task_") & ~F.data.in_({"task_photo_yes", "task_photo_no"}))
async def callback_task_details(callback: CallbackQuery):
    """Показать детали задачи"""
    task_id = int(callback.data.split('_')[1])
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """SELECT t.id, t.title, t.description, t.status, t.priority, t.due_date, 
                      u.username, t.created_at, t.assigned_to_id
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               WHERE t.id = %s""",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            await callback.answer("❌ Задача не найдена.", show_alert=True)
            return
        
        tid, title, description, status, priority, due_date, assigned_username, created_at, assigned_to_id = task
        
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
"""
        
        # Добавляем подсказку для неназначенных задач
        if assigned_to_id is None:
            text += "\n💡 Эта задача свободна - любой сотрудник может взять её в работу!"
        else:
            text += "\nВыберите новый статус:"
        
        # Проверяем, есть ли в сообщении фото или текст
        try:
            # Пытаемся отредактировать как текстовое сообщение
            await callback.message.edit_text(
                text,
                parse_mode='HTML',
                reply_markup=get_task_keyboard(task_id, status, assigned_to_id, user['id'], user['role'] == 'admin')
            )
        except Exception:
            # Если не получилось (например, сообщение с фото), удаляем и отправляем новое
            await callback.message.delete()
            await callback.message.answer(
                text,
                parse_mode='HTML',
                reply_markup=get_task_keyboard(task_id, status, assigned_to_id, user['id'], user['role'] == 'admin')
            )
        
        await callback.answer()
    
    finally:
        cur.close()
        conn.close()


@dp.callback_query(F.data.startswith("status_"))
async def callback_update_status(callback: CallbackQuery, state: FSMContext):
    """Обновить статус задачи"""
    parts = callback.data.split('_')
    task_id = int(parts[1])
    new_status = parts[2]
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
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
            await callback.answer("❌ Задача не найдена.", show_alert=True)
            return
        
        if task[0] != user['id'] and user['role'] != 'admin':
            await callback.answer("❌ Вы можете обновлять только свои задачи.", show_alert=True)
            return
        
        # Если меняем на "Завершена" или "Частично завершена" - запрашиваем комментарий
        if new_status in ['completed', 'partially_completed']:
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
            else:  # partially_completed
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
        
        # Для других статусов - обновляем сразу
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
        
        await callback.answer(f"✅ Статус обновлён на: {status_text}", show_alert=True)
        
        # Обновляем отображение задачи с новым статусом
        cur.execute(
            """SELECT t.id, t.title, t.description, t.status, t.priority, t.due_date, 
                      u.username, t.created_at
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               WHERE t.id = %s""",
            (task_id,)
        )
        updated_task = cur.fetchone()
        
        if updated_task:
            tid, title, description, status, priority, due_date, assigned_username, created_at = updated_task
            
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

Выберите новый статус:"""
            
            await callback.message.edit_text(
                text,
                parse_mode='HTML',
                reply_markup=get_task_keyboard(task_id, status)
            )
    
    except Exception as e:
        logger.error(f"Error updating status: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка при обновлении статуса: {str(e)}", show_alert=True)
    finally:
        cur.close()
        conn.close()


@dp.callback_query(F.data.startswith("take_"))
async def callback_take_task(callback: CallbackQuery):
    """Взять задачу в работу"""
    task_id = int(callback.data.split('_')[1])
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] == 'admin':
        await callback.answer("❌ Админы не могут брать задачи в работу. Используйте назначение через создание задачи.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Получаем полную информацию о задаче включая фото
        cur.execute(
            """SELECT id, title, description, priority, due_date, assigned_to_id, created_by_id, task_photo_file_id 
               FROM tasks WHERE id = %s""",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            await callback.answer("❌ Задача не найдена.", show_alert=True)
            return
        
        task_id_db, title, description, priority, due_date, assigned_to_id, created_by_id, task_photo_file_id = task
        
        if assigned_to_id is not None:
            await callback.answer("❌ Эта задача уже назначена другому сотруднику.", show_alert=True)
            return
        
        # Назначаем задачу пользователю и ставим статус "В работе"
        cur.execute(
            "UPDATE tasks SET assigned_to_id = %s, status = 'in_progress', updated_at = NOW() WHERE id = %s",
            (user['id'], task_id)
        )
        conn.commit()
        
        await callback.answer("✅ Задача взята в работу!", show_alert=True)
        
        # Отправляем уведомление админу (создателю)
        if created_by_id:
            cur.execute(
                "SELECT telegram_id, username FROM users WHERE id = %s",
                (created_by_id,)
            )
            creator = cur.fetchone()
            
            if creator:
                creator_telegram_id, creator_username = creator
                
                # Формируем текст уведомления
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
<b>Исполнитель:</b> @{username}
<b>Статус:</b> 🔄 В работе

Нажмите кнопку ниже для просмотра задачи."""
                
                # Кнопка для открытия задачи
                task_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📂 Открыть задачу", callback_data=f"task_{task_id}")]
                ])
                
                try:
                    if task_photo_file_id:
                        # Отправляем с фото
                        await bot.send_photo(
                            chat_id=creator_telegram_id,
                            photo=task_photo_file_id,
                            caption=notification_text,
                            parse_mode='HTML',
                            reply_markup=task_keyboard
                        )
                    else:
                        # Отправляем без фото
                        await bot.send_message(
                            chat_id=creator_telegram_id,
                            text=notification_text,
                            parse_mode='HTML',
                            reply_markup=task_keyboard
                        )
                    logger.info(f"✅ Task assignment notification sent to {creator_username}")
                except Exception as notif_error:
                    logger.warning(f"⚠️ Could not send notification: {notif_error}")
        
        # Обновляем отображение задачи
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
        logger.error(f"Error taking task: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
    finally:
        cur.close()
        conn.close()


@dp.message(CompleteTaskStates.waiting_for_comment)
async def process_completion_comment(message: Message, state: FSMContext):
    """Обработать комментарий о завершении задачи"""
    comment = message.text
    
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await message.answer("❌ Доступ запрещён")
        await state.clear()
        return
    
    # Сохраняем комментарий и спрашиваем про фото
    await state.update_data(comment=comment)
    await state.set_state(CompleteTaskStates.asking_for_photo)
    
    photo_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, добавить фото", callback_data="photo_yes"),
            InlineKeyboardButton(text="❌ Нет, без фото", callback_data="photo_no")
        ]
    ])
    
    await message.answer(
        "📸 <b>Добавить фото к отчёту?</b>\n\n"
        "Фото поможет лучше продемонстрировать результат работы.",
        parse_mode='HTML',
        reply_markup=photo_keyboard
    )


@dp.callback_query(F.data == "photo_yes")
async def callback_photo_yes(callback: CallbackQuery, state: FSMContext):
    """Пользователь хочет добавить фото"""
    await state.set_state(CompleteTaskStates.waiting_for_photo)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="photo_no")]
    ])
    
    await callback.message.edit_text(
        "📸 <b>Загрузите фото</b>\n\n"
        "Отправьте фотографию результата работы.\n"
        "Можно отправить одно фото.",
        parse_mode='HTML',
        reply_markup=cancel_keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "photo_no")
async def callback_photo_no(callback: CallbackQuery, state: FSMContext):
    """Пользователь не хочет добавлять фото"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        await state.clear()
        return
    
    data = await state.get_data()
    task_id = data.get('task_id')
    new_status = data.get('new_status')
    comment = data.get('comment')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Обновляем статус и сохраняем комментарий
        cur.execute(
            "UPDATE tasks SET status = %s, completion_comment = %s, updated_at = NOW() WHERE id = %s",
            (new_status, comment, task_id)
        )
        conn.commit()
        
        # Получаем информацию о задаче и создателе
        cur.execute(
            """SELECT t.id, t.title, t.description, t.priority, t.due_date, 
                      t.created_by_id, c.username as creator_username, c.telegram_id as creator_telegram_id
               FROM tasks t
               LEFT JOIN users c ON t.created_by_id = c.id
               WHERE t.id = %s""",
            (task_id,)
        )
        task_info = cur.fetchone()
        
        if task_info:
            task_id, title, description, priority, due_date, created_by_id, creator_username, creator_telegram_id = task_info
            
            priority_text = {
                'urgent': '🔴 Срочно',
                'high': '🟠 Высокий',
                'medium': '🟡 Средний',
                'low': '🟢 Низкий'
            }.get(priority, priority)
            
            # Подтверждение пользователю
            if new_status == 'completed':
                confirmation = "✅ <b>Задача завершена!</b>\n\nКомментарий сохранён.\nСоздатель задачи получит уведомление."
            else:  # partially_completed
                confirmation = "🔶 <b>Задача частично завершена!</b>\n\nКомментарий сохранён.\nСоздатель задачи получит уведомление о прогрессе."
            
            await callback.message.answer(
                confirmation,
                parse_mode='HTML',
                reply_markup=get_main_keyboard(user['role'])
            )
            
            # Отправляем уведомление создателю задачи (без фото)
            if created_by_id and creator_telegram_id and creator_telegram_id != telegram_id:
                try:
                    if new_status == 'completed':
                        notification_text = f"""✅ <b>Задача завершена!</b>

<b>Задача #{task_id}</b>
<b>Название:</b> {title}
<b>Приоритет:</b> {priority_text}
<b>Срок был:</b> 📅 {due_date}

<b>Исполнитель:</b> @{username}
<b>Комментарий:</b> {comment}

Используйте /start для просмотра задачи."""
                    else:  # partially_completed
                        notification_text = f"""🔶 <b>Задача частично завершена!</b>

<b>Задача #{task_id}</b>
<b>Название:</b> {title}
<b>Приоритет:</b> {priority_text}
<b>Срок:</b> 📅 {due_date}

<b>Исполнитель:</b> @{username}
<b>Отчёт о прогрессе:</b> {comment}

Задача ещё в работе. Используйте /start для просмотра."""
                    
                    await bot.send_message(
                        chat_id=creator_telegram_id,
                        text=notification_text,
                        parse_mode='HTML'
                    )
                    logger.info(f"✅ Completion notification sent to {creator_username} (task #{task_id})")
                except Exception as notif_error:
                    logger.warning(f"⚠️ Could not send completion notification: {notif_error}")
        
        await state.clear()
        logger.info(f"✅ Task #{task_id} completed by {username} with comment")
    
    except Exception as e:
        logger.error(f"Error completing task: {e}", exc_info=True)
        await callback.message.answer("❌ Ошибка при завершении задачи", reply_markup=get_main_keyboard(user['role']))
    finally:
        cur.close()
        conn.close()


@dp.message(CompleteTaskStates.waiting_for_photo, F.photo)
async def process_completion_photo(message: Message, state: FSMContext):
    """Обработать загруженное фото"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await message.answer("❌ Доступ запрещён")
        await state.clear()
        return
    
    # Получаем самую большую версию фото
    photo_file_id = message.photo[-1].file_id
    
    data = await state.get_data()
    task_id = data.get('task_id')
    new_status = data.get('new_status')
    comment = data.get('comment')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Обновляем задачу с комментарием и фото
        cur.execute(
            "UPDATE tasks SET status = %s, completion_comment = %s, photo_file_id = %s, updated_at = NOW() WHERE id = %s",
            (new_status, comment, photo_file_id, task_id)
        )
        conn.commit()
        
        # Получаем информацию о задаче
        cur.execute(
            """SELECT t.id, t.title, t.description, t.priority, t.due_date, 
                      t.created_by_id, c.username as creator_username, c.telegram_id as creator_telegram_id
               FROM tasks t
               LEFT JOIN users c ON t.created_by_id = c.id
               WHERE t.id = %s""",
            (task_id,)
        )
        task_info = cur.fetchone()
        
        if task_info:
            task_id, title, description, priority, due_date, created_by_id, creator_username, creator_telegram_id = task_info
            
            priority_text = {
                'urgent': '🔴 Срочно',
                'high': '🟠 Высокий',
                'medium': '🟡 Средний',
                'low': '🟢 Низкий'
            }.get(priority, priority)
            
            # Подтверждение пользователю
            if new_status == 'completed':
                confirmation = "✅ <b>Задача завершена!</b>\n\n📸 Фото и комментарий сохранены.\nСоздатель задачи получит уведомление."
            else:  # partially_completed
                confirmation = "🔶 <b>Задача частично завершена!</b>\n\n📸 Фото и комментарий сохранены.\nСоздатель задачи получит уведомление о прогрессе."
            
            await message.answer(
                confirmation,
                parse_mode='HTML',
                reply_markup=get_main_keyboard(user['role'])
            )
            
            # Отправляем уведомление создателю задачи с фото
            if created_by_id and creator_telegram_id and creator_telegram_id != telegram_id:
                try:
                    if new_status == 'completed':
                        caption = f"""✅ <b>Задача завершена!</b>

<b>Задача #{task_id}</b>
<b>Название:</b> {title}
<b>Приоритет:</b> {priority_text}
<b>Срок был:</b> 📅 {due_date}

<b>Исполнитель:</b> @{username}
<b>Комментарий:</b> {comment}

Используйте /start для просмотра задачи."""
                    else:  # partially_completed
                        caption = f"""🔶 <b>Задача частично завершена!</b>

<b>Задача #{task_id}</b>
<b>Название:</b> {title}
<b>Приоритет:</b> {priority_text}
<b>Срок:</b> 📅 {due_date}

<b>Исполнитель:</b> @{username}
<b>Отчёт о прогрессе:</b> {comment}

Задача ещё в работе. Используйте /start для просмотра."""
                    
                    # Отправляем фото с подписью
                    await bot.send_photo(
                        chat_id=creator_telegram_id,
                        photo=photo_file_id,
                        caption=caption,
                        parse_mode='HTML'
                    )
                    logger.info(f"✅ Completion notification with photo sent to {creator_username} (task #{task_id})")
                except Exception as notif_error:
                    logger.warning(f"⚠️ Could not send completion notification: {notif_error}")
        
        await state.clear()
        logger.info(f"✅ Task #{task_id} completed by {username} with comment and photo")
    
    except Exception as e:
        logger.error(f"Error completing task with photo: {e}", exc_info=True)
        await message.answer("❌ Ошибка при завершении задачи", reply_markup=get_main_keyboard(user['role']))
    finally:
        cur.close()
        conn.close()


@dp.callback_query(F.data == "create_task")
async def callback_create_task(callback: CallbackQuery, state: FSMContext):
    """Начать создание задачи"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        await callback.answer("❌ Только администраторы могут создавать задачи.", show_alert=True)
        return
    
    await state.set_state(CreateTaskStates.waiting_for_title)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    
    await callback.message.edit_text(
        "➕ <b>Создание задачи</b>\n\n"
        "Введите <b>название задачи</b>:",
        parse_mode='HTML',
        reply_markup=cancel_keyboard
    )
    await callback.answer()


@dp.message(CreateTaskStates.waiting_for_title)
async def process_task_title(message: Message, state: FSMContext):
    """Получить название задачи"""
    await state.update_data(title=message.text)
    await state.set_state(CreateTaskStates.waiting_for_description)
    
    skip_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_description")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    
    await message.answer(
        "Введите <b>описание задачи</b> (или нажмите Пропустить):",
        parse_mode='HTML',
        reply_markup=skip_keyboard
    )


@dp.callback_query(F.data == "skip_description", CreateTaskStates.waiting_for_description)
async def skip_description(callback: CallbackQuery, state: FSMContext):
    """Пропустить описание"""
    await state.update_data(description="")
    await state.set_state(CreateTaskStates.waiting_for_priority)
    
    await callback.message.edit_text(
        "Выберите <b>приоритет задачи</b>:",
        parse_mode='HTML',
        reply_markup=get_priority_keyboard()
    )
    await callback.answer()


@dp.message(CreateTaskStates.waiting_for_description)
async def process_task_description(message: Message, state: FSMContext):
    """Получить описание задачи"""
    await state.update_data(description=message.text)
    await state.set_state(CreateTaskStates.waiting_for_priority)
    
    await message.answer(
        "Выберите <b>приоритет задачи</b>:",
        parse_mode='HTML',
        reply_markup=get_priority_keyboard()
    )


@dp.callback_query(F.data.startswith("priority_"))
async def process_priority(callback: CallbackQuery, state: FSMContext):
    """Обработать выбор приоритета и перейти к выбору срока"""
    priority = callback.data.split('_')[1]
    
    await state.update_data(priority=priority)
    await state.set_state(CreateTaskStates.waiting_for_due_date)
    
    await callback.message.edit_text(
        "📅 <b>Выберите срок выполнения задачи:</b>",
        parse_mode='HTML',
        reply_markup=get_due_date_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("due_"))
async def process_due_date(callback: CallbackQuery, state: FSMContext):
    """Обработать выбор срока и перейти к выбору исполнителя"""
    due_date = callback.data.split('_', 1)[1]
    
    await state.update_data(due_date=due_date)
    await state.set_state(CreateTaskStates.waiting_for_assignee)
    
    await callback.message.edit_text(
        "👥 <b>Выберите исполнителя задачи:</b>",
        parse_mode='HTML',
        reply_markup=get_users_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("assignee_"))
async def process_assignee(callback: CallbackQuery, state: FSMContext):
    """Выбрать исполнителя и спросить про фото"""
    assignee_id = int(callback.data.split('_')[1])
    
    # Сохраняем исполнителя
    await state.update_data(assignee_id=assignee_id)
    await state.set_state(CreateTaskStates.asking_for_task_photo)
    
    # Спрашиваем про фото
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


async def create_task_with_photo(callback_or_message, state: FSMContext, photo_file_id=None):
    """Создать задачу с фото или без"""
    is_message = isinstance(callback_or_message, Message)
    
    if is_message:
        telegram_id = str(callback_or_message.from_user.id)
        username = callback_or_message.from_user.username
        first_name = callback_or_message.from_user.first_name or ''
    else:
        telegram_id = str(callback_or_message.from_user.id)
        username = callback_or_message.from_user.username
        first_name = callback_or_message.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
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
    due_date = data.get('due_date', (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
    assignee_id = data.get('assignee_id')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Получаем информацию об исполнителе (если есть)
        if assignee_id:
            cur.execute(
                "SELECT username, telegram_id FROM users WHERE id = %s",
                (assignee_id,)
            )
            assignee = cur.fetchone()
            
            if not assignee:
                if is_message:
                    await callback_or_message.answer("❌ Исполнитель не найден")
                else:
                    await callback_or_message.answer("❌ Исполнитель не найден", show_alert=True)
                await state.clear()
                return
            
            assignee_username = assignee[0]
            assignee_telegram_id = assignee[1]
        else:
            assignee_username = None
            assignee_telegram_id = None
        
        # Создаём задачу
        cur.execute(
            """INSERT INTO tasks 
               (title, description, priority, status, due_date, assigned_to_id, created_by_id, task_photo_file_id, created_at, updated_at)
               VALUES (%s, %s, %s, 'pending', %s, %s, %s, %s, NOW(), NOW())
               RETURNING id, title, priority, status""",
            (
                title,
                description,
                priority,
                due_date,
                assignee_id,
                user['id'],
                photo_file_id
            )
        )
        conn.commit()
        task = cur.fetchone()
        task_id = task[0]
        
        priority_text = {
            'urgent': '🔴 Срочно',
            'high': '🟠 Высокий',
            'medium': '🟡 Средний',
            'low': '🟢 Низкий'
        }.get(priority, priority)
        
        # Сообщение об успехе
        success_msg = f"✅ <b>Задача создана успешно!</b>\n\n"
        success_msg += f"ID: {task[0]}\n"
        success_msg += f"Название: {task[1]}\n"
        success_msg += f"Приоритет: {priority_text}\n"
        success_msg += f"Срок: 📅 {due_date}\n"
        
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
        
        # Отправляем уведомление исполнителю (если назначен)
        if assignee_telegram_id:
            try:
                notification_text = f"""📋 <b>Вам назначена новая задача!</b>

<b>Задача #{task_id}</b>
<b>Название:</b> {title}
<b>Описание:</b> {description or 'Нет описания'}
<b>Приоритет:</b> {priority_text}
<b>Срок:</b> 📅 {due_date}
<b>Создал:</b> @{username}
<b>Статус:</b> ⏳ Ожидает

Используйте /start для просмотра задачи."""
                
                # Кнопка для открытия задачи
                task_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📂 Открыть задачу", callback_data=f"task_{task_id}")]
                ])
                
                if photo_file_id:
                    # Отправляем с фото
                    await bot.send_photo(
                        chat_id=assignee_telegram_id,
                        photo=photo_file_id,
                        caption=notification_text,
                        parse_mode='HTML',
                        reply_markup=task_keyboard
                    )
                else:
                    # Отправляем без фото
                    await bot.send_message(
                        chat_id=assignee_telegram_id,
                        text=notification_text,
                        parse_mode='HTML',
                        reply_markup=task_keyboard
                    )
                logger.info(f"✅ Notification sent to {assignee_username} (task #{task_id})")
            except Exception as notif_error:
                logger.warning(f"⚠️ Could not send notification to {assignee_username}: {notif_error}")
        
        logger.info(f"✅ Task created: {title} by {username}")
    
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        if is_message:
            await callback_or_message.answer("❌ Ошибка при создании задачи")
        else:
            await callback_or_message.answer("❌ Ошибка при создании задачи", show_alert=True)
    finally:
        cur.close()
        conn.close()


@dp.callback_query(F.data == "task_photo_yes")
async def callback_task_photo_yes(callback: CallbackQuery, state: FSMContext):
    """Пользователь хочет добавить фото к задаче"""
    await state.set_state(CreateTaskStates.waiting_for_task_photo)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="task_photo_no")]
    ])
    
    await callback.message.edit_text(
        "📸 <b>Загрузите фото</b>\n\n"
        "Отправьте фотографию к задаче.\n"
        "Можно отправить одно фото.",
        parse_mode='HTML',
        reply_markup=cancel_keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "task_photo_no")
async def callback_task_photo_no(callback: CallbackQuery, state: FSMContext):
    """Создать задачу без фото"""
    await create_task_with_photo(callback, state, None)


@dp.message(CreateTaskStates.waiting_for_task_photo, F.photo)
async def process_task_photo(message: Message, state: FSMContext):
    """Обработать загруженное фото задачи"""
    # Получаем самую большую версию фото
    photo_file_id = message.photo[-1].file_id
    
    # Создаём задачу с фото
    await create_task_with_photo(message, state, photo_file_id)


@dp.callback_query(F.data == "delete_task_menu")
async def callback_delete_task_menu(callback: CallbackQuery):
    """Показать список незавершённых задач для удаления"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        await callback.answer("❌ Только администраторы могут удалять задачи.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Получаем незавершённые задачи
        cur.execute(
            """SELECT t.id, t.title, t.status, t.priority, u.username
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               WHERE t.status != 'completed'
               ORDER BY t.created_at DESC
               LIMIT 20"""
        )
        tasks = cur.fetchall()
        
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
            task_id, title, status, priority, assigned_username = task
            emoji_status = status_emoji.get(status, '📌')
            emoji_priority = priority_emoji.get(priority, '📌')
            
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


@dp.callback_query(F.data.startswith("delete_confirm_"))
async def callback_delete_confirm(callback: CallbackQuery):
    """Удалить задачу после подтверждения"""
    task_id = int(callback.data.split('_')[2])
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        await callback.answer("❌ Только администраторы могут удалять задачи.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Получаем информацию о задаче перед удалением
        cur.execute(
            "SELECT title FROM tasks WHERE id = %s",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            await callback.answer("❌ Задача не найдена.", show_alert=True)
            return
        
        task_title = task[0]
        
        # Удаляем задачу
        cur.execute(
            "DELETE FROM tasks WHERE id = %s",
            (task_id,)
        )
        conn.commit()
        
        await callback.message.edit_text(
            f"✅ <b>Задача удалена!</b>\n\n"
            f"ID: {task_id}\n"
            f"Название: {task_title}\n\n"
            f"Задача полностью удалена из системы.",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user['role'])
        )
        await callback.answer("✅ Задача удалена", show_alert=True)
        
        logger.info(f"✅ Task #{task_id} deleted by {username}")
    
    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        await callback.answer("❌ Ошибка при удалении задачи", show_alert=True)
    finally:
        cur.close()
        conn.close()


@dp.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена текущей операции"""
    await state.clear()
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.message.edit_text("❌ Доступ запрещён")
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "❌ Операция отменена.\n\nВыберите действие:",
        reply_markup=get_main_keyboard(user['role'])
    )
    await callback.answer()


@dp.callback_query(F.data == "back_to_main")
async def callback_back_to_main(callback: CallbackQuery):
    """Вернуться в главное меню"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.message.edit_text("❌ Доступ запрещён")
        await callback.answer()
        return
    
    role_text = "👨‍💼 Администратор" if user['role'] == 'admin' else "👤 Сотрудник"
    
    await callback.message.edit_text(
        f"👋 Привет, {user['username']}!\n\n"
        f"Роль: <b>{role_text}</b>\n\n"
        f"Выберите действие:",
        parse_mode='HTML',
        reply_markup=get_main_keyboard(user['role'])
    )
    await callback.answer()


@dp.callback_query(F.data == "remove_admin")
async def callback_remove_admin(callback: CallbackQuery):
    """Показать список админов для удаления"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        await callback.answer("❌ Только администраторы могут удалять пользователей.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT id, username FROM users WHERE role = 'admin' AND telegram_id != %s ORDER BY username",
            (telegram_id,)
        )
        admins = cur.fetchall()
        
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
        for admin_id, admin_username in admins:
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


@dp.callback_query(F.data == "remove_employee")
async def callback_remove_employee(callback: CallbackQuery):
    """Показать список сотрудников для удаления"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        await callback.answer("❌ Только администраторы могут удалять пользователей.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT id, username FROM users WHERE role = 'employee' ORDER BY username"
        )
        employees = cur.fetchall()
        
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
        for emp_id, emp_username in employees:
            buttons.append([
                InlineKeyboardButton(
                    text=f"🗑️ @{emp_username}",
                    callback_data=f"confirmremove_{emp_id}_employee"
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


@dp.callback_query(F.data.startswith("confirmremove_"))
async def callback_confirm_remove_user(callback: CallbackQuery):
    """Подтверждение удаления пользователя"""
    parts = callback.data.split('_')
    user_id_to_remove = int(parts[1])
    user_type = parts[2]
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        await callback.answer("❌ Только администраторы могут удалять пользователей.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Получаем информацию о пользователе
        cur.execute(
            "SELECT username, role FROM users WHERE id = %s",
            (user_id_to_remove,)
        )
        user_to_remove = cur.fetchone()
        
        if not user_to_remove:
            await callback.answer("❌ Пользователь не найден.", show_alert=True)
            return
        
        username_to_remove, role_to_remove = user_to_remove
        
        # Удаляем пользователя из таблицы users
        cur.execute("DELETE FROM users WHERE id = %s", (user_id_to_remove,))
        
        # Удаляем из allowed_users
        cur.execute("DELETE FROM allowed_users WHERE username = %s", (username_to_remove,))
        
        # Снимаем назначение с задач
        cur.execute("UPDATE tasks SET assigned_to_id = NULL WHERE assigned_to_id = %s", (user_id_to_remove,))
        
        conn.commit()
        
        role_text = "👨‍💼 Администратор" if role_to_remove == 'admin' else "👤 Сотрудник"
        
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
        
        logger.info(f"✅ Admin {username} removed user {username_to_remove} ({role_to_remove})")
    
    except Exception as e:
        logger.error(f"Error removing user: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка при удалении: {str(e)}", show_alert=True)
    finally:
        cur.close()
        conn.close()


@dp.message()
async def handle_unauthorized(message: Message):
    """Обработка сообщений от неавторизованных пользователей"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    
    if not user:
        await message.answer(
            "❌ <b>Доступ запрещён</b>\n\n"
            "Ваш username не авторизован в системе.\n"
            "Обратитесь к администратору для получения доступа.\n\n"
            f"Ваш username: @{username or 'отсутствует'}",
            parse_mode='HTML'
        )


async def main():
    """Запуск бота"""
    logger.info("🤖 Starting bot with whitelist authorization...")
    
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
