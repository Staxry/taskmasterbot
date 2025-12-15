"""
Notification service for task deadline reminders
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from aiogram import Bot

from app.database import get_db_connection
from app.logging_config import get_logger
from app.config import get_now, TIMEZONE
from app.services.notification_settings import should_send_notification

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
            SELECT COUNT(*) as count FROM task_notifications
            WHERE task_id = ? AND notification_type = ?
        """, (task_id, notification_type))
        
        result = cur.fetchone()
        count = result['count'] if result else 0
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
            INSERT OR IGNORE INTO task_notifications (task_id, notification_type, sent_at)
            VALUES (?, ?, datetime('now'))
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
    Получить задачи, до срока которых осталось ~8 часов
    Проверка времени выполняется в Python с учётом timezone
    
    Returns:
        List задач для уведомления
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Загружаем все активные задачи
        cur.execute("""
            SELECT 
                t.id,
                t.title,
                t.description,
                t.priority,
                t.due_date,
                t.assigned_to_id,
                u.telegram_id,
                u.username,
                u.first_name,
                u.last_name
            FROM tasks t
            JOIN users u ON t.assigned_to_id = u.id
            WHERE t.status NOT IN ('completed', 'partially_completed', 'rejected')
            AND t.due_date IS NOT NULL
        """)
        
        all_tasks = cur.fetchall()
        
        # Фильтруем задачи с дедлайном ~8 часов в Python с учётом timezone
        now = get_now()
        reminder_tasks = []
        
        for task in all_tasks:
            due_date = task['due_date']
            if isinstance(due_date, datetime):
                # Приводим к timezone-aware datetime если нужно
                if due_date.tzinfo is None:
                    due_date = TIMEZONE.localize(due_date)
                
                # Проверяем: до дедлайна осталось от 7 до 9 часов
                time_until = due_date - now
                hours_until = time_until.total_seconds() / 3600
                
                if 7 <= hours_until <= 9:
                    reminder_tasks.append(task)
        
        logger.info(f"📋 Found {len(reminder_tasks)} tasks for 8h reminder (checked {len(all_tasks)} active tasks)")
        return reminder_tasks
        
    finally:
        cur.close()
        conn.close()


def get_tasks_for_3h_reminder() -> List[Dict[str, Any]]:
    """
    Получить задачи, до срока которых осталось ~4 часа
    Проверка времени выполняется в Python с учётом timezone
    
    Returns:
        List задач для уведомления
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Загружаем все активные задачи
        cur.execute("""
            SELECT 
                t.id,
                t.title,
                t.description,
                t.priority,
                t.due_date,
                t.assigned_to_id,
                u.telegram_id,
                u.username,
                u.first_name,
                u.last_name
            FROM tasks t
            JOIN users u ON t.assigned_to_id = u.id
            WHERE t.status NOT IN ('completed', 'partially_completed', 'rejected')
            AND t.due_date IS NOT NULL
        """)
        
        all_tasks = cur.fetchall()
        
        # Фильтруем задачи с дедлайном ~4 часа в Python с учётом timezone
        now = get_now()
        reminder_tasks = []
        
        for task in all_tasks:
            due_date = task['due_date']
            if isinstance(due_date, datetime):
                # Приводим к timezone-aware datetime если нужно
                if due_date.tzinfo is None:
                    due_date = TIMEZONE.localize(due_date)
                
                # Проверяем: до дедлайна осталось от 3.5 до 4.5 часов
                time_until = due_date - now
                hours_until = time_until.total_seconds() / 3600
                
                if 3.5 <= hours_until <= 4.5:
                    reminder_tasks.append(task)
        
        logger.info(f"📋 Found {len(reminder_tasks)} tasks for 4h reminder (checked {len(all_tasks)} active tasks)")
        return reminder_tasks
        
    finally:
        cur.close()
        conn.close()


def get_tasks_for_1h_reminder() -> List[Dict[str, Any]]:
    """
    Получить задачи, до срока которых осталось меньше 1 часа
    В последний час уведомления отправляются каждые 10 минут
    Проверка времени выполняется в Python с учётом timezone
    
    Returns:
        List задач для уведомления
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Загружаем все активные задачи
        cur.execute("""
            SELECT 
                t.id,
                t.title,
                t.description,
                t.priority,
                t.due_date,
                t.assigned_to_id,
                u.telegram_id,
                u.username,
                u.first_name,
                u.last_name
            FROM tasks t
            JOIN users u ON t.assigned_to_id = u.id
            WHERE t.status NOT IN ('completed', 'partially_completed', 'rejected')
            AND t.due_date IS NOT NULL
        """)
        
        all_tasks = cur.fetchall()
        
        # Фильтруем задачи с дедлайном в течение последнего часа
        now = get_now()
        reminder_tasks = []
        
        for task in all_tasks:
            due_date = task['due_date']
            if isinstance(due_date, datetime):
                # Приводим к timezone-aware datetime если нужно
                if due_date.tzinfo is None:
                    due_date = TIMEZONE.localize(due_date)
                
                # Проверяем: до дедлайна осталось от 1 минуты до 60 минут
                time_until = due_date - now
                minutes_until = time_until.total_seconds() / 60
                
                # В последний час отправляем уведомления постоянно (каждые 10 минут)
                if 1 <= minutes_until <= 60:
                    reminder_tasks.append(task)
        
        logger.info(f"📋 Found {len(reminder_tasks)} tasks for final hour alerts (checked {len(all_tasks)} active tasks)")
        return reminder_tasks
        
    finally:
        cur.close()
        conn.close()


def get_overdue_tasks() -> List[Dict[str, Any]]:
    """
    Получить просроченные задачи (срок прошёл менее суток назад)
    Проверка времени выполняется в Python с учётом timezone
    
    Returns:
        List просроченных задач
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Загружаем все активные задачи
        cur.execute("""
            SELECT 
                t.id,
                t.title,
                t.description,
                t.priority,
                t.due_date,
                t.assigned_to_id,
                u.telegram_id,
                u.username,
                u.first_name,
                u.last_name
            FROM tasks t
            JOIN users u ON t.assigned_to_id = u.id
            WHERE t.status NOT IN ('completed', 'partially_completed', 'rejected')
            AND t.due_date IS NOT NULL
        """)
        
        all_tasks = cur.fetchall()
        
        # Фильтруем просроченные задачи в Python с учётом timezone
        now = get_now()
        overdue_tasks = []
        
        for task in all_tasks:
            due_date = task['due_date']
            # Приводим к timezone-aware datetime если нужно
            if isinstance(due_date, datetime):
                if due_date.tzinfo is None:
                    due_date = TIMEZONE.localize(due_date)
                
                # Задача просрочена, если дедлайн прошёл и прошло меньше суток
                time_diff = now - due_date
                if time_diff.total_seconds() > 0 and time_diff.days < 1:
                    overdue_tasks.append(task)
        
        logger.info(f"📋 Found {len(overdue_tasks)} overdue tasks (checked {len(all_tasks)} active tasks)")
        return overdue_tasks
        
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
        
        admins = [row['telegram_id'] for row in cur.fetchall()]
        logger.debug(f"👥 Found {len(admins)} admins")
        return admins
        
    finally:
        cur.close()
        conn.close()


async def send_24h_reminder(bot: Bot, task: Dict[str, Any]):
    """
    Отправить уведомление за 8 часов до срока
    
    Args:
        bot: Экземпляр Telegram бота
        task: Данные задачи
    """
    if check_notification_sent(task['id'], '24h'):
        logger.debug(f"⏭️ 8h reminder already sent for task {task['id']}")
        return
    
    # Проверяем персональные настройки пользователя
    if not should_send_notification(task['assigned_to_id'], '24h'):
        logger.debug(f"⏭️ 8h reminder disabled for user {task['assigned_to_id']}")
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
        f"⚠️ Осталось <b>~8 часов</b> до дедлайна!\n\n"
        f"Пожалуйста, завершите задачу вовремя."
    )
    
    try:
        await bot.send_message(
            chat_id=task['telegram_id'],
            text=message,
            parse_mode='HTML'
        )
        
        mark_notification_sent(task['id'], '24h')
        logger.info(f"✅ 8h reminder sent to {task['username']} for task #{task['id']}")
        
    except Exception as e:
        logger.error(f"❌ Error sending 8h reminder for task {task['id']}: {e}")


async def send_3h_reminder(bot: Bot, task: Dict[str, Any]):
    """
    Отправить уведомление за 4 часа до срока
    
    Args:
        bot: Экземпляр Telegram бота
        task: Данные задачи
    """
    if check_notification_sent(task['id'], '3h'):
        logger.debug(f"⏭️ 4h reminder already sent for task {task['id']}")
        return
    
    # Проверяем персональные настройки пользователя
    if not should_send_notification(task['assigned_to_id'], '3h'):
        logger.debug(f"⏭️ 4h reminder disabled for user {task['assigned_to_id']}")
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
        f"🔥 Осталось всего <b>~4 часа</b>!\n\n"
        f"⚡ <b>Необходимо срочно завершить задачу!</b>"
    )
    
    try:
        await bot.send_message(
            chat_id=task['telegram_id'],
            text=message,
            parse_mode='HTML'
        )
        
        mark_notification_sent(task['id'], '3h')
        logger.info(f"✅ 4h reminder sent to {task['username']} for task #{task['id']}")
        
    except Exception as e:
        logger.error(f"❌ Error sending 4h reminder for task {task['id']}: {e}")


async def send_1h_reminder(bot: Bot, task: Dict[str, Any]):
    """
    Отправить срочное уведомление в последний час
    Отправляется каждые 10 минут без проверки дубликатов
    
    Args:
        bot: Экземпляр Telegram бота
        task: Данные задачи
    """
    # Проверяем персональные настройки пользователя
    if not should_send_notification(task['assigned_to_id'], '1h'):
        logger.debug(f"⏭️ 1h reminder disabled for user {task['assigned_to_id']}")
        return
    priority_emoji = {
        'urgent': '🔴',
        'high': '🟠',
        'medium': '🟡',
        'low': '🟢'
    }
    
    emoji = priority_emoji.get(task['priority'], '📌')
    
    # Вычисляем точное время до дедлайна
    due_date = task['due_date']
    if due_date.tzinfo is None:
        due_date = TIMEZONE.localize(due_date)
    now = get_now()
    time_remaining = due_date - now
    minutes_remaining = int(time_remaining.total_seconds() / 60)
    
    description_text = task['description'][:100] if task.get('description') else "Нет описания"
    message = (
        f"🚨 <b>СРОЧНО! ПОСЛЕДНИЙ ЧАС!</b>\n\n"
        f"{emoji} <b>{task['title']}</b>\n"
        f"📝 {description_text}...\n\n"
        f"⏳ <b>Дедлайн: {task['due_date'].strftime('%d.%m.%Y %H:%M')}</b>\n"
        f"⏱ Осталось: <b>{minutes_remaining} мин</b>\n\n"
        f"⚡ <b>СРОЧНО ЗАВЕРШИТЕ ЗАДАЧУ!</b>"
    )
    
    try:
        await bot.send_message(
            chat_id=task['telegram_id'],
            text=message,
            parse_mode='HTML'
        )
        
        logger.info(f"⚡ Final hour alert sent to {task['username']} for task #{task['id']} ({minutes_remaining} min remaining)")
        
    except Exception as e:
        logger.error(f"❌ Error sending final hour alert for task {task['id']}: {e}")


async def send_overdue_notification(bot: Bot, task: Dict[str, Any]):
    """
    Отправить уведомление о просроченной задаче исполнителю и админам
    
    Args:
        bot: Экземпляр Telegram бота
        task: Данные задачи
    """
    if check_notification_sent(task['id'], 'overdue'):
        logger.debug(f"⏭️ Overdue notification already sent for task {task['id']}")
        return
    
    # Проверяем персональные настройки пользователя
    if not should_send_notification(task['assigned_to_id'], 'overdue'):
        logger.debug(f"⏭️ Overdue notification disabled for user {task['assigned_to_id']}")
        return
    
    priority_emoji = {
        'urgent': '🔴',
        'high': '🟠',
        'medium': '🟡',
        'low': '🟢'
    }
    
    emoji = priority_emoji.get(task['priority'], '📌')
    
    # Конвертируем due_date в часовой пояс приложения для корректного отображения
    due_date_aware = task['due_date'] if task['due_date'].tzinfo else TIMEZONE.localize(task['due_date'])
    now_aware = get_now()
    days_overdue = (now_aware.date() - due_date_aware.date()).days
    
    # Форматируем имя исполнителя
    if task.get('first_name') or task.get('last_name'):
        executor_display = f"{task.get('first_name', '') or ''} {task.get('last_name', '') or ''}".strip() + f" (@{task['username']})"
    else:
        executor_display = f"@{task['username']}"
    
    description_text = task['description'][:100] if task.get('description') else "Нет описания"
    
    # Сообщение для исполнителя
    message_executor = (
        f"❌ <b>ЗАДАЧА ПРОСРОЧЕНА!</b>\n\n"
        f"{emoji} <b>{task['title']}</b>\n"
        f"📝 {description_text}...\n\n"
        f"⏳ Срок был: {task['due_date'].strftime('%d.%m.%Y %H:%M')}\n"
        f"⚠️ Просрочено на <b>{days_overdue} дн.</b>\n\n"
        f"⚡ <b>СРОЧНО завершите задачу!</b>"
    )
    
    # Сообщение для админов (с информацией об исполнителе)
    message_admin = (
        f"❌ <b>ЗАДАЧА ПРОСРОЧЕНА!</b>\n\n"
        f"{emoji} <b>{task['title']}</b>\n"
        f"📝 {description_text}...\n\n"
        f"👤 Исполнитель: {executor_display}\n"
        f"⏳ Срок был: {task['due_date'].strftime('%d.%m.%Y %H:%M')}\n"
        f"⚠️ Просрочено на <b>{days_overdue} дн.</b>\n\n"
        f"Требуется проверка и контроль выполнения."
    )
    
    # Отправляем исполнителю
    try:
        await bot.send_message(
            chat_id=task['telegram_id'],
            text=message_executor,
            parse_mode='HTML'
        )
        logger.info(f"✅ Overdue notification sent to executor {task['username']} for task #{task['id']}")
        
    except Exception as e:
        logger.error(f"❌ Error sending overdue notification to executor {task['username']}: {e}")
    
    # Отправляем админам
    admins = get_all_admins()
    
    for admin_telegram_id in admins:
        try:
            await bot.send_message(
                chat_id=admin_telegram_id,
                text=message_admin,
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
        # Уведомления за 8 часов
        tasks_24h = get_tasks_for_24h_reminder()
        for task in tasks_24h:
            await send_24h_reminder(bot, task)
            await asyncio.sleep(0.5)  # Небольшая задержка между отправками
        
        # Уведомления за 4 часа
        tasks_3h = get_tasks_for_3h_reminder()
        for task in tasks_3h:
            await send_3h_reminder(bot, task)
            await asyncio.sleep(0.5)
        
        # Уведомления за 1 час
        tasks_1h = get_tasks_for_1h_reminder()
        for task in tasks_1h:
            await send_1h_reminder(bot, task)
            await asyncio.sleep(0.5)
        
        # Уведомления о просроченных задачах
        overdue_tasks = get_overdue_tasks()
        for task in overdue_tasks:
            await send_overdue_notification(bot, task)
            await asyncio.sleep(0.5)
        
        logger.info(f"✅ Notification check completed: 8h={len(tasks_24h)}, 4h={len(tasks_3h)}, 1h={len(tasks_1h)}, overdue={len(overdue_tasks)}")
        
    except Exception as e:
        logger.error(f"❌ Error in notification check cycle: {e}", exc_info=True)


async def notification_scheduler(bot: Bot):
    """
    Фоновая задача для периодической проверки уведомлений
    Проверка каждые 10 минут
    
    Args:
        bot: Экземпляр Telegram бота
    """
    logger.info("🔔 Notification scheduler started (check every 10 minutes)")
    
    while True:
        try:
            await check_and_send_notifications(bot)
            await asyncio.sleep(600)  # 10 минут = 600 секунд
            
        except Exception as e:
            logger.error(f"❌ Error in notification scheduler: {e}", exc_info=True)
            await asyncio.sleep(60)  # При ошибке пауза 1 минута
