"""Точка входа приложения"""
import logging
from telegram.ext import Application

from bot.handlers import setup_handlers
from sheets.client import get_client
import config

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Основная функция"""
    try:
        # Инициализируем листы при первом запуске
        logger.info("Инициализация Google Sheets...")
        client = get_client()
        client.initialize_sheets()
        logger.info("Инициализация завершена")
    except Exception as e:
        logger.error(f"Ошибка при инициализации: {e}")
        logger.warning("Продолжаем запуск, но некоторые функции могут не работать")
    
    # Создаем приложение
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # Настраиваем обработчики
    setup_handlers(application)
    
    # Запускаем бота
    logger.info("Запуск бота...")
    application.run_polling()


if __name__ == "__main__":
    main()

