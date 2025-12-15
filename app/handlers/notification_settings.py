"""
Notification settings handlers module
Обработчики для настройки уведомлений
"""
from aiogram import F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.handlers import core_router
from app.database import get_db_connection
from app.services.users import get_or_create_user
from app.services.notification_settings import (
    get_user_notification_settings,
    update_notification_setting
)
from app.keyboards.main_menu import get_main_keyboard
from app.keyboards.task_keyboards import is_mobile_device
from app.states import NotificationSettingsStates
from app.logging_config import get_logger

logger = get_logger(__name__)


@core_router.callback_query(F.data == "notification_settings")
async def callback_notification_settings(callback: CallbackQuery):
    """Показать настройки уведомлений"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"🔔 Notification settings requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    settings = get_user_notification_settings(user['id'])
    
    # Форматируем статусы
    status_24h = "✅" if settings['enable_24h_reminder'] else "❌"
    status_3h = "✅" if settings['enable_3h_reminder'] else "❌"
    status_1h = "✅" if settings['enable_1h_reminder'] else "❌"
    status_overdue = "✅" if settings['enable_overdue_notifications'] else "❌"
    status_comment = "✅" if settings['enable_comment_notifications'] else "❌"
    
    text = (
        f"🔔 <b>Настройки уведомлений</b>\n\n"
        f"<b>Напоминания о дедлайнах:</b>\n"
        f"{status_24h} За 8 часов до срока\n"
        f"{status_3h} За 4 часа до срока\n"
        f"{status_1h} За 1 час до срока\n"
        f"{status_overdue} О просроченных задачах\n\n"
        f"<b>Другие уведомления:</b>\n"
        f"{status_comment} О комментариях к задачам\n\n"
        f"<b>Тихие часы:</b>\n"
        f"🌙 {settings['quiet_hours_start']} - {settings['quiet_hours_end']}\n\n"
        f"Выберите настройку для изменения:"
    )
    
    buttons = []
    buttons.append([
        InlineKeyboardButton(
            text=f"{status_24h} Напоминание за 8ч",
            callback_data=f"toggle_notif_24h"
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text=f"{status_3h} Напоминание за 4ч",
            callback_data=f"toggle_notif_3h"
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text=f"{status_1h} Напоминание за 1ч",
            callback_data=f"toggle_notif_1h"
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text=f"{status_overdue} Просроченные",
            callback_data=f"toggle_notif_overdue"
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text=f"{status_comment} Комментарии",
            callback_data=f"toggle_notif_comment"
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text="🌙 Тихие часы",
            callback_data="set_quiet_hours"
        )
    ])
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    try:
        await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, parse_mode='HTML', reply_markup=keyboard)
    
    await callback.answer()


@core_router.callback_query(F.data.startswith("toggle_notif_"))
async def callback_toggle_notification(callback: CallbackQuery):
    """Переключить настройку уведомления"""
    setting_type = callback.data.split('_')[-1]
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    settings = get_user_notification_settings(user['id'])
    
    # Определяем название настройки
    setting_map = {
        '24h': 'enable_24h_reminder',
        '3h': 'enable_3h_reminder',
        '1h': 'enable_1h_reminder',
        'overdue': 'enable_overdue_notifications',
        'comment': 'enable_comment_notifications'
    }
    
    setting_name = setting_map.get(setting_type)
    if not setting_name:
        await callback.answer("❌ Неизвестная настройка", show_alert=True)
        return
    
    # Переключаем значение
    current_value = settings[setting_name]
    new_value = 0 if current_value else 1
    
    update_notification_setting(user['id'], setting_name, new_value)
    
    status_text = "включено" if new_value else "выключено"
    await callback.answer(f"✅ Напоминание {status_text}", show_alert=True)
    
    # Обновляем интерфейс
    await callback_notification_settings(callback)


@core_router.callback_query(F.data == "set_quiet_hours")
async def callback_set_quiet_hours(callback: CallbackQuery, state: FSMContext):
    """Начать настройку тихих часов"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    settings = get_user_notification_settings(user['id'])
    
    await state.set_state(NotificationSettingsStates.waiting_for_quiet_hours_start)
    
    text = (
        f"🌙 <b>Настройка тихих часов</b>\n\n"
        f"Текущие тихие часы: {settings['quiet_hours_start']} - {settings['quiet_hours_end']}\n\n"
        f"Введите время начала тихих часов в формате <code>ЧЧ:ММ</code>\n"
        f"Например: <code>22:00</code>"
    )
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="notification_settings")]
    ])
    
    try:
        await callback.message.edit_text(text, parse_mode='HTML', reply_markup=cancel_keyboard)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, parse_mode='HTML', reply_markup=cancel_keyboard)
    
    await callback.answer()


@core_router.message(NotificationSettingsStates.waiting_for_quiet_hours_start)
async def process_quiet_hours_start(message: Message, state: FSMContext):
    """Обработать время начала тихих часов"""
    time_text = message.text.strip()
    
    try:
        from datetime import datetime
        datetime.strptime(time_text, '%H:%M')
    except ValueError:
        await message.answer(
            "❌ <b>Неверный формат времени!</b>\n\n"
            "Используйте формат <code>ЧЧ:ММ</code>\n"
            "Например: <code>22:00</code>",
            parse_mode='HTML'
        )
        return
    
    await state.update_data(quiet_hours_start=time_text)
    await state.set_state(NotificationSettingsStates.waiting_for_quiet_hours_end)
    
    await message.answer(
        f"✅ Время начала: <code>{time_text}</code>\n\n"
        f"Теперь введите время окончания тихих часов:\n"
        f"Например: <code>08:00</code>",
        parse_mode='HTML'
    )


@core_router.message(NotificationSettingsStates.waiting_for_quiet_hours_end)
async def process_quiet_hours_end(message: Message, state: FSMContext):
    """Обработать время окончания тихих часов"""
    time_text = message.text.strip()
    
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    last_name = message.from_user.last_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await message.answer("❌ Доступ запрещён")
        await state.clear()
        return
    
    try:
        from datetime import datetime
        datetime.strptime(time_text, '%H:%M')
    except ValueError:
        await message.answer(
            "❌ <b>Неверный формат времени!</b>\n\n"
            "Используйте формат <code>ЧЧ:ММ</code>\n"
            "Например: <code>08:00</code>",
            parse_mode='HTML'
        )
        return
    
    data = await state.get_data()
    start_time = data.get('quiet_hours_start')
    
    # Обновляем настройки
    update_notification_setting(user['id'], 'quiet_hours_start', start_time)
    update_notification_setting(user['id'], 'quiet_hours_end', time_text)
    
    await message.answer(
        f"✅ <b>Тихие часы обновлены!</b>\n\n"
        f"🌙 {start_time} - {time_text}\n\n"
        f"В это время вы не будете получать уведомления.",
        parse_mode='HTML',
        reply_markup=get_main_keyboard(user['role'], is_mobile_device())
    )
    
    await state.clear()

