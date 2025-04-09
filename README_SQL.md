
# Telegram Бот з MySQL



## Як запускати:

1. Встанови залежності:
```
pip install aiogram mysql-connector-python python-dotenv
```
2. Створи базу даних через MySQL Workbench або:
```
mysql -u root -p < models.sql
```
3. Заповни `.env` своїми даними.
4. Запусти бота:
```
python main.py
```


📁 bot/
├── main.py              # Точка входу бота
├── db.py                # З'єднання з MySQL
├── handlers/
│   ├── __init__.py
│   └── cities.py        # Обробка команд та кнопок
├── models.sql           # SQL-скрипт для створення таблиць
├── .env                 # Конфігурації (токен, пароль)
└── README.md            # Інструкція по запуску

# ===== db.py =====
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

ADMINS = [int(id_) for id_ in os.getenv("ADMINS", "").split(",") if id_]

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# ===== main.py =====
from aiogram import Bot, Dispatcher, executor, types
from handlers import cities
import os
from dotenv import load_dotenv

load_dotenv()

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(bot)

cities.register_handlers(dp)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

# ===== handlers/cities.py =====
from aiogram import types, Dispatcher
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from db import get_connection, ADMINS

user_states = {}  # user_id: (city_id, street_id)

def register_handlers(dp: Dispatcher):

    @dp.message_handler(commands=["start"])
    async def start_handler(message: types.Message):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM cities")
        cities = cursor.fetchall()
        conn.close()

        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        for city_id, name in cities:
            keyboard.add(KeyboardButton(name))

        await message.answer("Оберіть місто:", reply_markup=keyboard)

    @dp.message_handler(lambda m: m.text)
    async def handle_city_or_street(message: types.Message):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM cities WHERE name = %s", (message.text,))
        city = cursor.fetchone()
        if city:
            city_id = city[0]
            user_states[message.from_user.id] = (city_id, None)
            cursor.execute("SELECT name FROM streets WHERE city_id = %s", (city_id,))
            streets = cursor.fetchall()
            conn.close()
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            for street in streets:
                keyboard.add(KeyboardButton(street[0]))
            await message.answer("Оберіть вулицю:", reply_markup=keyboard)
            return

        cursor.execute("SELECT id FROM streets WHERE name = %s", (message.text,))
        street = cursor.fetchone()
        if street:
            street_id = street[0]
            if message.from_user.id in user_states:
                city_id, _ = user_states[message.from_user.id]
                user_states[message.from_user.id] = (city_id, street_id)
                cursor.execute("""
                    SELECT id, surname, name, patronymic, contract_number, units, volume, payment_status 
                    FROM users WHERE street_id = %s
                """, (street_id,))
                users = cursor.fetchall()
                conn.close()
                if users:
                    msg = "Список мешканців:\n"
                    for u in users:
                        msg += f"ID: {u[0]} | {u[1]} {u[2]} {u[3]} | №: {u[4]} | Од.: {u[5]} | Обʼєм: {u[6]} | Статус: {u[7]}\n"
                    await message.answer(msg)
                else:
                    await message.answer("На цій вулиці ще немає мешканців")
                return
        conn.close()

    @dp.message_handler(commands=["add_city"])
    async def add_city(message: types.Message):
        if message.from_user.id not in ADMINS:
            return await message.answer("Доступ заборонено")

        name = message.get_args()
        if not name:
            return await message.answer("Введіть назву міста: /add_city Назва")

        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO cities (name) VALUES (%s)", (name,))
            conn.commit()
            await message.answer(f"Місто {name} додано")
        except:
            await message.answer("Помилка або місто вже існує")
        conn.close()

    @dp.message_handler(commands=["add_street"])
    async def add_street(message: types.Message):
        if message.from_user.id not in ADMINS:
            return await message.answer("Доступ заборонено")

        args = message.get_args().split(";")
        if len(args) != 2:
            return await message.answer("Формат: /add_street Назва;ID_міста")

        name, city_id = args
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO streets (name, city_id) VALUES (%s, %s)", (name, city_id))
            conn.commit()
            await message.answer(f"Вулицю {name} додано")
        except Exception as e:
            await message.answer(f"Помилка: {e}")
        conn.close()

    @dp.message_handler(commands=["add_user"])
    async def add_user(message: types.Message):
        if message.from_user.id not in ADMINS:
            return await message.answer("Доступ заборонено")

        args = message.get_args().split(";")
        if len(args) != 7:
            return await message.answer("Формат: /add_user Прізвище;Імʼя;По батькові;№договору;одиниці;обʼєм;id_вулиці")

        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (surname, name, patronymic, contract_number, units, volume, payment_status, street_id)
                VALUES (%s,%s,%s,%s,%s,%s,'НЕ СПЛАЧЕНО',%s)
            """, tuple(args))
            conn.commit()
            await message.answer("Користувача додано")
        except Exception as e:
            await message.answer(f"Помилка: {e}")
        conn.close()

    @dp.message_handler(commands=["change_status"])
    async def change_status(message: types.Message):
        if message.from_user.id not in ADMINS:
            return await message.answer("Доступ заборонено")

        args = message.get_args().split()
        if len(args) != 2:
            return await message.answer("Формат: /change_status ID СПЛАЧЕНО/НЕ")

        user_id, status = args
        if status not in ["СПЛАЧЕНО", "НЕ", "НЕ_СПЛАЧЕНО"]:
            return await message.answer("Статус має бути СПЛАЧЕНО або НЕ_СПЛАЧЕНО")

        if status == "НЕ":
            status = "НЕ СПЛАЧЕНО"

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET payment_status=%s WHERE id=%s", (status, user_id))
        conn.commit()
        conn.close()
        await message.answer("Статус змінено")

# ===== models.sql =====
CREATE DATABASE IF NOT EXISTS telegram_db;
USE telegram_db;

CREATE TABLE IF NOT EXISTS cities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) UNIQUE
);

CREATE TABLE IF NOT EXISTS streets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    city_id INT,
    FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    surname VARCHAR(100),
    name VARCHAR(100),
    patronymic VARCHAR(100),
    contract_number VARCHAR(50),
    units INT,
    volume VARCHAR(50),
    payment_status ENUM('СПЛАЧЕНО', 'НЕ СПЛАЧЕНО'),
    street_id INT,
    FOREIGN KEY (street_id) REFERENCES streets(id) ON DELETE CASCADE
);

# ===== .env (не заливати в GitHub!) =====
BOT_TOKEN=your_telegram_token
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=telegram_db
ADMINS=123456789  # id користувачів, через кому

# ===== README.md =====
# Telegram Бот з MySQL

## Як запускати:

1. Встанови залежності:
```
pip install aiogram mysql-connector-python python-dotenv
```
2. Створи базу даних через MySQL Workbench або:
```
mysql -u root -p < models.sql
```
3. Заповни `.env` своїми даними (включно з ID адміна).
4. Запусти бота:
```
python main.py
```

---

Команди:
- /start — вибір міста → вулиці → мешканців
- /add_city Назва
- /add_street Назва;ID_міста
- /add_user Прізвище;Імʼя;По батькові;№договору;одиниці;обʼєм;id_вулиці
- /change_status ID СПЛАЧЕНО або НЕ_СПЛАЧЕНО

---

Можна додати адмін-меню або перегляд за статусом — пиши, якщо треба ✨
