"""
Notification settings service
Управление персональными настройками уведомлений пользователей
"""
from typing import Optional, Dict, Any
from datetime import datetime, time
from app.database import get_db_connection
from app.logging_config import get_logger

logger = get_logger(__name__)


def get_user_notification_settings(user_id: int) -> Dict[str, Any]:
    """
    Получить настройки уведомлений пользователя
    
    Args:
        user_id: ID пользователя
    
    Returns:
        Dict с настройками уведомлений
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT * FROM user_notification_settings
            WHERE user_id = ?
        """, (user_id,))
        
        settings = cur.fetchone()
        
        if not settings:
            # Создаём настройки по умолчанию
            return create_default_settings(user_id)
        
        return {
            'user_id': settings['user_id'],
            'enable_24h_reminder': bool(settings['enable_24h_reminder']),
            'enable_3h_reminder': bool(settings['enable_3h_reminder']),
            'enable_1h_reminder': bool(settings['enable_1h_reminder']),
            'enable_overdue_notifications': bool(settings['enable_overdue_notifications']),
            'enable_comment_notifications': bool(settings['enable_comment_notifications']),
            'quiet_hours_start': settings['quiet_hours_start'],
            'quiet_hours_end': settings['quiet_hours_end'],
            'custom_reminder_intervals': settings['custom_reminder_intervals']
        }
        
    finally:
        cur.close()
        conn.close()


def create_default_settings(user_id: int) -> Dict[str, Any]:
    """
    Создать настройки по умолчанию для пользователя
    
    Args:
        user_id: ID пользователя
    
    Returns:
        Dict с настройками по умолчанию
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO user_notification_settings 
            (user_id, enable_24h_reminder, enable_3h_reminder, enable_1h_reminder,
             enable_overdue_notifications, enable_comment_notifications,
             quiet_hours_start, quiet_hours_end)
            VALUES (?, 1, 1, 1, 1, 1, '22:00', '08:00')
        """, (user_id,))
        
        conn.commit()
        
        logger.info(f"✅ Created default notification settings for user {user_id}")
        
        return {
            'user_id': user_id,
            'enable_24h_reminder': True,
            'enable_3h_reminder': True,
            'enable_1h_reminder': True,
            'enable_overdue_notifications': True,
            'enable_comment_notifications': True,
            'quiet_hours_start': '22:00',
            'quiet_hours_end': '08:00',
            'custom_reminder_intervals': None
        }
        
    finally:
        cur.close()
        conn.close()


def update_notification_setting(user_id: int, setting_name: str, value: Any):
    """
    Обновить конкретную настройку уведомлений
    
    Args:
        user_id: ID пользователя
        setting_name: Название настройки
        value: Новое значение
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Убеждаемся, что настройки существуют
        get_user_notification_settings(user_id)
        
        cur.execute(f"""
            UPDATE user_notification_settings
            SET {setting_name} = ?, updated_at = datetime('now')
            WHERE user_id = ?
        """, (value, user_id))
        
        conn.commit()
        
        logger.info(f"✅ Updated {setting_name} for user {user_id} to {value}")
        
    finally:
        cur.close()
        conn.close()


def is_quiet_hours(user_id: int) -> bool:
    """
    Проверить, находятся ли мы в тихих часах пользователя
    
    Args:
        user_id: ID пользователя
    
    Returns:
        bool: True если сейчас тихие часы
    """
    from app.config import get_now
    
    settings = get_user_notification_settings(user_id)
    now = get_now()
    current_time = now.time()
    
    start_time = datetime.strptime(settings['quiet_hours_start'], '%H:%M').time()
    end_time = datetime.strptime(settings['quiet_hours_end'], '%H:%M').time()
    
    # Если тихие часы переходят через полночь
    if start_time > end_time:
        return current_time >= start_time or current_time < end_time
    else:
        return start_time <= current_time < end_time


def should_send_notification(user_id: int, notification_type: str) -> bool:
    """
    Проверить, нужно ли отправлять уведомление пользователю
    
    Args:
        user_id: ID пользователя
        notification_type: Тип уведомления ('24h', '3h', '1h', 'overdue', 'comment')
    
    Returns:
        bool: True если нужно отправить уведомление
    """
    settings = get_user_notification_settings(user_id)
    
    # Проверяем тихие часы
    if is_quiet_hours(user_id):
        logger.debug(f"🔇 User {user_id} is in quiet hours, skipping notification")
        return False
    
    # Проверяем настройки для конкретного типа уведомления
    setting_map = {
        '24h': 'enable_24h_reminder',
        '3h': 'enable_3h_reminder',
        '1h': 'enable_1h_reminder',
        'overdue': 'enable_overdue_notifications',
        'comment': 'enable_comment_notifications'
    }
    
    setting_key = setting_map.get(notification_type)
    if setting_key:
        return settings.get(setting_key, True)
    
    return True

