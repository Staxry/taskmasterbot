# 📦 Инструкция по установке бота на сервер

## 🔧 Предварительные требования

- **Python 3.11** или выше
- **PostgreSQL** 12 или выше
- Доступ к серверу через SSH
- Telegram Bot Token (получить у [@BotFather](https://t.me/BotFather))

## 📋 Шаг 1: Установка зависимостей

### На Ubuntu/Debian:
```bash
# Обновите систему
sudo apt update && sudo apt upgrade -y

# Установите Python и PostgreSQL
sudo apt install python3 python3-pip python3-venv postgresql postgresql-contrib -y

# Установите git (если нужно)
sudo apt install git -y
```

### На CentOS/RHEL:
```bash
sudo yum update -y
sudo yum install python3 python3-pip postgresql-server postgresql-contrib git -y
sudo postgresql-setup initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

## 📂 Шаг 2: Клонирование проекта

```bash
# Перейдите в нужную директорию
cd /home/your_user

# Клонируйте или загрузите проект
# git clone your_repository_url task-bot
# или загрузите архив и распакуйте

cd task-bot
```

## 🗄️ Шаг 3: Настройка PostgreSQL

```bash
# Войдите в PostgreSQL
sudo -u postgres psql

# Создайте базу данных и пользователя
CREATE DATABASE task_bot;
CREATE USER bot_user WITH PASSWORD 'your_strong_password';
GRANT ALL PRIVILEGES ON DATABASE task_bot TO bot_user;
\q
```

**Важно:** Запомните имя базы данных, пользователя и пароль — они понадобятся для `.env` файла.

## ⚙️ Шаг 4: Настройка переменных окружения

Создайте файл `.env` на основе примера:

```bash
cp .env.example .env
nano .env
```

### Обязательные настройки в `.env`:

```env
# 1. TELEGRAM_BOT_TOKEN - получите у @BotFather
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# 2. DATABASE_URL - строка подключения к PostgreSQL
DATABASE_URL=postgresql://bot_user:your_strong_password@localhost:5432/task_bot

# 3. SESSION_SECRET - любая случайная строка
SESSION_SECRET=my_super_secret_random_string_12345

# 4. TIMEZONE - ваш часовой пояс (опционально)
TIMEZONE=Europe/Kaliningrad
```

### Как получить Telegram Bot Token:

1. Откройте Telegram и найдите [@BotFather](https://t.me/BotFather)
2. Отправьте команду `/newbot`
3. Следуйте инструкциям (выберите имя и username бота)
4. BotFather пришлёт вам токен вида `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`
5. Скопируйте токен в файл `.env`

## 📦 Шаг 5: Установка Python зависимостей

```bash
# Создайте виртуальное окружение
python3 -m venv venv

# Активируйте его
source venv/bin/activate

# Установите зависимости
pip install --upgrade pip
pip install -r requirements_deploy.txt
```

## 👥 Шаг 6: Добавление пользователей в whitelist

Перед первым запуском добавьте администраторов в базу данных:

```bash
# Подключитесь к базе
psql -U bot_user -d task_bot

# Добавьте администратора (замените username на ваш Telegram username БЕЗ @)
INSERT INTO allowed_users (username, role) VALUES ('your_telegram_username', 'admin');

# Добавьте сотрудников (опционально)
INSERT INTO allowed_users (username, role) VALUES ('employee_username', 'employee');

# Выход
\q
```

**Важно:** Используйте ваш Telegram username **без символа @**.

## 🚀 Шаг 7: Запуск бота

### Вариант 1: Ручной запуск (для тестирования)

```bash
# Активируйте виртуальное окружение
source venv/bin/activate

# Запустите бота
python3 bot.py
```

Для остановки нажмите `Ctrl+C`.

### Вариант 2: Запуск с помощью скрипта

```bash
# Сделайте скрипт исполняемым
chmod +x START_BOT.sh

# Запустите
./START_BOT.sh
```

Скрипт предложит меню с опциями: старт, стоп, рестарт, статус, установка как сервис.

### Вариант 3: Автозапуск через systemd (рекомендуется)

Используйте интерактивный скрипт:

```bash
./START_BOT.sh
# Выберите опцию 5: "Install as systemd service"
```

Или создайте сервис вручную:

```bash
sudo nano /etc/systemd/system/task-bot.service
```

Содержимое файла:

```ini
[Unit]
Description=Telegram Task Management Bot
After=network.target postgresql.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/home/your_user/task-bot
Environment="PATH=/home/your_user/task-bot/venv/bin"
ExecStart=/home/your_user/task-bot/venv/bin/python3 /home/your_user/task-bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Замените `your_user` на ваше имя пользователя.

Активируйте сервис:

```bash
sudo systemctl daemon-reload
sudo systemctl enable task-bot
sudo systemctl start task-bot
```

Проверьте статус:

```bash
sudo systemctl status task-bot
```

Просмотр логов:

```bash
# Логи systemd
sudo journalctl -u task-bot -f

# Логи бота
tail -f logs/bot.log
```

## 🔧 Шаг 8: Проверка работы

1. Откройте Telegram
2. Найдите вашего бота по username
3. Отправьте команду `/start`
4. Если вы добавлены в whitelist, бот ответит главным меню

## 📝 Настройка часового пояса

По умолчанию установлен **Europe/Kaliningrad (UTC+2)**.

Для изменения:

1. Откройте файл `.env`
2. Измените строку `TIMEZONE=`:

```env
# Для Москвы
TIMEZONE=Europe/Moscow

# Для Киева
TIMEZONE=Europe/Kiev

# Для Алматы
TIMEZONE=Asia/Almaty

# Для Минска
TIMEZONE=Europe/Minsk
```

3. Перезапустите бота

## 🔄 Обновление бота

```bash
# Остановите бота
sudo systemctl stop task-bot
# или ./START_BOT.sh -> выберите "Stop bot"

# Обновите код (если используете git)
git pull

# Обновите зависимости
source venv/bin/activate
pip install --upgrade -r requirements_deploy.txt

# Запустите бота
sudo systemctl start task-bot
# или ./START_BOT.sh -> выберите "Start bot"
```

## 🛡️ Рекомендации по безопасности

1. **Никогда не публикуйте файл `.env`** в публичных репозиториях
2. Используйте **сильные пароли** для базы данных
3. Настройте **фаервол** на сервере:
   ```bash
   sudo ufw allow OpenSSH
   sudo ufw enable
   ```
4. Регулярно **обновляйте систему**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
5. Настройте **автоматическое резервное копирование** базы данных:
   ```bash
   # Добавьте в crontab
   crontab -e
   # Добавьте строку (бэкап каждый день в 3:00)
   0 3 * * * pg_dump -U bot_user task_bot > /home/your_user/backups/task_bot_$(date +\%Y\%m\%d).sql
   ```

## 📊 Мониторинг

### Просмотр логов:
```bash
# Последние 50 строк
tail -50 logs/bot.log

# Постоянный просмотр (live)
tail -f logs/bot.log

# Поиск ошибок
grep ERROR logs/bot.log
```

### Проверка статуса:
```bash
# Статус сервиса
sudo systemctl status task-bot

# Проверка процесса
ps aux | grep bot.py
```

## ❓ Решение проблем

### Бот не запускается:
1. Проверьте правильность `TELEGRAM_BOT_TOKEN` в `.env`
2. Проверьте подключение к базе данных:
   ```bash
   psql -U bot_user -d task_bot
   ```
3. Проверьте логи:
   ```bash
   tail -100 logs/bot.log
   ```

### База данных не подключается:
1. Убедитесь, что PostgreSQL запущен:
   ```bash
   sudo systemctl status postgresql
   ```
2. Проверьте правильность `DATABASE_URL` в `.env`
3. Проверьте права доступа пользователя к базе

### Бот не отвечает на команды:
1. Убедитесь, что ваш Telegram username добавлен в `allowed_users`
2. Проверьте, что бот запущен:
   ```bash
   sudo systemctl status task-bot
   ```
3. Проверьте логи на ошибки

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи бота в `logs/bot.log`
2. Проверьте логи systemd: `sudo journalctl -u task-bot -n 100`
3. Убедитесь, что все зависимости установлены
4. Проверьте корректность настроек в `.env`

---

**Готово!** Ваш бот установлен и работает. 🎉
