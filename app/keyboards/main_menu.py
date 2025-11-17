"""
Main menu keyboard
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.logging_config import get_logger

logger = get_logger(__name__)


def get_main_keyboard(role: str) -> InlineKeyboardMarkup:
    """
    Главное меню с кнопками в зависимости от роли пользователя
    
    Args:
        role: Роль пользователя ('admin' или 'employee')
    
    Returns:
        InlineKeyboardMarkup: Клавиатура главного меню
    """
    logger.debug(f"📋 Generating main keyboard for role: {role}")
    
    buttons = [
        [InlineKeyboardButton(text="📋 Мои задачи", callback_data="my_tasks")],
    ]
    
    if role == 'admin':
        buttons.append([InlineKeyboardButton(text="📊 Все задачи", callback_data="all_tasks")])
        buttons.append([InlineKeyboardButton(text="➕ Создать задачу", callback_data="create_task")])
        buttons.append([InlineKeyboardButton(text="🗑️ Удалить задачу", callback_data="delete_task_menu")])
        buttons.append([
            InlineKeyboardButton(text="➕👨‍💼 Добавить админа", callback_data="add_admin"),
            InlineKeyboardButton(text="➕👤 Добавить сотрудника", callback_data="add_employee")
        ])
        buttons.append([
            InlineKeyboardButton(text="🗑️👨‍💼 Удалить админа", callback_data="remove_admin"),
            InlineKeyboardButton(text="🗑️👤 Удалить сотрудника", callback_data="remove_employee")
        ])
    
    buttons.append([InlineKeyboardButton(text="❓ Помощь", callback_data="help")])
    
    logger.debug(f"✅ Main keyboard generated with {len(buttons)} rows")
    return InlineKeyboardMarkup(inline_keyboard=buttons)
