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
        
        # Создание таблицы для фото задач (поддержка множественных фото)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                photo_file_id TEXT NOT NULL,
                created_at timestamp DEFAULT (datetime('now')),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        """)
        
        # Создаем индекс для быстрого поиска фото по задаче
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_photos_task_id ON task_photos(task_id)
        """)
        
        # Создание таблицы настроек уведомлений пользователей
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_notification_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                enable_24h_reminder INTEGER DEFAULT 1 CHECK(enable_24h_reminder IN (0, 1)),
                enable_3h_reminder INTEGER DEFAULT 1 CHECK(enable_3h_reminder IN (0, 1)),
                enable_1h_reminder INTEGER DEFAULT 1 CHECK(enable_1h_reminder IN (0, 1)),
                enable_overdue_notifications INTEGER DEFAULT 1 CHECK(enable_overdue_notifications IN (0, 1)),
                enable_comment_notifications INTEGER DEFAULT 1 CHECK(enable_comment_notifications IN (0, 1)),
                quiet_hours_start TEXT DEFAULT '22:00',
                quiet_hours_end TEXT DEFAULT '08:00',
                custom_reminder_intervals TEXT,
                created_at timestamp DEFAULT (datetime('now')),
                updated_at timestamp DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Создание таблицы истории изменений задач
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                change_type TEXT NOT NULL CHECK(change_type IN ('status', 'priority', 'assignee', 'due_date', 'title', 'description', 'created', 'reopened')),
                old_value TEXT,
                new_value TEXT,
                created_at timestamp DEFAULT (datetime('now')),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Создание индекса для истории изменений
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_history_task_id ON task_history(task_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_history_created_at ON task_history(created_at)
        """)
        
        # Создание таблицы комментариев к задачам
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                comment_text TEXT NOT NULL,
                created_at timestamp DEFAULT (datetime('now')),
                updated_at timestamp DEFAULT (datetime('now')),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Создание индекса для комментариев
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_comments_task_id ON task_comments(task_id)
        """)
        
        # Создание таблицы файлов комментариев
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comment_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_id INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                file_type TEXT NOT NULL CHECK(file_type IN ('photo', 'document', 'video', 'audio', 'voice')),
                file_name TEXT,
                created_at timestamp DEFAULT (datetime('now')),
                FOREIGN KEY (comment_id) REFERENCES task_comments(id) ON DELETE CASCADE
            )
        """)
        
        # Создание индекса для файлов комментариев
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_comment_files_comment_id ON comment_files(comment_id)
        """)
        
        # Создание таблицы упоминаний в комментариях
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comment_mentions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_id INTEGER NOT NULL,
                mentioned_user_id INTEGER NOT NULL,
                created_at timestamp DEFAULT (datetime('now')),
                FOREIGN KEY (comment_id) REFERENCES task_comments(id) ON DELETE CASCADE,
                FOREIGN KEY (mentioned_user_id) REFERENCES users(id),
                UNIQUE(comment_id, mentioned_user_id)
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
