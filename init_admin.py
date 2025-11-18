#!/usr/bin/env python3
"""
Скрипт для добавления первого администратора в базу данных
Использование: python3 init_admin.py
"""
import sqlite3
import sys
from app.config import DATABASE_PATH


def add_admin_to_whitelist(username: str):
    """Добавить админа в whitelist"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        
        # Проверяем, существует ли уже такой пользователь
        cur.execute("SELECT username, role FROM allowed_users WHERE username = ?", (username,))
        existing = cur.fetchone()
        
        if existing:
            print(f"⚠️  Пользователь @{username} уже существует в whitelist с ролью: {existing[1]}")
            
            # Обновляем роль на admin, если это необходимо
            if existing[1] != 'admin':
                cur.execute("UPDATE allowed_users SET role = 'admin' WHERE username = ?", (username,))
                conn.commit()
                print(f"✅ Роль пользователя @{username} изменена на 'admin'")
            return
        
        # Добавляем нового админа
        cur.execute(
            "INSERT INTO allowed_users (username, role) VALUES (?, 'admin')",
            (username,)
        )
        conn.commit()
        
        print(f"✅ Администратор @{username} успешно добавлен в whitelist!")
        print(f"📱 Теперь пользователь может запустить бота командой /start")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)
    finally:
        conn.close()


def main():
    print("=" * 60)
    print("🔧 Инициализация первого администратора")
    print("=" * 60)
    print()
    
    # Запрашиваем username
    username = input("Введите Telegram username админа (без @): ").strip()
    
    if not username:
        print("❌ Username не может быть пустым!")
        sys.exit(1)
    
    # Удаляем @ если пользователь его ввел
    username = username.lstrip('@')
    
    print()
    print(f"Добавляем администратора: @{username}")
    print()
    
    add_admin_to_whitelist(username)
    
    print()
    print("=" * 60)
    print("✅ Готово! Теперь админ может начать работу с ботом")
    print("=" * 60)


if __name__ == "__main__":
    main()
