#!/usr/bin/env python3
"""
Диагностика загрузки .env файла
Запустите на своем Mac: python test_env.py
"""
import os
import sys
from pathlib import Path

print("\n" + "="*60)
print("🔍 ДИАГНОСТИКА ЗАГРУЗКИ .ENV ФАЙЛА")
print("="*60)

# Проверка текущей директории
current_dir = Path.cwd()
print(f"\n📂 Текущая директория: {current_dir}")

# Проверка наличия .env файла
env_file = current_dir / ".env"
print(f"\n📄 Проверка файла .env:")
print(f"   Путь: {env_file}")
print(f"   Существует: {'✅ Да' if env_file.exists() else '❌ Нет'}")

if env_file.exists():
    print(f"   Размер: {env_file.stat().st_size} байт")
    print(f"\n📋 Содержимое .env файла:")
    print("   " + "-"*56)
    with open(env_file, 'r') as f:
        lines = f.readlines()
        for i, line in enumerate(lines, 1):
            # Скрываем токен для безопасности
            if 'TOKEN' in line and '=' in line:
                parts = line.split('=', 1)
                if len(parts) == 2 and len(parts[1].strip()) > 10:
                    masked = parts[1][:10] + "..." + parts[1][-5:]
                    print(f"   {i}: {parts[0]}={masked}")
                else:
                    print(f"   {i}: {line.rstrip()}")
            else:
                print(f"   {i}: {line.rstrip()}")
    print("   " + "-"*56)

# Проверка загрузки через python-dotenv
print(f"\n🐍 Проверка python-dotenv:")
try:
    from dotenv import load_dotenv
    print("   ✅ Модуль dotenv установлен")
    
    # Пытаемся загрузить
    result = load_dotenv(verbose=True)
    print(f"   Результат load_dotenv(): {result}")
    
except ImportError:
    print("   ❌ Модуль python-dotenv НЕ установлен!")
    print("   Установите: pip install python-dotenv")
    sys.exit(1)

# Проверка переменных окружения
print(f"\n🔑 Переменные окружения:")
telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
if telegram_token:
    print(f"   ✅ TELEGRAM_BOT_TOKEN: {telegram_token[:10]}...{telegram_token[-5:]}")
    print(f"   Длина токена: {len(telegram_token)} символов")
else:
    print(f"   ❌ TELEGRAM_BOT_TOKEN: не найден!")

db_path = os.getenv('DATABASE_PATH')
print(f"   DATABASE_PATH: {db_path or 'не найден'}")

timezone = os.getenv('TIMEZONE')
print(f"   TIMEZONE: {timezone or 'не найден'}")

# Итог
print("\n" + "="*60)
if telegram_token:
    print("✅ УСПЕХ: Токен загружен правильно!")
    print("\n💡 Можно запускать бота: python bot.py")
else:
    print("❌ ПРОБЛЕМА: Токен НЕ загружен!")
    print("\n🔧 Проверьте:")
    print("   1. Файл .env находится в той же папке, что и bot.py")
    print("   2. Формат: TELEGRAM_BOT_TOKEN=ваш_токен (без кавычек)")
    print("   3. Нет пробелов вокруг знака =")
    print("   4. Файл сохранен в кодировке UTF-8")
print("="*60 + "\n")
