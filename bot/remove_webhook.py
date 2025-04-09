# remove_webhook.py

import asyncio
from aiogram import Bot
from dotenv import load_dotenv
import os

# Завантажуємо токен із .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def delete_webhook():
    bot = Bot(token=BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    print("\n✅ Webhook успішно видалено. Можна запускати бота з polling.\n")

if __name__ == "__main__":
    asyncio.run(delete_webhook())