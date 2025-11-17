#!/usr/bin/env python3
import os
import logging
import psycopg2
from flask import Flask, request, jsonify
from datetime import datetime
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

def get_db_connection():
    """Создать подключение к PostgreSQL"""
    return psycopg2.connect(DATABASE_URL)

def send_telegram_message(chat_id, text):
    """Отправить сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        logger.info(f"📤 Sent message to chat {chat_id}")
        return response.json()
    except Exception as e:
        logger.error(f"❌ Failed to send message: {e}")
        return None

def get_or_create_user(telegram_id, username, first_name):
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

def handle_start_command(user):
    """Обработка команды /start"""
    return f"""👋 Привет, {user['username']}!

Вы зарегистрированы как: <b>{user['role']}</b>

Используйте /help для списка команд."""

def handle_help_command(user):
    """Обработка команды /help"""
    if user['role'] == 'admin':
        return """📋 <b>Доступные команды (Администратор):</b>

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
        return """📋 <b>Доступные команды (Сотрудник):</b>

/start - Приветствие
/help - Список команд
/my_tasks - Мои задачи
/task_details &lt;ID&gt; - Детали задачи
/update_status &lt;ID&gt; &lt;статус&gt; - Обновить статус

<b>Статусы:</b> pending, in_progress, completed, rejected"""

def parse_task_params(text):
    """Парсинг параметров задачи из текста команды"""
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
    
    return params

def handle_create_task(user, text):
    """Обработка команды /create_task"""
    if user['role'] != 'admin':
        return "❌ Только администраторы могут создавать задачи."
    
    params = parse_task_params(text)
    
    if not params.get('title'):
        return """❌ Необходимо указать название задачи.

<b>Использование:</b>
/create_task title:"название" description:"описание" priority:high due_date:2025-12-25 assigned_to:telegram_id

<b>Пример:</b>
/create_task title:"Подготовить отчет" priority:high"""
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        assigned_to_id = user['id']
        assigned_info = "вам"
        
        if params.get('assigned_to'):
            assigned_telegram_id = params['assigned_to']
            
            if not assigned_telegram_id.isdigit():
                return f"❌ Некорректный Telegram ID: {assigned_telegram_id}. Telegram ID должен содержать только цифры."
            
            logger.info(f"[create_task] Looking up user with Telegram ID: {assigned_telegram_id}")
            
            cur.execute(
                "SELECT id, username FROM users WHERE telegram_id = %s",
                (assigned_telegram_id,)
            )
            assigned_user = cur.fetchone()
            
            if not assigned_user:
                logger.info(f"[create_task] User not found: {assigned_telegram_id}")
                return f"❌ Пользователь с Telegram ID {assigned_telegram_id} не найден. Пользователь должен сначала отправить /start боту."
            
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
        
        return f"""✅ <b>Задача создана успешно!</b>

ID: {task[0]}
Название: {task[1]}
Приоритет: {task[2]}
Статус: {task[3]}
Назначена: {assigned_info}"""
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating task: {e}")
        return f"❌ Ошибка при создании задачи: {str(e)}"
    finally:
        cur.close()
        conn.close()

def handle_my_tasks(user):
    """Обработка команды /my_tasks"""
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
            return "📋 У вас пока нет задач."
        
        response = f"📋 <b>Ваши задачи ({len(tasks)}):</b>\n\n"
        
        for task in tasks:
            task_id, title, status, priority, due_date = task
            response += f"""📌 <b>ID {task_id}:</b> {title}
   Статус: {status}
   Приоритет: {priority}
   Срок: {due_date}

"""
        
        return response.strip()
    
    finally:
        cur.close()
        conn.close()

def handle_all_tasks(user):
    """Обработка команды /all_tasks"""
    if user['role'] != 'admin':
        return "❌ Только администраторы могут просматривать все задачи."
    
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
            return "📋 В системе пока нет задач."
        
        response = f"📋 <b>Все задачи ({len(tasks)}):</b>\n\n"
        
        for task in tasks:
            task_id, title, status, priority, assigned_user_id = task
            response += f"""📌 <b>ID {task_id}:</b> {title}
   Статус: {status}
   Приоритет: {priority}
   Назначена: User #{assigned_user_id}

"""
        
        return response.strip()
    
    finally:
        cur.close()
        conn.close()

def handle_task_details(user, text):
    """Обработка команды /task_details"""
    parts = text.split()
    if len(parts) < 2:
        return "❌ Укажите ID задачи: /task_details 5"
    
    try:
        task_id = int(parts[1])
    except ValueError:
        return "❌ ID задачи должен быть числом."
    
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
            return f"❌ Задача #{task_id} не найдена."
        
        return f"""📋 <b>Детали задачи #{task[0]}</b>

<b>Название:</b> {task[1]}
<b>Описание:</b> {task[2] or 'Нет описания'}
<b>Статус:</b> {task[3]}
<b>Приоритет:</b> {task[4]}
<b>Срок:</b> {task[5]}
<b>Назначена:</b> User #{task[6]}
<b>Создана:</b> {task[7].strftime('%Y-%m-%d %H:%M')}"""
    
    finally:
        cur.close()
        conn.close()

def handle_update_status(user, text):
    """Обработка команды /update_status"""
    parts = text.split()
    if len(parts) < 3:
        return """❌ Неверный формат команды.

<b>Использование:</b>
/update_status &lt;ID&gt; &lt;статус&gt;

<b>Статусы:</b> pending, in_progress, completed, rejected

<b>Пример:</b>
/update_status 5 in_progress"""
    
    try:
        task_id = int(parts[1])
    except ValueError:
        return "❌ ID задачи должен быть числом."
    
    new_status = parts[2]
    valid_statuses = ['pending', 'in_progress', 'completed', 'rejected']
    
    if new_status not in valid_statuses:
        return f"❌ Некорректный статус. Доступны: {', '.join(valid_statuses)}"
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT assigned_to_id FROM tasks WHERE id = %s",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            return f"❌ Задача #{task_id} не найдена."
        
        if task[0] != user['id'] and user['role'] != 'admin':
            return "❌ Вы можете обновлять только свои задачи."
        
        cur.execute(
            "UPDATE tasks SET status = %s, updated_at = NOW() WHERE id = %s",
            (new_status, task_id)
        )
        conn.commit()
        
        return f"✅ Статус задачи #{task_id} обновлён на: <b>{new_status}</b>"
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating status: {e}")
        return f"❌ Ошибка при обновлении статуса: {str(e)}"
    finally:
        cur.close()
        conn.close()

def process_command(telegram_id, username, first_name, text):
    """Обработать команду от пользователя"""
    logger.info(f"🎯 Processing command from {telegram_id}: {text}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    
    text = text.strip()
    command = text.split()[0].lower()
    
    if command in ['/start', '/старт']:
        return handle_start_command(user)
    elif command in ['/help', '/помощь']:
        return handle_help_command(user)
    elif command in ['/create_task', '/создать_задачу']:
        return handle_create_task(user, text)
    elif command in ['/my_tasks', '/мои_задачи']:
        return handle_my_tasks(user)
    elif command in ['/all_tasks', '/все_задачи']:
        return handle_all_tasks(user)
    elif command in ['/task_details', '/детали_задачи']:
        return handle_task_details(user, text)
    elif command in ['/update_status', '/обновить_статус']:
        return handle_update_status(user, text)
    else:
        return f"❌ Неизвестная команда: {command}\n\nИспользуйте /help для списка команд."

@app.route('/webhooks/telegram/action', methods=['POST'])
def telegram_webhook():
    """Обработка webhook от Telegram"""
    try:
        data = request.json
        logger.info(f"📝 Received webhook: {data}")
        
        if 'message' not in data:
            return jsonify({'ok': True})
        
        message = data['message']
        
        if 'text' not in message:
            return jsonify({'ok': True})
        
        telegram_id = str(message['from']['id'])
        username = message['from'].get('username', '')
        first_name = message['from'].get('first_name', '')
        text = message['text']
        chat_id = message['chat']['id']
        
        response_text = process_command(telegram_id, username, first_name, text)
        
        send_telegram_message(chat_id, response_text)
        
        return jsonify({'ok': True})
    
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
