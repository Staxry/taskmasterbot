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
TIMEZONE = pytz.timezone(os.getenv('TIMEZONE', 'Europe/Moscow'))

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL')

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
