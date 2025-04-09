# bot/handlers/cities.py (оновлено під aiogram 3)
from aiogram import types, Router, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from gspread_client import list_cities, list_streets, list_users_by_street
import os
from dotenv import load_dotenv

load_dotenv()
ADMINS = [int(id_) for id_ in os.getenv("ADMINS", "").split(",") if id_]

router = Router()
user_states = {}  # user_id: (city, street)

@router.message(Command("start"))
async def start_handler(message: types.Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=city)] for city in list_cities()],
        resize_keyboard=True
    )
    await message.answer("Оберіть населений пункт:", reply_markup=keyboard)

@router.message(F.text)
async def handle_city_or_street(message: types.Message):
    user_id = message.from_user.id
    cities = list_cities()
    if message.text in cities:
        user_states[user_id] = (message.text, None)
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=street)] for street in list_streets(message.text)],
            resize_keyboard=True
        )
        await message.answer("Оберіть вулицю:", reply_markup=keyboard)
    else:
        if user_id in user_states:
            city, _ = user_states[user_id]
            user_states[user_id] = (city, message.text)
            residents = list_users_by_street(city, message.text)
            if not residents:
                await message.answer("Мешканців не знайдено")
            else:
                msg = "Список мешканців\n"
                for person in residents:
                    msg += f"Буд. {person['№ будинку']}: {person['ПІБ']} | Договір №{person['номер договору']} | Мішки: {person['кількість мішків']}\n"
                await message.answer(msg)
