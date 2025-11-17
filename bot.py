#!/usr/bin/env python3
import os
import asyncio
import logging
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage

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


def get_db_connection():
    """Создать подключение к PostgreSQL"""
    return psycopg2.connect(DATABASE_URL)


def get_or_create_user(telegram_id: str, username: str, first_name: str):
    """Получить пользователя или создать нового"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT id, telegram_id, username, role FROM users WHERE telegram_id = %s",
            (telegram_id,)
        )
        user = cur.fetchone()
        
        if user:
            logger.info(f"👤 Found existing user: {telegram_id}")
            return {
                'id': user[0],
                'telegram_id': user[1],
                'username': user[2],
                'role': user[3]
            }
        else:
            cur.execute(
                """INSERT INTO users (telegram_id, username, role, created_at, updated_at) 
                   VALUES (%s, %s, 'employee', NOW(), NOW()) 
                   RETURNING id, telegram_id, username, role""",
                (telegram_id, username or first_name or str(telegram_id))
            )
            conn.commit()
            new_user = cur.fetchone()
            logger.info(f"✅ Created new user: {telegram_id}")
            return {
                'id': new_user[0],
                'telegram_id': new_user[1],
                'username': new_user[2],
                'role': new_user[3]
            }
    finally:
        cur.close()
        conn.close()


@dp.message(Command('start', 'старт'))
async def cmd_start(message: Message):
    """Обработка команды /start"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username or message.from_user.first_name
    first_name = message.from_user.first_name or ''
    
    logger.info(f"🎯 /start from {telegram_id}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    
    await message.answer(
        f"👋 Привет, {user['username']}!\n\n"
        f"Вы зарегистрированы как: <b>{user['role']}</b>\n\n"
        f"Используйте /help для списка команд.",
        parse_mode='HTML'
    )


@dp.message(Command('help', 'помощь'))
async def cmd_help(message: Message):
    """Обработка команды /help"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username or message.from_user.first_name
    first_name = message.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    
    if user['role'] == 'admin':
        text = """📋 <b>Доступные команды (Администратор):</b>

<b>Общие:</b>
/start - Приветствие
/help - Список команд

<b>Управление задачами:</b>
/create_task - Создать задачу
/my_tasks - Мои задачи
/all_tasks - Все задачи
/task_details &lt;ID&gt; - Детали задачи
/update_status &lt;ID&gt; &lt;статус&gt; - Обновить статус

<b>Создание задачи:</b>
/create_task title:"название" description:"описание" priority:high due_date:2025-12-25 assigned_to:telegram_id"""
    else:
        text = """📋 <b>Доступные команды (Сотрудник):</b>

/start - Приветствие
/help - Список команд
/my_tasks - Мои задачи
/task_details &lt;ID&gt; - Детали задачи
/update_status &lt;ID&gt; &lt;статус&gt; - Обновить статус

<b>Статусы:</b> pending, in_progress, completed, rejected"""
    
    await message.answer(text, parse_mode='HTML')


@dp.message(Command('my_tasks', 'мои_задачи'))
async def cmd_my_tasks(message: Message):
    """Обработка команды /my_tasks"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username or message.from_user.first_name
    first_name = message.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """SELECT id, title, status, priority, due_date 
               FROM tasks 
               WHERE assigned_to_id = %s 
               ORDER BY created_at DESC""",
            (user['id'],)
        )
        tasks = cur.fetchall()
        
        if not tasks:
            await message.answer("📋 У вас пока нет задач.")
            return
        
        text = f"📋 <b>Ваши задачи ({len(tasks)}):</b>\n\n"
        
        for task in tasks:
            task_id, title, status, priority, due_date = task
            text += f"""📌 <b>ID {task_id}:</b> {title}
   Статус: {status}
   Приоритет: {priority}
   Срок: {due_date}

"""
        
        await message.answer(text.strip(), parse_mode='HTML')
    
    finally:
        cur.close()
        conn.close()


@dp.message(Command('all_tasks', 'все_задачи'))
async def cmd_all_tasks(message: Message):
    """Обработка команды /all_tasks"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username or message.from_user.first_name
    first_name = message.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    
    if user['role'] != 'admin':
        await message.answer("❌ Только администраторы могут просматривать все задачи.")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """SELECT t.id, t.title, t.status, t.priority, u.id 
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               ORDER BY t.created_at DESC"""
        )
        tasks = cur.fetchall()
        
        if not tasks:
            await message.answer("📋 В системе пока нет задач.")
            return
        
        text = f"📋 <b>Все задачи ({len(tasks)}):</b>\n\n"
        
        for task in tasks:
            task_id, title, status, priority, assigned_user_id = task
            text += f"""📌 <b>ID {task_id}:</b> {title}
   Статус: {status}
   Приоритет: {priority}
   Назначена: User #{assigned_user_id}

"""
        
        await message.answer(text.strip(), parse_mode='HTML')
    
    finally:
        cur.close()
        conn.close()


@dp.message(Command('task_details', 'детали_задачи'))
async def cmd_task_details(message: Message):
    """Обработка команды /task_details"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username or message.from_user.first_name
    first_name = message.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Укажите ID задачи: /task_details 5")
        return
    
    try:
        task_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID задачи должен быть числом.")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """SELECT t.id, t.title, t.description, t.status, t.priority, t.due_date, 
                      t.assigned_to_id, t.created_at
               FROM tasks t
               WHERE t.id = %s""",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            await message.answer(f"❌ Задача #{task_id} не найдена.")
            return
        
        text = f"""📋 <b>Детали задачи #{task[0]}</b>

<b>Название:</b> {task[1]}
<b>Описание:</b> {task[2] or 'Нет описания'}
<b>Статус:</b> {task[3]}
<b>Приоритет:</b> {task[4]}
<b>Срок:</b> {task[5]}
<b>Назначена:</b> User #{task[6]}
<b>Создана:</b> {task[7].strftime('%Y-%m-%d %H:%M')}"""
        
        await message.answer(text, parse_mode='HTML')
    
    finally:
        cur.close()
        conn.close()


@dp.message(Command('update_status', 'обновить_статус'))
async def cmd_update_status(message: Message):
    """Обработка команды /update_status"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username or message.from_user.first_name
    first_name = message.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    
    parts = message.text.split()
    if len(parts) < 3:
        text = """❌ Неверный формат команды.

<b>Использование:</b>
/update_status &lt;ID&gt; &lt;статус&gt;

<b>Статусы:</b> pending, in_progress, completed, rejected

<b>Пример:</b>
/update_status 5 in_progress"""
        await message.answer(text, parse_mode='HTML')
        return
    
    try:
        task_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID задачи должен быть числом.")
        return
    
    new_status = parts[2]
    valid_statuses = ['pending', 'in_progress', 'completed', 'rejected']
    
    if new_status not in valid_statuses:
        await message.answer(f"❌ Некорректный статус. Доступны: {', '.join(valid_statuses)}")
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
            await message.answer(f"❌ Задача #{task_id} не найдена.")
            return
        
        if task[0] != user['id'] and user['role'] != 'admin':
            await message.answer("❌ Вы можете обновлять только свои задачи.")
            return
        
        cur.execute(
            "UPDATE tasks SET status = %s, updated_at = NOW() WHERE id = %s",
            (new_status, task_id)
        )
        conn.commit()
        
        await message.answer(f"✅ Статус задачи #{task_id} обновлён на: <b>{new_status}</b>", parse_mode='HTML')
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating status: {e}")
        await message.answer(f"❌ Ошибка при обновлении статуса: {str(e)}")
    finally:
        cur.close()
        conn.close()


@dp.message(Command('create_task', 'создать_задачу'))
async def cmd_create_task(message: Message):
    """Обработка команды /create_task"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username or message.from_user.first_name
    first_name = message.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    
    if user['role'] != 'admin':
        await message.answer("❌ Только администраторы могут создавать задачи.")
        return
    
    text = message.text
    
    if len(text.split()) < 2:
        help_text = """❌ Необходимо указать параметры задачи.

<b>Использование:</b>
/create_task title:"название" description:"описание" priority:high due_date:2025-12-25 assigned_to:telegram_id

<b>Пример:</b>
/create_task title:"Подготовить отчет" priority:high"""
        await message.answer(help_text, parse_mode='HTML')
        return
    
    import re
    params = {}
    
    title_match = re.search(r'title:"([^"]*)"', text)
    if title_match:
        params['title'] = title_match.group(1)
    
    desc_match = re.search(r'description:"([^"]*)"', text)
    if desc_match:
        params['description'] = desc_match.group(1)
    
    priority_match = re.search(r'priority:(\w+)', text)
    if priority_match:
        params['priority'] = priority_match.group(1)
    
    due_date_match = re.search(r'due_date:(\d{4}-\d{2}-\d{2})', text)
    if due_date_match:
        params['due_date'] = due_date_match.group(1)
    
    assigned_to_match = re.search(r'assigned_to:([^\s]+)', text)
    if assigned_to_match:
        params['assigned_to'] = assigned_to_match.group(1)
    
    if not params.get('title'):
        await message.answer('❌ Необходимо указать название задачи (title:"...")')
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        assigned_to_id = user['id']
        assigned_info = "вам"
        
        if params.get('assigned_to'):
            assigned_telegram_id = params['assigned_to']
            
            if not assigned_telegram_id.isdigit():
                await message.answer(f"❌ Некорректный Telegram ID: {assigned_telegram_id}. Telegram ID должен содержать только цифры.")
                return
            
            logger.info(f"[create_task] Looking up user with Telegram ID: {assigned_telegram_id}")
            
            cur.execute(
                "SELECT id, username FROM users WHERE telegram_id = %s",
                (assigned_telegram_id,)
            )
            assigned_user = cur.fetchone()
            
            if not assigned_user:
                logger.info(f"[create_task] User not found: {assigned_telegram_id}")
                await message.answer(f"❌ Пользователь с Telegram ID {assigned_telegram_id} не найден. Пользователь должен сначала отправить /start боту.")
                return
            
            assigned_to_id = assigned_user[0]
            assigned_info = f"User #{assigned_user[0]} (Telegram ID: {assigned_telegram_id})"
            logger.info(f"[create_task] Found user #{assigned_user[0]} for Telegram ID: {assigned_telegram_id}")
        
        cur.execute(
            """INSERT INTO tasks 
               (title, description, priority, status, due_date, assigned_to_id, created_by_id, created_at, updated_at)
               VALUES (%s, %s, %s, 'pending', %s, %s, %s, NOW(), NOW())
               RETURNING id, title, priority, status""",
            (
                params['title'],
                params.get('description', ''),
                params.get('priority', 'medium'),
                params.get('due_date', datetime.now().strftime('%Y-%m-%d')),
                assigned_to_id,
                user['id']
            )
        )
        conn.commit()
        task = cur.fetchone()
        
        logger.info(f"[create_task] Task #{task[0]} created and assigned to user #{assigned_to_id}")
        
        result_text = f"""✅ <b>Задача создана успешно!</b>

ID: {task[0]}
Название: {task[1]}
Приоритет: {task[2]}
Статус: {task[3]}
Назначена: {assigned_info}"""
        
        await message.answer(result_text, parse_mode='HTML')
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating task: {e}")
        await message.answer(f"❌ Ошибка при создании задачи: {str(e)}")
    finally:
        cur.close()
        conn.close()


async def main():
    """Запуск бота"""
    logger.info("🤖 Starting bot...")
    
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
