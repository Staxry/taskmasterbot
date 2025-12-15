"""
Main menu keyboard
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.logging_config import get_logger

logger = get_logger(__name__)


def get_main_keyboard(role: str, is_mobile: bool = True) -> InlineKeyboardMarkup:
    """
    Главное меню с кнопками в зависимости от роли пользователя (адаптивное для мобильных)
    
    Args:
        role: Роль пользователя ('admin' или 'employee')
        is_mobile: Является ли устройство мобильным
    
    Returns:
        InlineKeyboardMarkup: Клавиатура главного меню
    """
    logger.debug(f"📋 Generating main keyboard for role: {role}, mobile: {is_mobile}")
    
    buttons = [
        [InlineKeyboardButton(text="📋 Мои задачи", callback_data="my_tasks")],
        [InlineKeyboardButton(text="🔍 Поиск", callback_data="search_tasks")],
    ]
    
    if role == 'admin':
        if is_mobile:
            # На мобильных - компактные кнопки по одной
            buttons.append([InlineKeyboardButton(text="📊 Все задачи", callback_data="all_tasks")])
            buttons.append([InlineKeyboardButton(text="📈 Статистика", callback_data="dashboard")])
            buttons.append([InlineKeyboardButton(text="➕ Создать", callback_data="create_task")])
            buttons.append([InlineKeyboardButton(text="🗑️ Удалить", callback_data="delete_task_menu")])
            buttons.append([InlineKeyboardButton(text="➕👨‍💼 Админ", callback_data="add_admin")])
            buttons.append([InlineKeyboardButton(text="➕👤 Сотрудник", callback_data="add_employee")])
            buttons.append([InlineKeyboardButton(text="🗑️👨‍💼 Удалить админа", callback_data="remove_admin")])
            buttons.append([InlineKeyboardButton(text="🗑️👤 Удалить сотрудника", callback_data="remove_employee")])
        else:
            # На десктопе - группируем кнопки
            buttons.append([InlineKeyboardButton(text="📊 Все задачи", callback_data="all_tasks")])
            buttons.append([InlineKeyboardButton(text="📈 Статистика и отчёты", callback_data="dashboard")])
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
    
    # Кнопка настроек уведомлений для всех
    buttons.append([InlineKeyboardButton(text="🔔 Настройки", callback_data="notification_settings")])
    buttons.append([InlineKeyboardButton(text="❓ Помощь", callback_data="help")])
    
    logger.debug(f"✅ Main keyboard generated with {len(buttons)} rows")
    return InlineKeyboardMarkup(inline_keyboard=buttons)
