"""
Task comments service
Управление комментариями к задачам
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import re
from app.database import get_db_connection
from app.logging_config import get_logger
from app.services.notification_settings import should_send_notification

logger = get_logger(__name__)


def add_comment(
    task_id: int,
    user_id: int,
    comment_text: str
) -> int:
    """
    Добавить комментарий к задаче
    
    Args:
        task_id: ID задачи
        user_id: ID пользователя
        comment_text: Текст комментария
    
    Returns:
        int: ID созданного комментария
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO task_comments (task_id, user_id, comment_text)
            VALUES (?, ?, ?)
        """, (task_id, user_id, comment_text))
        
        comment_id = cur.lastrowid
        
        # Обрабатываем упоминания
        mentioned_usernames = extract_mentions(comment_text)
        if mentioned_usernames:
            add_mentions(comment_id, mentioned_usernames)
        
        conn.commit()
        
        logger.info(f"💬 Comment #{comment_id} added to task #{task_id} by user {user_id}")
        
        return comment_id
        
    except Exception as e:
        logger.error(f"❌ Error adding comment: {e}", exc_info=True)
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def extract_mentions(text: str) -> List[str]:
    """
    Извлечь упоминания пользователей из текста (@username)
    
    Args:
        text: Текст комментария
    
    Returns:
        List упоминаний (username без @)
    """
    # Ищем паттерн @username
    pattern = r'@(\w+)'
    mentions = re.findall(pattern, text)
    
    return list(set(mentions))  # Убираем дубликаты


def add_mentions(comment_id: int, usernames: List[str]):
    """
    Добавить упоминания пользователей к комментарию
    
    Args:
        comment_id: ID комментария
        usernames: Список username (без @)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        for username in usernames:
            # Находим ID пользователя по username
            cur.execute("SELECT id FROM users WHERE username = ?", (username,))
            user = cur.fetchone()
            
            if user:
                user_id = user['id']
                try:
                    cur.execute("""
                        INSERT INTO comment_mentions (comment_id, mentioned_user_id)
                        VALUES (?, ?)
                    """, (comment_id, user_id))
                    logger.debug(f"✅ Added mention: @{username} in comment #{comment_id}")
                except Exception:
                    # Уже существует
                    pass
        
        conn.commit()
        
    finally:
        cur.close()
        conn.close()


def get_task_comments(task_id: int) -> List[Dict[str, Any]]:
    """
    Получить все комментарии к задаче
    
    Args:
        task_id: ID задачи
    
    Returns:
        List комментариев
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT 
                tc.id,
                tc.comment_text,
                tc.created_at,
                tc.updated_at,
                u.id as user_id,
                u.username,
                u.first_name,
                u.last_name
            FROM task_comments tc
            JOIN users u ON tc.user_id = u.id
            WHERE tc.task_id = ?
            ORDER BY tc.created_at ASC
        """, (task_id,))
        
        comments = cur.fetchall()
        
        # Получаем файлы для каждого комментария
        for comment in comments:
            cur.execute("""
                SELECT file_id, file_type, file_name
                FROM comment_files
                WHERE comment_id = ?
                ORDER BY created_at ASC
            """, (comment['id'],))
            
            comment['files'] = cur.fetchall()
            
            # Получаем упоминания
            cur.execute("""
                SELECT u.username, u.first_name, u.last_name
                FROM comment_mentions cm
                JOIN users u ON cm.mentioned_user_id = u.id
                WHERE cm.comment_id = ?
            """, (comment['id'],))
            
            comment['mentions'] = cur.fetchall()
        
        return comments
        
    finally:
        cur.close()
        conn.close()


def add_comment_file(
    comment_id: int,
    file_id: str,
    file_type: str,
    file_name: Optional[str] = None
):
    """
    Добавить файл к комментарию
    
    Args:
        comment_id: ID комментария
        file_id: ID файла в Telegram
        file_type: Тип файла ('photo', 'document', 'video', 'audio', 'voice')
        file_name: Имя файла (опционально)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO comment_files (comment_id, file_id, file_type, file_name)
            VALUES (?, ?, ?, ?)
        """, (comment_id, file_id, file_type, file_name))
        
        conn.commit()
        
        logger.info(f"📎 File added to comment #{comment_id}: {file_type}")
        
    except Exception as e:
        logger.error(f"❌ Error adding file to comment: {e}", exc_info=True)
        conn.rollback()
    finally:
        cur.close()
        conn.close()


async def notify_mentioned_users(comment_id: int, task_id: int, bot):
    """
    Отправить уведомления упомянутым пользователям
    
    Args:
        comment_id: ID комментария
        task_id: ID задачи
        bot: Экземпляр бота
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Получаем информацию о комментарии и задаче
        cur.execute("""
            SELECT tc.comment_text, tc.user_id, u.username as author_username,
                   u.first_name as author_first_name, u.last_name as author_last_name,
                   t.title as task_title
            FROM task_comments tc
            JOIN users u ON tc.user_id = u.id
            JOIN tasks t ON tc.task_id = t.id
            WHERE tc.id = ?
        """, (comment_id,))
        
        comment_data = cur.fetchone()
        if not comment_data:
            return
        
        # Получаем упомянутых пользователей
        cur.execute("""
            SELECT u.id, u.telegram_id, u.username, u.first_name, u.last_name
            FROM comment_mentions cm
            JOIN users u ON cm.mentioned_user_id = u.id
            WHERE cm.comment_id = ?
        """, (comment_id,))
        
        mentioned_users = cur.fetchall()
        
        # Форматируем имя автора
        author = comment_data
        if author['author_first_name'] or author['author_last_name']:
            author_display = f"{author['author_first_name'] or ''} {author['author_last_name'] or ''}".strip() + f" (@{author['author_username']})"
        else:
            author_display = f"@{author['author_username']}"
        
        # Отправляем уведомления
        for user in mentioned_users:
            if should_send_notification(user['id'], 'comment'):
                try:
                    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                    
                    message = (
                        f"💬 <b>Вас упомянули в комментарии к задаче!</b>\n\n"
                        f"📋 <b>Задача #{task_id}:</b> {comment_data['task_title']}\n"
                        f"👤 <b>Автор:</b> {author_display}\n\n"
                        f"💬 <b>Комментарий:</b>\n{comment_data['comment_text'][:200]}"
                    )
                    
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📂 Открыть задачу", callback_data=f"task_{task_id}")]
                    ])
                    
                    await bot.send_message(
                        chat_id=user['telegram_id'],
                        text=message,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                    
                    logger.info(f"✅ Comment notification sent to @{user['username']}")
                    
                except Exception as e:
                    logger.error(f"❌ Error sending comment notification: {e}")
        
    finally:
        cur.close()
        conn.close()

