"""
User-related keyboards
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.database import get_db_connection
from app.logging_config import get_logger

logger = get_logger(__name__)


def get_users_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора исполнителя из списка пользователей
    
    Returns:
        InlineKeyboardMarkup: Клавиатура со списком пользователей
    """
    logger.debug("🎹 Generating users keyboard")
    
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
        
        buttons.append([InlineKeyboardButton(text="📭 Не назначать исполнителя", callback_data="assignee_none")])
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
        
        logger.debug(f"✅ Generated users keyboard with {len(users)} users")
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    finally:
        cur.close()
        conn.close()


def get_remove_user_keyboard(role: str) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора пользователя для удаления
    
    Args:
        role: Роль пользователей для отображения ('admin' или 'employee')
    
    Returns:
        InlineKeyboardMarkup: Клавиатура со списком пользователей для удаления
    """
    logger.debug(f"🎹 Generating remove user keyboard for role: {role}")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """SELECT username FROM allowed_users 
               WHERE role = %s
               ORDER BY username ASC""",
            (role,)
        )
        users = cur.fetchall()
        
        if not users:
            buttons = [
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
            ]
            logger.debug(f"⚠️ No users found with role: {role}")
            return InlineKeyboardMarkup(inline_keyboard=buttons)
        
        buttons = []
        
        for (username,) in users:
            buttons.append([
                InlineKeyboardButton(
                    text=f"🗑️ @{username}",
                    callback_data=f"remove_user_{role}_{username}"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
        
        logger.debug(f"✅ Generated remove user keyboard with {len(users)} users")
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    finally:
        cur.close()
        conn.close()
