#!/usr/bin/env python3
"""
Скрипт миграции существующих SQLite БД для использования типа timestamp.
Это нужно для автоматической конвертации строк в datetime объекты.

ВАЖНО: Запускайте этот скрипт только если вы обновляете бота с СТАРОЙ версии!
Для новых установок этот скрипт НЕ НУЖЕН - схема уже использует timestamp.
"""

import sqlite3
import os
from datetime import datetime

DATABASE_PATH = 'data/task_bot.db'


def backup_database():
    """Создаёт резервную копию БД"""
    if not os.path.exists(DATABASE_PATH):
        print(f"❌ База данных не найдена: {DATABASE_PATH}")
        return False
    
    backup_path = f"{DATABASE_PATH}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        import shutil
        shutil.copy2(DATABASE_PATH, backup_path)
        print(f"✅ Резервная копия создана: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ Ошибка создания резервной копии: {e}")
        return False


def check_schema_version(conn):
    """Проверяет версию схемы БД"""
    cur = conn.cursor()
    
    # Проверяем тип поля due_date в таблице tasks
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'")
    result = cur.fetchone()
    
    if result:
        schema_sql = result[0]
        if 'due_date timestamp' in schema_sql.lower():
            return 'timestamp'
        elif 'due_date text' in schema_sql.lower():
            return 'text'
    
    return None


def migrate_schema():
    """Выполняет миграцию схемы с TEXT на timestamp"""
    
    print("=" * 60)
    print("🔧 Скрипт миграции SQLite схемы")
    print("=" * 60)
    print()
    
    # Проверка наличия БД
    if not os.path.exists(DATABASE_PATH):
        print(f"❌ База данных не найдена: {DATABASE_PATH}")
        print("   Для новой установки этот скрипт НЕ НУЖЕН!")
        return
    
    # Создаём резервную копию
    print("📦 Создание резервной копии...")
    if not backup_database():
        print("❌ Не удалось создать резервную копию. Миграция отменена.")
        return
    
    print()
    
    # Подключаемся к БД
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        
        # Проверяем версию схемы
        schema_version = check_schema_version(conn)
        
        if schema_version == 'timestamp':
            print("✅ База данных уже использует тип timestamp!")
            print("   Миграция не требуется.")
            conn.close()
            return
        elif schema_version == 'text':
            print("📝 Обнаружена старая схема с типом TEXT для дат.")
            print("   Начинаем миграцию...")
        else:
            print("⚠️ Не удалось определить версию схемы.")
            print("   Продолжаем миграцию...")
        
        print()
        
        # Отключаем foreign key constraints для безопасной миграции
        print("🔄 Подготовка: Отключение foreign key constraints...")
        cur.execute("PRAGMA foreign_keys=OFF")
        
        # Начинаем миграцию
        print("🔄 Шаг 1: Создание временных таблиц с новой схемой...")
        
        # Создаём новую таблицу tasks с правильными типами
        cur.execute("""
            CREATE TABLE tasks_new (
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
        
        print("✅ Временная таблица создана")
        
        # Копируем данные
        print("🔄 Шаг 2: Копирование данных...")
        cur.execute("""
            INSERT INTO tasks_new 
            SELECT * FROM tasks
        """)
        
        print(f"✅ Скопировано {cur.rowcount} записей")
        
        # Удаляем старую таблицу и переименовываем новую
        print("🔄 Шаг 3: Замена старой таблицы...")
        cur.execute("DROP TABLE tasks")
        cur.execute("ALTER TABLE tasks_new RENAME TO tasks")
        
        print("✅ Таблица tasks обновлена")
        
        # Аналогично для других таблиц
        print("🔄 Шаг 4: Обновление таблицы users...")
        
        cur.execute("""
            CREATE TABLE users_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                role TEXT NOT NULL DEFAULT 'employee' CHECK(role IN ('admin', 'employee')),
                created_at timestamp DEFAULT (datetime('now')),
                updated_at timestamp DEFAULT (datetime('now'))
            )
        """)
        
        cur.execute("INSERT INTO users_new SELECT * FROM users")
        cur.execute("DROP TABLE users")
        cur.execute("ALTER TABLE users_new RENAME TO users")
        
        print("✅ Таблица users обновлена")
        
        # Таблица allowed_users
        print("🔄 Шаг 5: Обновление таблицы allowed_users...")
        
        cur.execute("""
            CREATE TABLE allowed_users_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL DEFAULT 'employee' CHECK(role IN ('admin', 'employee')),
                added_by_id INTEGER,
                created_at timestamp DEFAULT (datetime('now')),
                FOREIGN KEY (added_by_id) REFERENCES users(id)
            )
        """)
        
        cur.execute("INSERT INTO allowed_users_new SELECT * FROM allowed_users")
        cur.execute("DROP TABLE allowed_users")
        cur.execute("ALTER TABLE allowed_users_new RENAME TO allowed_users")
        
        print("✅ Таблица allowed_users обновлена")
        
        # Таблица task_notifications
        print("🔄 Шаг 6: Обновление таблицы task_notifications...")
        
        cur.execute("""
            CREATE TABLE task_notifications_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                notification_type TEXT NOT NULL,
                sent_at timestamp DEFAULT (datetime('now')),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                UNIQUE(task_id, notification_type)
            )
        """)
        
        cur.execute("INSERT INTO task_notifications_new SELECT * FROM task_notifications")
        cur.execute("DROP TABLE task_notifications")
        cur.execute("ALTER TABLE task_notifications_new RENAME TO task_notifications")
        
        print("✅ Таблица task_notifications обновлена")
        
        # Включаем обратно foreign key constraints
        print("🔄 Завершение: Включение foreign key constraints...")
        cur.execute("PRAGMA foreign_keys=ON")
        
        # Коммитим изменения
        conn.commit()
        
        print()
        print("=" * 60)
        print("✅✅✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print("=" * 60)
        print()
        print("📊 Все таблицы теперь используют тип timestamp")
        print("🔄 Перезапустите бота для применения изменений")
        print()
        
        conn.close()
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ ОШИБКА ПРИ МИГРАЦИИ!")
        print("=" * 60)
        print(f"   {e}")
        print()
        print("🔄 Восстановите БД из резервной копии:")
        print(f"   cp data/task_bot.db.backup_* {DATABASE_PATH}")
        print()


if __name__ == "__main__":
    migrate_schema()
