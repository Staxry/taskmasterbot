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


class AddUserStates(StatesGroup):
    waiting_for_username = State()
    waiting_for_role = State()


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
        buttons.append([
            InlineKeyboardButton(text="👨‍💼 Добавить админа", callback_data="add_admin"),
            InlineKeyboardButton(text="👤 Добавить сотрудника", callback_data="add_employee")
        ])
    
    buttons.append([InlineKeyboardButton(text="❓ Помощь", callback_data="help")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_task_keyboard(task_id: int, current_status: str):
    """Клавиатура для работы с задачей"""
    buttons = []
    
    statuses = {
        'pending': '⏳ Ожидает',
        'in_progress': '🔄 В работе',
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
        cur.execute(
            """SELECT id, title, status, priority, due_date 
               FROM tasks 
               WHERE assigned_to_id = %s 
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
            task_id, title, status, priority, due_date = task
            emoji_status = status_emoji.get(status, '📌')
            emoji_priority = priority_emoji.get(priority, '📌')
            
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


@dp.callback_query(F.data.startswith("task_"))
async def callback_task_details(callback: CallbackQuery):
    """Показать детали задачи"""
    task_id = int(callback.data.split('_')[1])
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """SELECT t.id, t.title, t.description, t.status, t.priority, t.due_date, 
                      u.username, t.created_at
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               WHERE t.id = %s""",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            await callback.answer("❌ Задача не найдена.", show_alert=True)
            return
        
        tid, title, description, status, priority, due_date, assigned_username, created_at = task
        
        status_text = {
            'pending': '⏳ Ожидает',
            'in_progress': '🔄 В работе',
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
<b>Назначена:</b> @{assigned_username or 'Не назначена'}
<b>Создана:</b> {created_at.strftime('%Y-%m-%d %H:%M')}

Выберите новый статус:"""
        
        await callback.message.edit_text(
            text,
            parse_mode='HTML',
            reply_markup=get_task_keyboard(task_id, status)
        )
        await callback.answer()
    
    finally:
        cur.close()
        conn.close()


@dp.callback_query(F.data.startswith("status_"))
async def callback_update_status(callback: CallbackQuery):
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
        
        cur.execute(
            "UPDATE tasks SET status = %s, updated_at = NOW() WHERE id = %s",
            (new_status, task_id)
        )
        conn.commit()
        
        status_text = {
            'pending': '⏳ Ожидает',
            'in_progress': '🔄 В работе',
            'completed': '✅ Завершена',
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
    """Обработать выбор исполнителя и создать задачу"""
    assignee_id = int(callback.data.split('_')[1])
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        await state.clear()
        return
    
    data = await state.get_data()
    title = data.get('title', '')
    description = data.get('description', '')
    priority = data.get('priority', 'medium')
    due_date = data.get('due_date', (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Получаем информацию об исполнителе
        cur.execute(
            "SELECT username, telegram_id FROM users WHERE id = %s",
            (assignee_id,)
        )
        assignee = cur.fetchone()
        
        if not assignee:
            await callback.answer("❌ Исполнитель не найден", show_alert=True)
            await state.clear()
            return
        
        assignee_username = assignee[0]
        assignee_telegram_id = assignee[1]
        
        # Создаём задачу
        cur.execute(
            """INSERT INTO tasks 
               (title, description, priority, status, due_date, assigned_to_id, created_by_id, created_at, updated_at)
               VALUES (%s, %s, %s, 'pending', %s, %s, %s, NOW(), NOW())
               RETURNING id, title, priority, status""",
            (
                title,
                description,
                priority,
                due_date,
                assignee_id,
                user['id']
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
        
        await callback.message.edit_text(
            f"✅ <b>Задача создана успешно!</b>\n\n"
            f"ID: {task[0]}\n"
            f"Название: {task[1]}\n"
            f"Приоритет: {priority_text}\n"
            f"Срок: 📅 {due_date}\n"
            f"Исполнитель: @{assignee_username}\n"
            f"Статус: ⏳ Ожидает\n\n"
            f"📨 Уведомление отправлено исполнителю",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user['role'])
        )
        await callback.answer()
        await state.clear()
        
        # Отправляем уведомление исполнителю
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
            
            await bot.send_message(
                chat_id=assignee_telegram_id,
                text=notification_text,
                parse_mode='HTML'
            )
            logger.info(f"✅ Notification sent to {assignee_username} (task #{task_id})")
        except Exception as notif_error:
            logger.warning(f"⚠️ Could not send notification to {assignee_username}: {notif_error}")
        
        logger.info(f"✅ Task created: {title} assigned to {assignee_username} by {username}")
    
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        await callback.answer("❌ Ошибка при создании задачи", show_alert=True)
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
