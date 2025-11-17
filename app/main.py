"""
Main bot initialization module
Создание экземпляра бота и регистрация всех роутеров
"""
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from app.config import BOT_TOKEN
from app.logging_config import setup_logging, get_logger
from app.database import init_database

# Инициализация логирования
setup_logging()
logger = get_logger(__name__)

# Создаем экземпляр бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def register_routers():
    """
    Регистрация всех роутеров в диспетчере
    Порядок важен: сначала более специфичные, потом общие
    """
    logger.info("📝 Registering routers...")
    
    # ВАЖНО: Импортируем handler модули, чтобы декораторы @router выполнились
    # Это загрузит все обработчики и зарегистрирует их в роутерах
    from app.handlers import core_router, statuses_router, photos_router
    import app.handlers.core
    import app.handlers.statuses
    import app.handlers.photos
    
    # Регистрируем в правильном порядке
    dp.include_router(photos_router)
    dp.include_router(statuses_router)
    dp.include_router(core_router)
    
    logger.info("✅ All routers registered successfully")


async def on_startup():
    """
    Действия при запуске бота
    """
    logger.info("=" * 60)
    logger.info("🚀 Bot is starting...")
    logger.info("=" * 60)
    
    # Инициализация базы данных
    init_database()
    
    # Регистрация роутеров
    register_routers()
    
    logger.info("✅ Bot startup complete")


async def on_shutdown():
    """
    Действия при остановке бота
    """
    logger.info("=" * 60)
    logger.info("🛑 Bot is shutting down...")
    logger.info("=" * 60)
    
    # Закрываем сессию бота
    await bot.session.close()
    
    logger.info("✅ Bot shutdown complete")


async def main():
    """
    Главная функция запуска бота
    """
    try:
        # Выполняем действия при старте
        await on_startup()
        
        # Запускаем polling
        logger.info("🔄 Starting polling...")
        await dp.start_polling(bot, skip_updates=True)
        
    except KeyboardInterrupt:
        logger.info("⚠️ Received KeyboardInterrupt")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
    finally:
        # Выполняем действия при остановке
        await on_shutdown()


def run_bot():
    """
    Запуск бота через asyncio
    """
    asyncio.run(main())


if __name__ == '__main__':
    run_bot()
