#!/bin/bash

# =================================================================
# Telegram Task Manager Bot - Start Script
# Интерактивное меню для управления ботом
# =================================================================

BOT_NAME="telegram_task_bot"
BOT_SCRIPT="bot.py"
BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="telegram-task-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
LOG_FILE="$BOT_DIR/logs/bot.log"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для красивого вывода
print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Проверка запущен ли бот
check_bot_status() {
    if pgrep -f "python.*$BOT_SCRIPT" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# Запуск бота в обычном режиме
start_bot() {
    print_header "Запуск бота"
    
    if check_bot_status; then
        print_warning "Бот уже запущен!"
        return 1
    fi
    
    print_info "Запускаю бота в фоновом режиме..."
    cd "$BOT_DIR"
    
    # Создаем директорию для логов если её нет
    mkdir -p logs
    
    # Запускаем бота в фоне
    nohup python3 bot.py > logs/bot.log 2>&1 &
    
    sleep 3
    
    if check_bot_status; then
        print_success "Бот успешно запущен!"
        print_info "PID: $(pgrep -f "python.*$BOT_SCRIPT")"
        print_info "Логи: $LOG_FILE"
    else
        print_error "Не удалось запустить бота. Проверьте логи:"
        tail -20 logs/bot.log
    fi
}

# Остановка бота
stop_bot() {
    print_header "Остановка бота"
    
    if ! check_bot_status; then
        print_warning "Бот не запущен!"
        return 1
    fi
    
    print_info "Останавливаю бота..."
    pkill -f "python.*$BOT_SCRIPT"
    sleep 2
    
    if ! check_bot_status; then
        print_success "Бот остановлен!"
    else
        print_warning "Бот не остановился, принудительное завершение..."
        pkill -9 -f "python.*$BOT_SCRIPT"
        sleep 1
        if ! check_bot_status; then
            print_success "Бот принудительно остановлен!"
        else
            print_error "Не удалось остановить бота!"
        fi
    fi
}

# Перезапуск бота
restart_bot() {
    print_header "Перезапуск бота"
    stop_bot
    sleep 2
    start_bot
}

# Статус бота
show_status() {
    print_header "Статус бота"
    
    if check_bot_status; then
        print_success "Бот запущен"
        print_info "PID: $(pgrep -f "python.*$BOT_SCRIPT")"
        print_info "Логи: $LOG_FILE"
        echo ""
        print_info "Последние 10 строк логов:"
        tail -10 "$LOG_FILE" 2>/dev/null || echo "Логи пока пусты"
    else
        print_warning "Бот не запущен"
    fi
}

# Просмотр логов
view_logs() {
    print_header "Просмотр логов"
    
    if [ ! -f "$LOG_FILE" ]; then
        print_warning "Файл логов не найден: $LOG_FILE"
        return 1
    fi
    
    echo -e "${BLUE}Последние 50 строк логов:${NC}"
    tail -50 "$LOG_FILE"
    echo ""
    print_info "Полный путь к логам: $LOG_FILE"
    print_info "Для просмотра всех логов: cat $LOG_FILE"
    print_info "Для отслеживания в реальном времени: tail -f $LOG_FILE"
}

# Установка на Ubuntu Server
install_ubuntu_service() {
    print_header "Установка systemd службы"
    
    # Проверка прав
    if [ "$EUID" -ne 0 ]; then 
        print_error "Для установки службы нужны права root"
        print_info "Запустите: sudo $0"
        return 1
    fi
    
    print_info "Создаю systemd service файл..."
    
    # Определяем пользователя
    if [ -n "$SUDO_USER" ]; then
        RUN_USER="$SUDO_USER"
    else
        RUN_USER="$(whoami)"
    fi
    
    # Создаем service файл
    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Telegram Task Manager Bot
After=network.target postgresql.service

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$BOT_DIR
Environment="PATH=$PATH"
ExecStart=/usr/bin/python3 $BOT_DIR/bot.py
Restart=always
RestartSec=10

# Логирование
StandardOutput=append:$LOG_FILE
StandardError=append:$LOG_FILE

[Install]
WantedBy=multi-user.target
EOF
    
    print_success "Service файл создан: $SERVICE_FILE"
    
    # Перезагружаем systemd
    print_info "Перезагружаю systemd..."
    systemctl daemon-reload
    
    # Включаем автозапуск
    print_info "Включаю автозапуск..."
    systemctl enable $SERVICE_NAME
    
    print_success "Служба успешно установлена!"
    echo ""
    print_info "Доступные команды:"
    echo "  sudo systemctl start $SERVICE_NAME    - Запустить бота"
    echo "  sudo systemctl stop $SERVICE_NAME     - Остановить бота"
    echo "  sudo systemctl restart $SERVICE_NAME  - Перезапустить бота"
    echo "  sudo systemctl status $SERVICE_NAME   - Статус бота"
    echo "  journalctl -u $SERVICE_NAME -f        - Логи в реальном времени"
}

# Управление systemd службой
manage_service() {
    print_header "Управление systemd службой"
    
    if [ ! -f "$SERVICE_FILE" ]; then
        print_error "Служба не установлена!"
        print_info "Сначала выполните установку (опция 6)"
        return 1
    fi
    
    echo "Выберите действие:"
    echo "1) Запустить службу"
    echo "2) Остановить службу"
    echo "3) Перезапустить службу"
    echo "4) Статус службы"
    echo "5) Включить автозапуск"
    echo "6) Отключить автозапуск"
    echo "7) Просмотреть логи"
    echo "0) Назад"
    echo ""
    read -p "Ваш выбор: " choice
    
    case $choice in
        1)
            sudo systemctl start $SERVICE_NAME
            print_success "Служба запущена"
            ;;
        2)
            sudo systemctl stop $SERVICE_NAME
            print_success "Служба остановлена"
            ;;
        3)
            sudo systemctl restart $SERVICE_NAME
            print_success "Служба перезапущена"
            ;;
        4)
            sudo systemctl status $SERVICE_NAME
            ;;
        5)
            sudo systemctl enable $SERVICE_NAME
            print_success "Автозапуск включен"
            ;;
        6)
            sudo systemctl disable $SERVICE_NAME
            print_success "Автозапуск отключен"
            ;;
        7)
            sudo journalctl -u $SERVICE_NAME -n 50
            ;;
        0)
            return 0
            ;;
        *)
            print_error "Неверный выбор!"
            ;;
    esac
}

# Главное меню
show_menu() {
    clear
    print_header "Telegram Task Manager Bot - Управление"
    echo ""
    
    # Показываем статус
    if check_bot_status; then
        echo -e "${GREEN}● Бот запущен${NC} (PID: $(pgrep -f "python.*$BOT_SCRIPT"))"
    else
        echo -e "${RED}● Бот остановлен${NC}"
    fi
    
    # Проверяем службу
    if [ -f "$SERVICE_FILE" ]; then
        if systemctl is-enabled $SERVICE_NAME &>/dev/null; then
            echo -e "${GREEN}● Служба установлена и включена${NC}"
        else
            echo -e "${YELLOW}● Служба установлена но отключена${NC}"
        fi
    fi
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "1) Запустить бота"
    echo "2) Остановить бота"
    echo "3) Перезапустить бота"
    echo "4) Показать статус"
    echo "5) Просмотреть логи"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "6) Установить systemd службу (Ubuntu)"
    echo "7) Управление службой"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "0) Выход"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

# Основной цикл
main() {
    while true; do
        show_menu
        read -p "Выберите действие: " choice
        echo ""
        
        case $choice in
            1)
                start_bot
                ;;
            2)
                stop_bot
                ;;
            3)
                restart_bot
                ;;
            4)
                show_status
                ;;
            5)
                view_logs
                ;;
            6)
                install_ubuntu_service
                ;;
            7)
                manage_service
                ;;
            0)
                print_info "Выход..."
                exit 0
                ;;
            *)
                print_error "Неверный выбор! Попробуйте снова."
                ;;
        esac
        
        echo ""
        read -p "Нажмите Enter для продолжения..."
    done
}

# Запуск
main
