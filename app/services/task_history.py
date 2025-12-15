"""
Task history service
Управление историей изменений задач
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.database import get_db_connection
from app.logging_config import get_logger

logger = get_logger(__name__)


def add_task_history_entry(
    task_id: int,
    user_id: int,
    change_type: str,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None
):
    """
    Добавить запись в историю изменений задачи
    
    Args:
        task_id: ID задачи
        user_id: ID пользователя, который внёс изменение
        change_type: Тип изменения ('status', 'priority', 'assignee', 'due_date', 'title', 'description', 'created', 'reopened')
        old_value: Старое значение
        new_value: Новое значение
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO task_history (task_id, user_id, change_type, old_value, new_value)
            VALUES (?, ?, ?, ?, ?)
        """, (task_id, user_id, change_type, old_value, new_value))
        
        conn.commit()
        
        logger.debug(f"📝 Added history entry for task #{task_id}: {change_type} ({old_value} -> {new_value})")
        
    except Exception as e:
        logger.error(f"❌ Error adding task history entry: {e}", exc_info=True)
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def get_task_history(task_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Получить историю изменений задачи
    
    Args:
        task_id: ID задачи
        limit: Максимальное количество записей
    
    Returns:
        List записей истории
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT 
                th.id,
                th.change_type,
                th.old_value,
                th.new_value,
                th.created_at,
                u.username,
                u.first_name,
                u.last_name
            FROM task_history th
            JOIN users u ON th.user_id = u.id
            WHERE th.task_id = ?
            ORDER BY th.created_at DESC
            LIMIT ?
        """, (task_id, limit))
        
        history = cur.fetchall()
        
        return history
        
    finally:
        cur.close()
        conn.close()


def format_history_entry(entry: Dict[str, Any]) -> str:
    """
    Форматировать запись истории для отображения
    
    Args:
        entry: Запись истории
    
    Returns:
        str: Отформатированная строка
    """
    change_type = entry['change_type']
    old_value = entry.get('old_value')
    new_value = entry.get('new_value')
    username = entry.get('username', 'Неизвестно')
    first_name = entry.get('first_name')
    last_name = entry.get('last_name')
    created_at = entry.get('created_at')
    
    # Форматируем имя пользователя
    if first_name or last_name:
        user_display = f"{first_name or ''} {last_name or ''}".strip() + f" (@{username})"
    else:
        user_display = f"@{username}"
    
    # Форматируем дату
    if isinstance(created_at, datetime):
        date_str = created_at.strftime('%d.%m.%Y %H:%M')
    elif isinstance(created_at, str):
        try:
            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            date_str = dt.strftime('%d.%m.%Y %H:%M')
        except:
            date_str = str(created_at)
    else:
        date_str = str(created_at)
    
    # Форматируем тип изменения
    type_labels = {
        'status': 'Статус',
        'priority': 'Приоритет',
        'assignee': 'Исполнитель',
        'due_date': 'Срок выполнения',
        'title': 'Название',
        'description': 'Описание',
        'created': 'Создана',
        'reopened': 'Возвращена в работу',
        'comment': 'Комментарий'
    }
    
    type_label = type_labels.get(change_type, change_type)
    
    # Форматируем значения
    if change_type == 'status':
        status_map = {
            'pending': '⏳ Ожидает',
            'in_progress': '🔄 В работе',
            'partially_completed': '🔶 Частично завершена',
            'completed': '✅ Завершена',
            'rejected': '❌ Отклонена'
        }
        old_display = status_map.get(old_value, old_value) if old_value else None
        new_display = status_map.get(new_value, new_value) if new_value else None
    elif change_type == 'priority':
        priority_map = {
            'urgent': '🔴 Срочно',
            'high': '🟠 Высокий',
            'medium': '🟡 Средний',
            'low': '🟢 Низкий'
        }
        old_display = priority_map.get(old_value, old_value) if old_value else None
        new_display = priority_map.get(new_value, new_value) if new_value else None
    else:
        old_display = old_value
        new_display = new_value
    
    # Формируем строку
    if change_type in ('created', 'reopened'):
        return f"📅 {date_str} | {user_display}\n{type_label}"
    elif old_value and new_value:
        return f"📅 {date_str} | {user_display}\n{type_label}: {old_display} → {new_display}"
    elif new_value:
        return f"📅 {date_str} | {user_display}\n{type_label}: {new_display}"
    else:
        return f"📅 {date_str} | {user_display}\n{type_label}"

