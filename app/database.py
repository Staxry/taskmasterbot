"""
Database connection and management module (SQLite)
"""
import sqlite3
import os
from datetime import datetime
from app.config import DATABASE_PATH
from app.logging_config import get_logger

logger = get_logger(__name__)


# Регистрируем конвертер для datetime из SQLite
def adapt_datetime(dt):
    """Конвертирует datetime в строку для SQLite"""
    return dt.isoformat()


def convert_datetime(s):
    """Конвертирует строку из SQLite в datetime с поддержкой множества форматов"""
    if s is None:
        return None
    if isinstance(s, bytes):
        s = s.decode('utf-8')
    
    # Пробуем разные форматы datetime
    formats_to_try = [
        '%Y-%m-%d %H:%M:%S.%f',      # С микросекундами
        '%Y-%m-%d %H:%M:%S',          # Стандартный SQLite datetime('now')
        '%Y-%m-%dT%H:%M:%S.%f',       # ISO 8601 с микросекундами
        '%Y-%m-%dT%H:%M:%S',          # ISO 8601
        '%Y-%m-%d %H:%M',             # Без секунд
        '%Y-%m-%d',                   # Только дата
    ]
    
    # Сначала пробуем fromisoformat (самый быстрый для ISO форматов)
    if 'T' in s or '+' in s or 'Z' in s:
        try:
            return datetime.fromisoformat(s.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            pass
    
    # Пробуем все форматы
    for fmt in formats_to_try:
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            continue
    
    # Если не удалось распарсить, возвращаем оригинальную строку
    # (для обратной совместимости и отладки)
    logger.debug(f"⚠️ Could not parse datetime string: {s}")
    return s


# Регистрируем адаптеры и конверторы SQLite
sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("timestamp", convert_datetime)


def dict_factory(cursor, row):
    """Преобразует строки SQLite в словари"""
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}


def get_db_connection():
    """
    Создать подключение к SQLite базе данных
    
    Returns:
        sqlite3.Connection: Подключение к базе данных
    """
    try:
        # Создаём директорию для БД если её нет
        db_dir = os.path.dirname(DATABASE_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        # PARSE_DECLTYPES включает автоматическое преобразование типов
        conn = sqlite3.connect(
            DATABASE_PATH, 
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = dict_factory  # Возвращать результаты как словари
        logger.debug(f"🔌 Database connection established: {DATABASE_PATH}")
        return conn
    except Exception as e:
        logger.error(f"❌ Database connection error: {e}", exc_info=True)
        raise


def init_database():
    """
    Инициализация схемы базы данных SQLite
    Создание таблиц если их нет
    """
    logger.info("🔧 Initializing SQLite database schema...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Создание таблицы пользователей
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                role TEXT NOT NULL DEFAULT 'employee' CHECK(role IN ('admin', 'employee')),
                created_at timestamp DEFAULT (datetime('now')),
                updated_at timestamp DEFAULT (datetime('now'))
            )
        """)
        
        # Создание таблицы whitelist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS allowed_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL DEFAULT 'employee' CHECK(role IN ('admin', 'employee')),
                added_by_id INTEGER,
                created_at timestamp DEFAULT (datetime('now')),
                FOREIGN KEY (added_by_id) REFERENCES users(id)
            )
        """)
        
        # Создание таблицы задач
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'in_progress', 'partially_completed', 'completed', 'rejected')),
                priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('urgent', 'high', 'medium', 'low')),
                due_date timestamp NOT NULL,
                assigned_to_id INTEGER,
                created_by_id INTEGER,
                task_photo_file_id TEXT,
                completion_comment TEXT,
                photo_file_id TEXT,
                created_at timestamp DEFAULT (datetime('now')),
                updated_at timestamp DEFAULT (datetime('now')),
                FOREIGN KEY (assigned_to_id) REFERENCES users(id),
                FOREIGN KEY (created_by_id) REFERENCES users(id)
            )
        """)
        
        # Создание таблицы уведомлений
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                notification_type TEXT NOT NULL,
                sent_at timestamp DEFAULT (datetime('now')),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                UNIQUE(task_id, notification_type)
            )
        """)
        
        conn.commit()
        logger.info("✅ SQLite database schema initialized successfully")
        logger.info(f"📁 Database file: {DATABASE_PATH}")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Database initialization error: {e}", exc_info=True)
        raise
    finally:
        cur.close()
        conn.close()
