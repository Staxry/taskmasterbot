# Overview

Это полноценный асинхронный Telegram бот для управления задачами, построенный на Python с использованием библиотеки **aiogram**. Бот работает по командам (без AI) и использует **polling** (постоянное опрашивание Telegram API) вместо webhook - **полностью бесплатно**!

Система демонстрирует производственно-готовую реализацию:
- Асинхронный бот на aiogram 3.22 с polling
- Система управления задачами с ролевым доступом (admin/employee)
- База данных PostgreSQL для хранения пользователей и задач
- Команды на русском языке
- Полностью бесплатная работа (без затрат на AI)

## Current Status (November 17, 2025)

✅ **Готов к использованию (Python + Aiogram + Polling)**

Все компоненты реализованы на Python и протестированы:
- База данных PostgreSQL с таблицами users, tasks и allowed_users
- Асинхронный бот на aiogram с polling (без webhook)
- Интерактивные inline-кнопки для всех команд
- Система whitelist авторизации по username
- Валидация прав доступа (admin vs employee)
- FSM для создания задач и добавления пользователей
- Обработка ошибок и валидация данных
- **Полностью бесплатно** - без затрат на AI API

**Последние изменения (17 ноября 2025):**
- ✅ Полностью переписан на Python + aiogram
- ✅ Удалены все TypeScript/Mastra файлы
- ✅ Использован polling вместо webhook (работает сразу, без публикации)
- ✅ Добавлены inline-кнопки для всех команд
- ✅ Система whitelist авторизации по username
- ✅ Кнопки "Добавить админа" и "Добавить сотрудника"
- ✅ Блокировка доступа для неавторизованных пользователей
- ✅ Очистка проекта от лишних файлов

**Как использовать:**
1. Бот уже запущен и работает в фоне
2. Откройте Telegram и найдите вашего бота (username из @BotFather)
3. Отправьте `/start` для регистрации
4. Используйте `/help` для просмотра команд

# User Preferences

Preferred communication style: Simple, everyday language (Russian).

# System Architecture

## Core Framework

**Python 3.11 + aiogram 3.22** - основа приложения:
- Асинхронная обработка команд через asyncio
- Polling режим (постоянное опрашивание Telegram API)
- MemoryStorage для FSM (Finite State Machine)
- Автоматическая обработка обновлений от Telegram

## Database Layer

**PostgreSQL с psycopg2** для работы с данными:
- **Schema Design**: Три основные таблицы (users, tasks, allowed_users) с enum типами для ролей, приоритетов и статусов
- **Relations**: Foreign key связи между users и tasks (assigned_to_id, created_by_id)
- **Connection**: Синхронный драйвер psycopg2 с подключением через `DATABASE_URL`
- **Migration Strategy**: Схема создана через Drizzle (из предыдущей версии)

**Key Entities**:
- **Users**: Telegram ID (unique), username, role (admin/employee), timestamps
- **Tasks**: Title, description, priority (low/medium/high/urgent), status (pending/in_progress/completed/rejected), due date, assignment tracking
- **Allowed Users**: Username (unique), role, added_by_id (FK → users.id), created_at - whitelist для авторизации

## Bot Architecture

**Aiogram Handlers** (bot.py) обрабатывают команды Telegram:
- Декораторы @dp.message для регистрации обработчиков
- Command filters для фильтрации команд
- Асинхронные функции для обработки запросов
- Прямое взаимодействие с PostgreSQL через psycopg2
- Валидация прав доступа на уровне обработчиков

**Handler Pattern**: Каждая команда имеет свой асинхронный обработчик, который:
1. Получает или создаёт пользователя в БД
2. Проверяет права доступа
3. Выполняет операцию с БД
4. Отправляет ответ через Telegram Bot API

## Polling vs Webhook

**Текущая реализация: Polling**
- ✅ Работает сразу после запуска
- ✅ Не требует публикации Replit приложения
- ✅ Не требует HTTPS сертификата
- ✅ Проще в настройке и отладке
- Бот постоянно опрашивает Telegram API на наличие новых сообщений

**Преимущества polling для разработки:**
- Мгновенный запуск - просто `python bot.py`
- Не нужно настраивать webhook URL
- Легко тестировать локально
- Подходит для Replit (бесплатный tier)

## Design Decisions

**Почему Python + aiogram**: Простота разработки, отличная документация, асинхронность из коробки, большое сообщество.

**Почему Polling**: Проще в настройке, работает без публикации, идеально для разработки и тестирования.

**Почему PostgreSQL**: Надёжная реляционная БД с поддержкой транзакций, foreign keys, и сложных запросов.

**Почему без AI**: Полностью бесплатная работа, предсказуемое поведение, быстрая обработка команд.

# External Dependencies

## AI/LLM Services
- **None**: Бот работает без AI - только команды

## Database & Storage
- **PostgreSQL**: Основная база данных (подключение через `DATABASE_URL`)
- **psycopg2-binary**: Синхронный PostgreSQL драйвер (v2.9.11)
- **asyncpg**: Асинхронный PostgreSQL драйвер (v0.30.0) - установлен, но не используется

## Telegram Integration
- **aiogram**: Асинхронная библиотека для Telegram Bot API (v3.22.0)
- **aiohttp**: HTTP клиент для асинхронных запросов (v3.12.15)
- **Telegram Bot API**: Взаимодействие через polling

## Utilities
- **python-dotenv**: Загрузка environment variables (v1.2.1)
- **typing-extensions**: Расширенная поддержка типов (v4.15.0)

## Development
- **Python**: v3.11
- **uv**: Менеджер пакетов (используется Replit)

# File Structure

```
.
├── bot.py              # Основной файл бота (aiogram)
├── README.md           # Документация на русском
├── replit.md           # Этот файл (архитектура проекта)
├── START_BOT.sh        # Скрипт запуска бота
├── pyproject.toml      # Python зависимости (управляется uv)
└── uv.lock             # Версии пакетов
```

**Все лишние файлы удалены:**
- ❌ TypeScript файлы (shared/, *.ts)
- ❌ Node.js зависимости (package.json, node_modules)
- ❌ Mastra документация (docs/)
- ❌ Дубликаты README

# Available Commands

## Общие команды
- `/start` или `/старт` - Регистрация / приветствие
- `/help` или `/помощь` - Список команд

## Команды для всех пользователей
- `/my_tasks` или `/мои_задачи` - Список ваших задач
- `/task_details <ID>` или `/детали_задачи <ID>` - Детали задачи
- `/update_status <ID> <статус>` или `/обновить_статус <ID> <статус>` - Обновить статус

## Команды администратора
- `/create_task` или `/создать_задачу` - Создать задачу
- `/all_tasks` или `/все_задачи` - Все задачи в системе

## Формат создания задачи

```
/create_task title:"название" description:"описание" priority:high due_date:2025-12-25 assigned_to:telegram_id
```

**Параметры:**
- `title:"..."` - название (обязательно)
- `description:"..."` - описание (опционально)
- `priority:` - low/medium/high/urgent (по умолчанию: medium)
- `due_date:` - YYYY-MM-DD (опционально)
- `assigned_to:` - telegram_id сотрудника (опционально)

# How It Works

1. **Запуск**: `python bot.py` запускает бота в режиме polling
2. **Polling**: Бот каждые ~0.5 секунд опрашивает Telegram API
3. **Получение команды**: Telegram API возвращает новые сообщения
4. **Обработка**: Aiogram вызывает соответствующий handler
5. **База данных**: Handler работает с PostgreSQL через psycopg2
6. **Ответ**: Бот отправляет ответ через Telegram Bot API

# Running the Bot

## Локальный запуск

```bash
python bot.py
```

Или в фоне:

```bash
nohup python bot.py > /tmp/telegram_bot.log 2>&1 &
```

## Проверка статуса

```bash
# Проверить процесс
ps aux | grep "python bot.py"

# Посмотреть логи
tail -f /tmp/telegram_bot.log
```

## Остановка

```bash
pkill -f "python bot.py"
```

# Getting Admin Role

По умолчанию все новые пользователи регистрируются как **employee**.

Для получения роли администратора:

```sql
UPDATE users SET role = 'admin' WHERE telegram_id = 'ваш_telegram_id';
```

Узнать свой Telegram ID:
1. Отправьте `/start` боту
2. Откройте Database pane в Replit
3. Выполните: `SELECT * FROM users ORDER BY created_at DESC LIMIT 5;`

# Troubleshooting

## Бот не отвечает

1. Проверьте процесс: `ps aux | grep python`
2. Проверьте логи: `tail -f /tmp/telegram_bot.log`
3. Проверьте токен: `echo $TELEGRAM_BOT_TOKEN`
4. Перезапустите: `pkill -f python && python bot.py &`

## Ошибка Token is invalid

Токен должен быть из @BotFather без пробелов и переносов строк.

## База данных не работает

Проверьте подключение:
```bash
psql $DATABASE_URL -c "SELECT COUNT(*) FROM users;"
```

# Future Improvements

- [ ] Inline-кнопки для быстрых действий
- [ ] Напоминания о дедлайнах
- [ ] Статистика по задачам
- [ ] Экспорт отчётов
- [ ] Фильтрация задач
- [ ] Поиск по ключевым словам
