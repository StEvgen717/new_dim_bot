"""Точка входу бота Estate Atlas."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import TELEGRAM_BOT_TOKEN
from handlers import add_object, common, search

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задано. Перевірте файл bot/.env")

    # Без parse_mode="HTML": адреси/описи/посилання на оголошення вводять
    # користувачі й часто містять символи "&", "<", ">" (напр. у URL),
    # які HTML-режим намагався б тлумачити як розмітку/сутності.
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Порядок важливий: common.router має першим перехоплювати /start,
    # "🚀 РОЗПОЧАТИ" та "📝 Головне меню" незалежно від поточного кроку
    # майстра додавання/пошуку.
    dp.include_router(common.router)
    dp.include_router(add_object.router)
    dp.include_router(search.router)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запускається (polling)...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
