# ===== handlers/cities.py (оновлено під aiogram 3 з "Назад", пошуком, головним меню та кнопкою "Розпочати") =====
from aiogram import types, Router, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from gspread_client import list_cities, list_streets, list_users_by_street, get_user_by_contract_or_name
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
ADMINS = [int(id_) for id_ in os.getenv("ADMINS", "").split(",") if id_]

router = Router()
user_states = {}  # user_id: (city, street)

# Отримання поточного місяця українською
MONTHS_UA = {
    1: "Січень", 2: "Лютий", 3: "Березень", 4: "Квітень",
    5: "Травень", 6: "Червень", 7: "Липень", 8: "Серпень",
    9: "Вересень", 10: "Жовтень", 11: "Листопад", 12: "Грудень"
}

# ціна за мішок
BAG_PRICE = 27.65

@router.message(Command("start"))
async def start_handler(message: types.Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 РОЗПОЧАТИ")]
        ],
        resize_keyboard=True
    )
    await message.answer("Натисніть кнопку нижче, щоб почати:", reply_markup=keyboard)

@router.message(F.text)
async def handle_all_text(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if text == "🚀 РОЗПОЧАТИ" or text == "📝 Головне меню":
        user_states[user_id] = (None, None)
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Обрати населений пункт")],
                [KeyboardButton(text="Пошук за договором")]
            ],
            resize_keyboard=True
        )
        await message.answer("Виберіть дію:", reply_markup=keyboard)
        return

    if text == "Обрати населений пункт":
        user_states[user_id] = (None, None)
        cities = list_cities()
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=city)] for city in cities] + [[KeyboardButton(text="📝 Головне меню")]],
            resize_keyboard=True
        )
        await message.answer("Оберіть населений пункт:", reply_markup=keyboard)
        return

    if text == "Пошук за договором":
        user_states[user_id] = (None, "search")
        await message.answer("Введіть номер договору (наприклад: 1000) або ПІБ (наприклад: Гончар Леся Петрівна):")
        return

    if text == "🔙 Назад":
        city, street = user_states.get(user_id, (None, None))
        if street and city:
            streets = list_streets(city)
            keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=s)] for s in streets] + [[KeyboardButton(text="🔙 Назад"), KeyboardButton(text="📝 Головне меню")]],
                resize_keyboard=True
            )
            user_states[user_id] = (city, None)
            await message.answer("Оберіть вулицю:", reply_markup=keyboard)
        elif city:
            cities = list_cities()
            keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=city)] for city in cities] + [[KeyboardButton(text="📝 Головне меню")]],
                resize_keyboard=True
            )
            user_states[user_id] = (None, None)
            await message.answer("Оберіть населений пункт:", reply_markup=keyboard)
        else:
            await start_handler(message)
        return

    state = user_states.get(user_id, (None, None))

    # Якщо ми в пошуку
    if state[1] == "search":
        try:
            search_input = text.strip().lower()
            result = get_user_by_contract_or_name(search_input)
        except Exception as e:
            await message.answer("⚠️ Сталася помилка під час обробки пошуку. Перевірте формат введених даних або зверніться до адміністратора.")
            return

        if isinstance(result, dict) and result.get("message") == "multiple":
            await message.answer(f"Знайдено декілька користувачів з таким ПІБ. Введіть номер договору для уточнення.")
        elif result:
            name = result['ПІБ']
            house = result['№ будинку']
            contract = str(result['номер договору'])
            bags = int(result['кількість мішків'])

            raw_payment = str(result.get(MONTHS_UA[datetime.now().month], "")).strip().replace(",", ".")
            try:
                payment = float(raw_payment)
            except ValueError:
                payment = 0.0
            required = bags * BAG_PRICE

            if payment >= required:
                status = "✅ ОПЛАЧЕНО"
            elif 0 < payment < required:
                paid_bags = round(payment / BAG_PRICE, 1)
                status = f"❗️УВАГА  ОПЛАЧЕНО за {paid_bags} мішок(и)"
            else:
                status = "❌ НЕ ОПЛАЧЕНО"

            msg = f"Буд. {house}: {name} | Договір №{contract} | Мішки: {bags} | {status}"
        else:
            msg = "Мешканця не знайдено. Введіть номер договору (наприклад: 1000) або ПІБ (наприклад: Гончар Леся Петрівна). Перевірте, щоб ім’я було повністю: Прізвище Ім’я По батькові."

        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📝 Головне меню")]],
            resize_keyboard=True
        )
        await message.answer(msg, reply_markup=keyboard)
        return

    cities = list_cities()
    if text in cities:
        user_states[user_id] = (text, None)
        streets = list_streets(text)
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=street)] for street in streets] + [[KeyboardButton(text="🔙 Назад"), KeyboardButton(text="📝 Головне меню")]],
            resize_keyboard=True
        )
        await message.answer("Оберіть вулицю:", reply_markup=keyboard)
        return

    city, street = user_states.get(user_id, (None, None))
    if city:
        user_states[user_id] = (city, text)
        residents = list_users_by_street(city, text)
        if not residents:
            await message.answer("Мешканців не знайдено")
        else:
            current_month = MONTHS_UA[datetime.now().month]
            msg = "Список мешканців\n"
            for person in residents:
                name = person['ПІБ']
                house = person['№ будинку']
                contract = str(person['номер договору'])
                bags = int(person['кількість мішків'])

                raw_payment = str(person.get(current_month, "")).strip().replace(",", ".")
                try:
                    payment = float(raw_payment)
                except ValueError:
                    payment = 0.0

                required = bags * BAG_PRICE

                if payment >= required:
                    status = "✅ ОПЛАЧЕНО"
                elif 0 < payment < required:
                    paid_bags = round(payment / BAG_PRICE, 1)
                    status = f"❗️УВАГА  ОПЛАЧЕНО за {paid_bags} мішок(и)"
                else:
                    status = "❌ НЕ ОПЛАЧЕНО"

                msg += f"Буд. {house}: {name} | Договір №{contract} | Мішки: {bags} | {status}\n"

            keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🔙 Назад"), KeyboardButton(text="📝 Головне меню")]],
                resize_keyboard=True
            )
            await message.answer(msg, reply_markup=keyboard)
    else:
        await message.answer("Будь ласка, спочатку оберіть населений пункт.")
