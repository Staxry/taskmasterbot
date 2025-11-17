"""
Notification service for task deadline reminders
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from aiogram import Bot

from app.database import get_db_connection
from app.logging_config import get_logger

logger = get_logger(__name__)


def check_notification_sent(task_id: int, notification_type: str) -> bool:
    """
    Проверить, было ли уже отправлено уведомление
    
    Args:
        task_id: ID задачи
        notification_type: Тип уведомления ('24h', '3h', 'overdue')
    
    Returns:
        bool: True если уведомление уже отправлялось
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT COUNT(*) FROM task_notifications
            WHERE task_id = %s AND notification_type = %s
        """, (task_id, notification_type))
        
        count = cur.fetchone()[0]
        return count > 0
        
    finally:
        cur.close()
        conn.close()


def mark_notification_sent(task_id: int, notification_type: str):
    """
    Отметить уведомление как отправленное
    
    Args:
        task_id: ID задачи
        notification_type: Тип уведомления
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO task_notifications (task_id, notification_type, sent_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (task_id, notification_type) DO NOTHING
        """, (task_id, notification_type))
        
        conn.commit()
        logger.debug(f"✅ Notification marked as sent: task_id={task_id}, type={notification_type}")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error marking notification: {e}", exc_info=True)
    finally:
        cur.close()
        conn.close()


def get_tasks_for_24h_reminder() -> List[Dict[str, Any]]:
    """
    Получить задачи, до срока которых осталось ~24 часа
    
    Returns:
        List задач для уведомления
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT 
                t.id,
                t.title,
                t.description,
                t.priority,
                t.due_date,
                t.assigned_to_id,
                u.telegram_id,
                u.username
            FROM tasks t
            JOIN users u ON t.assigned_to_id = u.id
            WHERE t.status NOT IN ('completed', 'rejected')
            AND t.due_date::timestamp BETWEEN NOW() + INTERVAL '23 hours' AND NOW() + INTERVAL '25 hours'
        """)
        
        tasks = []
        for row in cur.fetchall():
            tasks.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'priority': row[3],
                'due_date': row[4],
                'assigned_to_id': row[5],
                'telegram_id': row[6],
                'username': row[7]
            })
        
        logger.info(f"📋 Found {len(tasks)} tasks for 24h reminder")
        return tasks
        
    finally:
        cur.close()
        conn.close()


def get_tasks_for_3h_reminder() -> List[Dict[str, Any]]:
    """
    Получить задачи, до срока которых осталось ~3 часа
    
    Returns:
        List задач для уведомления
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT 
                t.id,
                t.title,
                t.description,
                t.priority,
                t.due_date,
                t.assigned_to_id,
                u.telegram_id,
                u.username
            FROM tasks t
            JOIN users u ON t.assigned_to_id = u.id
            WHERE t.status NOT IN ('completed', 'rejected')
            AND t.due_date::timestamp BETWEEN NOW() + INTERVAL '2 hours 30 minutes' AND NOW() + INTERVAL '3 hours 30 minutes'
        """)
        
        tasks = []
        for row in cur.fetchall():
            tasks.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'priority': row[3],
                'due_date': row[4],
                'assigned_to_id': row[5],
                'telegram_id': row[6],
                'username': row[7]
            })
        
        logger.info(f"📋 Found {len(tasks)} tasks for 3h reminder")
        return tasks
        
    finally:
        cur.close()
        conn.close()


def get_overdue_tasks() -> List[Dict[str, Any]]:
    """
    Получить просроченные задачи (срок прошёл менее суток назад)
    
    Returns:
        List просроченных задач
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT 
                t.id,
                t.title,
                t.description,
                t.priority,
                t.due_date,
                t.assigned_to_id,
                u.telegram_id,
                u.username
            FROM tasks t
            JOIN users u ON t.assigned_to_id = u.id
            WHERE t.status NOT IN ('completed', 'rejected')
            AND t.due_date < CURRENT_DATE
            AND t.due_date >= CURRENT_DATE - INTERVAL '1 day'
        """)
        
        tasks = []
        for row in cur.fetchall():
            tasks.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'priority': row[3],
                'due_date': row[4],
                'assigned_to_id': row[5],
                'telegram_id': row[6],
                'username': row[7]
            })
        
        logger.info(f"📋 Found {len(tasks)} overdue tasks")
        return tasks
        
    finally:
        cur.close()
        conn.close()


def get_all_admins() -> List[str]:
    """
    Получить telegram_id всех администраторов
    
    Returns:
        List telegram_id админов
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT telegram_id FROM users
            WHERE role = 'admin'
        """)
        
        admins = [row[0] for row in cur.fetchall()]
        logger.debug(f"👥 Found {len(admins)} admins")
        return admins
        
    finally:
        cur.close()
        conn.close()


async def send_24h_reminder(bot: Bot, task: Dict[str, Any]):
    """
    Отправить уведомление за 24 часа до срока
    
    Args:
        bot: Экземпляр Telegram бота
        task: Данные задачи
    """
    if check_notification_sent(task['id'], '24h'):
        logger.debug(f"⏭️ 24h reminder already sent for task {task['id']}")
        return
    
    priority_emoji = {
        'urgent': '🔴',
        'high': '🟠',
        'medium': '🟡',
        'low': '🟢'
    }
    
    emoji = priority_emoji.get(task['priority'], '📌')
    
    description_text = task['description'][:100] if task.get('description') else "Нет описания"
    message = (
        f"⏰ <b>Напоминание о задаче!</b>\n\n"
        f"{emoji} <b>{task['title']}</b>\n"
        f"📝 {description_text}...\n\n"
        f"⏳ <b>Срок: {task['due_date'].strftime('%d.%m.%Y %H:%M')}</b>\n"
        f"⚠️ Осталось <b>~24 часа</b> до дедлайна!\n\n"
        f"Пожалуйста, завершите задачу вовремя."
    )
    
    try:
        await bot.send_message(
            chat_id=task['telegram_id'],
            text=message,
            parse_mode='HTML'
        )
        
        mark_notification_sent(task['id'], '24h')
        logger.info(f"✅ 24h reminder sent to {task['username']} for task #{task['id']}")
        
    except Exception as e:
        logger.error(f"❌ Error sending 24h reminder for task {task['id']}: {e}")


async def send_3h_reminder(bot: Bot, task: Dict[str, Any]):
    """
    Отправить уведомление за 3 часа до срока
    
    Args:
        bot: Экземпляр Telegram бота
        task: Данные задачи
    """
    if check_notification_sent(task['id'], '3h'):
        logger.debug(f"⏭️ 3h reminder already sent for task {task['id']}")
        return
    
    priority_emoji = {
        'urgent': '🔴',
        'high': '🟠',
        'medium': '🟡',
        'low': '🟢'
    }
    
    emoji = priority_emoji.get(task['priority'], '📌')
    
    description_text = task['description'][:100] if task.get('description') else "Нет описания"
    message = (
        f"🚨 <b>СРОЧНО! Задача скоро просрочится!</b>\n\n"
        f"{emoji} <b>{task['title']}</b>\n"
        f"📝 {description_text}...\n\n"
        f"⏳ <b>Срок: {task['due_date'].strftime('%d.%m.%Y %H:%M')}</b>\n"
        f"🔥 Осталось всего <b>~3 часа</b>!\n\n"
        f"⚡ <b>Необходимо срочно завершить задачу!</b>"
    )
    
    try:
        await bot.send_message(
            chat_id=task['telegram_id'],
            text=message,
            parse_mode='HTML'
        )
        
        mark_notification_sent(task['id'], '3h')
        logger.info(f"✅ 3h reminder sent to {task['username']} for task #{task['id']}")
        
    except Exception as e:
        logger.error(f"❌ Error sending 3h reminder for task {task['id']}: {e}")


async def send_overdue_notification(bot: Bot, task: Dict[str, Any]):
    """
    Отправить уведомление админам о просроченной задаче
    
    Args:
        bot: Экземпляр Telegram бота
        task: Данные задачи
    """
    if check_notification_sent(task['id'], 'overdue'):
        logger.debug(f"⏭️ Overdue notification already sent for task {task['id']}")
        return
    
    priority_emoji = {
        'urgent': '🔴',
        'high': '🟠',
        'medium': '🟡',
        'low': '🟢'
    }
    
    emoji = priority_emoji.get(task['priority'], '📌')
    
    due_date_obj = task['due_date'].date() if hasattr(task['due_date'], 'date') else task['due_date']
    days_overdue = (datetime.now().date() - due_date_obj).days
    
    description_text = task['description'][:100] if task.get('description') else "Нет описания"
    message = (
        f"❌ <b>ЗАДАЧА ПРОСРОЧЕНА!</b>\n\n"
        f"{emoji} <b>{task['title']}</b>\n"
        f"📝 {description_text}...\n\n"
        f"👤 Исполнитель: @{task['username']}\n"
        f"⏳ Срок был: {task['due_date'].strftime('%d.%m.%Y %H:%M')}\n"
        f"⚠️ Просрочено на <b>{days_overdue} дн.</b>\n\n"
        f"Требуется проверка и контроль выполнения."
    )
    
    admins = get_all_admins()
    
    for admin_telegram_id in admins:
        try:
            await bot.send_message(
                chat_id=admin_telegram_id,
                text=message,
                parse_mode='HTML'
            )
            logger.info(f"✅ Overdue notification sent to admin {admin_telegram_id} for task #{task['id']}")
            
        except Exception as e:
            logger.error(f"❌ Error sending overdue notification to admin {admin_telegram_id}: {e}")
    
    mark_notification_sent(task['id'], 'overdue')


async def check_and_send_notifications(bot: Bot):
    """
    Проверить все задачи и отправить необходимые уведомления
    
    Args:
        bot: Экземпляр Telegram бота
    """
    logger.info("🔔 Starting notification check cycle...")
    
    try:
        # Уведомления за 24 часа
        tasks_24h = get_tasks_for_24h_reminder()
        for task in tasks_24h:
            await send_24h_reminder(bot, task)
            await asyncio.sleep(0.5)  # Небольшая задержка между отправками
        
        # Уведомления за 3 часа
        tasks_3h = get_tasks_for_3h_reminder()
        for task in tasks_3h:
            await send_3h_reminder(bot, task)
            await asyncio.sleep(0.5)
        
        # Уведомления о просроченных задачах
        overdue_tasks = get_overdue_tasks()
        for task in overdue_tasks:
            await send_overdue_notification(bot, task)
            await asyncio.sleep(0.5)
        
        logger.info(f"✅ Notification check completed: 24h={len(tasks_24h)}, 3h={len(tasks_3h)}, overdue={len(overdue_tasks)}")
        
    except Exception as e:
        logger.error(f"❌ Error in notification check cycle: {e}", exc_info=True)


async def notification_scheduler(bot: Bot):
    """
    Фоновая задача для периодической проверки уведомлений
    Проверка каждые 30 минут
    
    Args:
        bot: Экземпляр Telegram бота
    """
    logger.info("🔔 Notification scheduler started (check every 30 minutes)")
    
    while True:
        try:
            await check_and_send_notifications(bot)
            await asyncio.sleep(1800)  # 30 минут = 1800 секунд
            
        except Exception as e:
            logger.error(f"❌ Error in notification scheduler: {e}", exc_info=True)
            await asyncio.sleep(300)  # При ошибке пауза 5 минут
