"""
Logging configuration module
Настройка логирования в файл и консоль с ротацией
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from app.config import LOG_FILE, LOG_LEVEL, LOG_MAX_BYTES, LOG_BACKUP_COUNT


def setup_logging():
    """
    Настройка логирования с выводом в файл и консоль
    - Ротация логов при достижении LOG_MAX_BYTES
    - Хранение LOG_BACKUP_COUNT файлов
    - Формат: время - модуль - уровень - сообщение
    """
    # Создаем директорию для логов если её нет
    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Получаем корневой логгер
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    
    # Очищаем существующие обработчики
    logger.handlers.clear()
    
    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Обработчик для файла с ротацией
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Логируем начало работы
    logger.info("=" * 60)
    logger.info("📝 Logging configured successfully")
    logger.info(f"📁 Log file: {LOG_FILE}")
    logger.info(f"📊 Log level: {LOG_LEVEL}")
    logger.info("=" * 60)
    
    return logger


def get_logger(name: str = __name__):
    """Получить логгер для модуля"""
    return logging.getLogger(name)
