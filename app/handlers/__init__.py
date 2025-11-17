"""
Handler modules for Telegram bot commands and callbacks
"""
from aiogram import Router

# Создаем роутеры для разных групп обработчиков
core_router = Router()
statuses_router = Router()
photos_router = Router()

__all__ = [
    'core_router',
    'statuses_router',
    'photos_router'
]
