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
        InlineKeyboardMarkup: Клавиатура со списком пользователей с именами из Telegram
    """
    logger.debug("🎹 Generating users keyboard")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """SELECT id, username, first_name, last_name, role FROM users 
               ORDER BY role DESC, first_name ASC, username ASC"""
        )
        users = cur.fetchall()
        
        buttons = []
        
        for user in users:
            user_id = user['id']
            username = user['username']
            first_name = user.get('first_name')
            last_name = user.get('last_name')
            role = user['role']
            role_emoji = "👨‍💼" if role == "admin" else "👤"
            
            if first_name or last_name:
                display_name = f"{first_name or ''} {last_name or ''}".strip()
                button_text = f"{role_emoji} {display_name} (@{username})"
            else:
                button_text = f"{role_emoji} @{username}"
            
            buttons.append([
                InlineKeyboardButton(
                    text=button_text,
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
               WHERE role = ?
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
        
        for user in users:
            username = user['username']
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
