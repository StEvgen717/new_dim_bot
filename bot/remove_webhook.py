"""Утиліта: видалити вебхук, якщо бот раніше працював у режимі webhook.

Запускати окремо лише за потреби (main.py тепер робить це автоматично
перед запуском polling, тож зазвичай цей скрипт не потрібен):
    python remove_webhook.py
"""
import asyncio
import logging

from aiogram import Bot

from config import TELEGRAM_BOT_TOKEN

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def delete_webhook() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задано. Перевірте файл bot/.env")

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ Webhook успішно видалено. Можна запускати бота з polling.")


if __name__ == "__main__":
    asyncio.run(delete_webhook())
