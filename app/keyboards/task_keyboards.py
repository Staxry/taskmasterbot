"""
Task-related keyboards
"""
from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.logging_config import get_logger
from app.config import get_now

logger = get_logger(__name__)


def is_mobile_device(user_id: int = None) -> bool:
    """
    Определить, является ли устройство мобильным
    В Telegram нет прямого способа определить устройство,
    поэтому используем эвристику: компактные клавиатуры для всех
    (можно расширить логику в будущем)
    
    Args:
        user_id: ID пользователя (для будущего расширения)
    
    Returns:
        bool: True если мобильное устройство
    """
    # По умолчанию считаем, что все пользователи на мобильных
    # для лучшего UX на маленьких экранах
    return True


def get_task_keyboard(task_id: int, current_status: str, assigned_to_id: int = None, 
                     user_id: int = None, is_admin: bool = False, 
                     has_task_photo: bool = False, is_mobile: bool = True) -> InlineKeyboardMarkup:
    """
    Клавиатура для работы с задачей (адаптивная для мобильных)
    
    Args:
        task_id: ID задачи
        current_status: Текущий статус задачи
        assigned_to_id: ID назначенного исполнителя
        user_id: ID текущего пользователя
        is_admin: Является ли пользователь админом
        has_task_photo: Есть ли фото у задачи
        is_mobile: Является ли устройство мобильным
    
    Returns:
        InlineKeyboardMarkup: Клавиатура задачи
    """
    logger.debug(f"🎹 Generating task keyboard for task #{task_id}, status: {current_status}, mobile: {is_mobile}")
    
    buttons = []
    
    # Кнопка просмотра фото задачи (если есть)
    if has_task_photo:
        buttons.append([InlineKeyboardButton(text="📸 Фото", callback_data=f"view_task_photo_{task_id}")])
    
    # Кнопки комментариев и истории
    action_buttons = []
    action_buttons.append(InlineKeyboardButton(text="💬 Комментарии", callback_data=f"task_comments_{task_id}"))
    action_buttons.append(InlineKeyboardButton(text="📜 История", callback_data=f"task_history_{task_id}"))
    
    if is_mobile:
        # На мобильных - по одной кнопке в ряд
        buttons.append([action_buttons[0]])
        buttons.append([action_buttons[1]])
    else:
        # На десктопе - две кнопки в ряд
        buttons.append(action_buttons)
    
    # Если задача не назначена и пользователь не админ - показываем кнопку "Взять в работу"
    if assigned_to_id is None and not is_admin:
        buttons.append([InlineKeyboardButton(text="✋ Взять в работу", callback_data=f"take_{task_id}")])
        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="my_tasks")])
        logger.debug("✅ Generated 'take task' keyboard for unassigned task")
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Если задача завершена или частично завершена - показываем кнопки для админов
    if current_status in ['completed', 'partially_completed']:
        if is_admin:
            admin_buttons = []
            admin_buttons.append(InlineKeyboardButton(text="🔄 Вернуть", callback_data=f"reopen_{task_id}"))
            admin_buttons.append(InlineKeyboardButton(text="👤 Сменить", callback_data=f"change_assignee_{task_id}"))
            
            if is_mobile:
                buttons.append([admin_buttons[0]])
                buttons.append([admin_buttons[1]])
            else:
                buttons.append(admin_buttons)
        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="my_tasks")])
        logger.debug(f"✅ Generated keyboard for completed task (admin: {is_admin})")
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Для остальных статусов показываем все доступные статусы
    statuses = {
        'pending': '⏳ Ожидает',
        'in_progress': '🔄 В работе',
        'partially_completed': '🔶 Частично',
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
    
    # На мобильных - по одной кнопке в ряд, на десктопе - по две
    if is_mobile:
        for btn in status_buttons:
            buttons.append([btn])
    else:
        for i in range(0, len(status_buttons), 2):
            buttons.append(status_buttons[i:i+2])
    
    # Для админов добавляем кнопку смены исполнителя
    if is_admin and assigned_to_id is not None:
        buttons.append([InlineKeyboardButton(text="👤 Сменить исполнителя", callback_data=f"change_assignee_{task_id}")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="my_tasks")])
    
    logger.debug(f"✅ Generated task keyboard with {len(status_buttons)} status buttons (mobile: {is_mobile})")
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
    
    buttons.append([
        InlineKeyboardButton(text="🌃 21:00", callback_data="time_21:00"),
        InlineKeyboardButton(text="🌃 22:00", callback_data="time_22:00"),
        InlineKeyboardButton(text="🌙 23:59 (конец дня)", callback_data="time_23:59")
    ])
    
    # Специальные опции
    buttons.append([
        InlineKeyboardButton(text="✍️ Ввод вручную", callback_data="time_manual")
    ])
    
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
