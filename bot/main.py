# main.py
import asyncio
from aiogram import Bot, Dispatcher
from handlers import cities
from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(cities.router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
