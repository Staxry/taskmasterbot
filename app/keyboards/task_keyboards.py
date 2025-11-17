"""
Task-related keyboards
"""
from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.logging_config import get_logger
from app.config import get_now

logger = get_logger(__name__)


def get_task_keyboard(task_id: int, current_status: str, assigned_to_id: int = None, 
                     user_id: int = None, is_admin: bool = False) -> InlineKeyboardMarkup:
    """
    Клавиатура для работы с задачей
    
    Args:
        task_id: ID задачи
        current_status: Текущий статус задачи
        assigned_to_id: ID назначенного исполнителя
        user_id: ID текущего пользователя
        is_admin: Является ли пользователь админом
    
    Returns:
        InlineKeyboardMarkup: Клавиатура задачи
    """
    logger.debug(f"🎹 Generating task keyboard for task #{task_id}, status: {current_status}")
    
    buttons = []
    
    # Если задача не назначена и пользователь не админ - показываем кнопку "Взять в работу"
    if assigned_to_id is None and not is_admin:
        buttons.append([InlineKeyboardButton(text="✋ Взять в работу", callback_data=f"take_{task_id}")])
        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="my_tasks")])
        logger.debug("✅ Generated 'take task' keyboard for unassigned task")
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Если задача завершена или частично завершена - показываем только кнопку "Вернуть в работу" для админов
    if current_status in ['completed', 'partially_completed']:
        if is_admin:
            buttons.append([InlineKeyboardButton(text="🔄 Вернуть в работу", callback_data=f"reopen_{task_id}")])
        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="my_tasks")])
        logger.debug(f"✅ Generated keyboard for completed task (admin: {is_admin})")
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Для остальных статусов показываем все доступные статусы
    statuses = {
        'pending': '⏳ Ожидает',
        'in_progress': '🔄 В работе',
        'partially_completed': '🔶 Частично завершена',
        'completed': '✅ Завершена',
        'rejected': '❌ Отклонена'
    }
    
    status_buttons = []
    for status, label in statuses.items():
        if status != current_status:
            status_buttons.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"status_{task_id}_{status}"
                )
            )
    
    # Размещаем кнопки статусов по 2 в ряд
    for i in range(0, len(status_buttons), 2):
        buttons.append(status_buttons[i:i+2])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="my_tasks")])
    
    logger.debug(f"✅ Generated task keyboard with {len(status_buttons)} status buttons")
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_priority_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора приоритета задачи
    
    Returns:
        InlineKeyboardMarkup: Клавиатура выбора приоритета
    """
    logger.debug("🎹 Generating priority keyboard")
    
    buttons = [
        [
            InlineKeyboardButton(text="🔴 Срочно", callback_data="priority_urgent"),
            InlineKeyboardButton(text="🟠 Высокий", callback_data="priority_high")
        ],
        [
            InlineKeyboardButton(text="🟡 Средний", callback_data="priority_medium"),
            InlineKeyboardButton(text="🟢 Низкий", callback_data="priority_low")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_due_date_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора срока выполнения задачи
    
    Returns:
        InlineKeyboardMarkup: Клавиатура выбора срока
    """
    logger.debug("🎹 Generating due date keyboard")
    
    today = get_now()
    
    buttons = [
        [
            InlineKeyboardButton(text="📅 Сегодня", callback_data=f"due_{today.strftime('%Y-%m-%d')}"),
            InlineKeyboardButton(text="📅 Завтра", callback_data=f"due_{(today + timedelta(days=1)).strftime('%Y-%m-%d')}")
        ],
        [
            InlineKeyboardButton(text="📅 Через 3 дня", callback_data=f"due_{(today + timedelta(days=3)).strftime('%Y-%m-%d')}"),
            InlineKeyboardButton(text="📅 Через неделю", callback_data=f"due_{(today + timedelta(days=7)).strftime('%Y-%m-%d')}")
        ],
        [
            InlineKeyboardButton(text="📅 Через 2 недели", callback_data=f"due_{(today + timedelta(days=14)).strftime('%Y-%m-%d')}"),
            InlineKeyboardButton(text="📅 Через месяц", callback_data=f"due_{(today + timedelta(days=30)).strftime('%Y-%m-%d')}")
        ],
        [InlineKeyboardButton(text="✍️ Ввод вручную", callback_data="due_manual")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_due_time_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора времени выполнения задачи
    
    Returns:
        InlineKeyboardMarkup: Клавиатура выбора времени
    """
    logger.debug("🎹 Generating due time keyboard")
    
    buttons = []
    
    # Утро
    buttons.append([
        InlineKeyboardButton(text="🌅 09:00", callback_data="time_09:00"),
        InlineKeyboardButton(text="🌅 10:00", callback_data="time_10:00"),
        InlineKeyboardButton(text="🌅 11:00", callback_data="time_11:00")
    ])
    
    # День
    buttons.append([
        InlineKeyboardButton(text="☀️ 12:00", callback_data="time_12:00"),
        InlineKeyboardButton(text="☀️ 13:00", callback_data="time_13:00"),
        InlineKeyboardButton(text="☀️ 14:00", callback_data="time_14:00")
    ])
    
    # Вечер
    buttons.append([
        InlineKeyboardButton(text="🌆 15:00", callback_data="time_15:00"),
        InlineKeyboardButton(text="🌆 16:00", callback_data="time_16:00"),
        InlineKeyboardButton(text="🌆 17:00", callback_data="time_17:00")
    ])
    
    buttons.append([
        InlineKeyboardButton(text="🌃 18:00", callback_data="time_18:00"),
        InlineKeyboardButton(text="🌃 19:00", callback_data="time_19:00"),
        InlineKeyboardButton(text="🌃 20:00", callback_data="time_20:00")
    ])
    
    # Специальные опции
    buttons.append([
        InlineKeyboardButton(text="🌙 23:59 (конец дня)", callback_data="time_23:59"),
        InlineKeyboardButton(text="✍️ Ввод вручную", callback_data="time_manual")
    ])
    
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
