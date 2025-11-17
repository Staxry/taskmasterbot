"""
Configuration module for the Telegram bot
"""
import os
from dotenv import load_dotenv
import pytz

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Timezone Configuration
# Установите нужный часовой пояс для вашего региона
# Примеры: 'Europe/Moscow', 'Europe/Kiev', 'Asia/Almaty', 'Europe/Minsk'
TIMEZONE = pytz.timezone(os.getenv('TIMEZONE', 'Europe/Kaliningrad'))


def get_now():
    """Получить текущее время в настроенном часовом поясе"""
    from datetime import datetime
    return datetime.now(TIMEZONE)


def combine_datetime(date_str: str, time_str: str):
    """
    Объединить дату и время в datetime с часовым поясом
    
    Args:
        date_str: Дата в формате YYYY-MM-DD
        time_str: Время в формате HH:MM
    
    Returns:
        datetime: Datetime с настроенным часовым поясом
    """
    from datetime import datetime
    # Парсим дату и время
    naive_dt = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
    # Добавляем часовой пояс
    return TIMEZONE.localize(naive_dt)

# Database Configuration (SQLite)
# По умолчанию БД создаётся в файле data/task_bot.db
DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/task_bot.db')

# Logging Configuration
LOG_FILE = 'logs/bot.log'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# Bot Configuration
POLLING_TIMEOUT = 30
REQUEST_TIMEOUT = 30

# Status Display Mapping
STATUS_DISPLAY = {
    'pending': '⏳ Ожидает',
    'in_progress': '🔄 В работе',
    'partially_completed': '🔶 Частично завершена',
    'completed': '✅ Завершена',
    'rejected': '❌ Отклонена'
}

# Priority Display Mapping
PRIORITY_DISPLAY = {
    'urgent': '🔴 Срочно',
    'high': '🟠 Высокий',
    'medium': '🟡 Средний',
    'low': '🟢 Низкий'
}

# Role Display Mapping
ROLE_DISPLAY = {
    'admin': '👨‍💼 Админ',
    'employee': '👤 Сотрудник'
}
