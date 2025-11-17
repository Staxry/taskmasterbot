#!/bin/bash
# Скрипт для запуска Telegram бота

echo "🤖 Запуск Telegram бота..."

# Останавливаем старые процессы
pkill -f "python bot.py" 2>/dev/null

# Запускаем бота в фоне
nohup python bot.py > /tmp/telegram_bot.log 2>&1 &

sleep 3

# Проверяем статус
if pgrep -f "python bot.py" > /dev/null; then
    echo "✅ Бот запущен успешно!"
    echo ""
    echo "📝 Для просмотра логов: tail -f /tmp/telegram_bot.log"
    echo "🛑 Для остановки: pkill -f 'python bot.py'"
else
    echo "❌ Ошибка запуска. Проверьте логи: cat /tmp/telegram_bot.log"
fi
