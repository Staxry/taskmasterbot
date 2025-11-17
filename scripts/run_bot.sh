#!/bin/bash
# Обёртка для запуска Python бота через Replit workflow

echo "🤖 Starting Telegram Bot (Python)..."
echo ""

# Останавливаем старые процессы
pkill -f "python bot.py" 2>/dev/null
sleep 1

# Запускаем бота
exec python bot.py
