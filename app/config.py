"""
Configuration module for the Telegram bot
"""
import os
import sys
from dotenv import load_dotenv
import pytz

# Загружаем переменные из .env файла
load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Валидация токена
if not BOT_TOKEN:
    print("\n" + "="*60)
    print("❌ ОШИБКА: Токен бота не найден!")
    print("="*60)
    print("\nТокен не загружен из переменных окружения.")
    print("\n📋 Варианты решения:")
    print("\n1️⃣  Создайте файл .env в корне проекта:")
    print("   cp .env.example .env")
    print("   nano .env")
    print("\n2️⃣  Добавьте в файл .env:")
    print("   TELEGRAM_BOT_TOKEN=ваш_токен_без_кавычек")
    print("\n3️⃣  Пример правильного формата .env:")
    print("   TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
    print("   DATABASE_PATH=data/task_bot.db")
    print("   TIMEZONE=Europe/Kaliningrad")
    print("\n⚠️  Важно:")
    print("   - Файл .env должен быть в корне проекта (там же где bot.py)")
    print("   - Токен без кавычек и пробелов")
    print("   - После = сразу токен, без пробелов")
    print("\n4️⃣  Получить токен можно у @BotFather в Telegram")
    print("="*60 + "\n")
    sys.exit(1)

# Timezone Configuration
# Установите нужный часовой пояс для вашего региона
# Примеры: 'Europe/Moscow', 'Europe/Kiev', 'Asia/Almaty', 'Europe/Minsk'
TIMEZONE = pytz.timezone(os.getenv('TIMEZONE', 'Europe/Kaliningrad'))

# Аббревиатура часового пояса для отображения пользователю
# Europe/Kaliningrad = UTC+2
TIMEZONE_ABBR = os.getenv('TIMEZONE_ABBR', 'КЛД')


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


def format_datetime_for_display(dt_value) -> str:
    """
    Форматировать дату/время для отображения пользователю
    
    Args:
        dt_value: Может быть строкой, datetime объектом или None
        
    Returns:
        str: Отформатированная дата в формате 'DD.MM.YYYY HH:MM' или 'не указан'
    """
    from datetime import datetime
    
    if not dt_value:
        return 'не указан'
    
    if isinstance(dt_value, str):
        try:
            dt = datetime.fromisoformat(dt_value.replace('Z', '+00:00'))
            return dt.strftime('%d.%m.%Y %H:%M')
        except:
            return dt_value
    
    if hasattr(dt_value, 'strftime'):
        return dt_value.strftime('%d.%m.%Y %H:%M')
    
    return str(dt_value)

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
