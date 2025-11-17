"""
Database connection and management module
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from app.config import DATABASE_URL
from app.logging_config import get_logger

logger = get_logger(__name__)


def get_db_connection():
    """
    Создать подключение к PostgreSQL
    
    Returns:
        psycopg2.connection: Подключение к базе данных
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.debug("🔌 Database connection established")
        return conn
    except Exception as e:
        logger.error(f"❌ Database connection error: {e}", exc_info=True)
        raise


def init_database():
    """
    Инициализация схемы базы данных
    Создание таблиц и типов если их нет
    """
    logger.info("🔧 Initializing database schema...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Создание enum типов
        cur.execute("""
            DO $$ BEGIN
                CREATE TYPE user_role AS ENUM ('admin', 'employee');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        cur.execute("""
            DO $$ BEGIN
                CREATE TYPE task_priority AS ENUM ('urgent', 'high', 'medium', 'low');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        cur.execute("""
            DO $$ BEGIN
                CREATE TYPE task_status AS ENUM ('pending', 'in_progress', 'partially_completed', 'completed', 'rejected');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        # Создание таблицы пользователей
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id VARCHAR(255) UNIQUE NOT NULL,
                username VARCHAR(255),
                first_name VARCHAR(255),
                role user_role NOT NULL DEFAULT 'employee',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Создание таблицы whitelist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS allowed_users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                role user_role NOT NULL DEFAULT 'employee',
                added_by_id INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Создание таблицы задач
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                status task_status NOT NULL DEFAULT 'pending',
                priority task_priority NOT NULL DEFAULT 'medium',
                due_date DATE NOT NULL,
                assigned_to_id INTEGER REFERENCES users(id),
                created_by_id INTEGER REFERENCES users(id),
                task_photo_file_id VARCHAR(255),
                completion_comment TEXT,
                photo_file_id VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Создание таблицы уведомлений
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_notifications (
                id SERIAL PRIMARY KEY,
                task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
                notification_type VARCHAR(50) NOT NULL,
                sent_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(task_id, notification_type)
            )
        """)
        
        conn.commit()
        logger.info("✅ Database schema initialized successfully")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Database initialization error: {e}", exc_info=True)
        raise
    finally:
        cur.close()
        conn.close()
