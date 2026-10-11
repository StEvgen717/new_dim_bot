"""Централізована конфігурація бота Estate Atlas.

Усі значення читаються зі змінних середовища (файл ``.env`` поруч із цим
модулем). Див. ``.env.example`` та README.md для опису кожної змінної.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _split_ids(raw: str) -> set[int]:
    return {int(piece) for piece in raw.split(",") if piece.strip().isdigit()}


# ===== Telegram =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")

# ===== Google Cloud / Sheets / Drive =====
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID", "")
GOOGLE_SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID", "")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

# OAuth "Desktop app" client secret + кешований токен користувача.
# За замовчуванням обидва файли лежать поруч із цим модулем (у bot/).
GOOGLE_OAUTH_CLIENT_FILE = Path(
    os.getenv("GOOGLE_OAUTH_CLIENT_FILE", str(BASE_DIR / "google-oauth-client.json"))
)
GOOGLE_OAUTH_TOKEN_FILE = Path(
    os.getenv("GOOGLE_OAUTH_TOKEN_FILE", str(BASE_DIR / "token.json"))
)

# Як проходити перший (одноразовий) вхід Google-акаунтом:
# - "local_server" (за замовчуванням) - сам відкриває браузер на цій же машині;
# - "console" - для headless-серверів без браузера: друкує посилання в
#   консоль, яке можна відкрити на БУДЬ-ЯКОМУ іншому пристрої, і просить
#   вставити код авторизації назад у термінал.
GOOGLE_OAUTH_FLOW = os.getenv("GOOGLE_OAUTH_FLOW", "local_server").strip().lower()

# ===== Контроль доступу =====
# Telegram ID користувачів, яким дозволено "Додати об'єкт" та "Редагувати".
# Якщо список порожній — доступ відкритий для всіх (режим "open").
ADMINS = _split_ids(os.getenv("ADMINS", ""))


def is_admin(user_id: int) -> bool:
    """Чи дозволено користувачу "➕ Додати об'єкт" / "✏️ Редагувати".

    Якщо ADMINS не задано в .env - дозволено всім (відкритий режим).
    """
    return not ADMINS or user_id in ADMINS


# ===== Пошук =====
# Скільки об'єктів показувати за один раз (кнопка "Показати ще" довантажує решту).
SEARCH_PAGE_SIZE = int(os.getenv("SEARCH_PAGE_SIZE", "5"))

# Аркуші, які є в таблиці, але НЕ є населеними пунктами (технічні/довідкові
# аркуші - не показувати їх у списку вибору населеного пункту).
EXCLUDED_SHEETS = {
    s.strip() for s in os.getenv("EXCLUDED_SHEETS", "Довідники,Каталог,1").split(",") if s.strip()
}

# ===== Довідники для майстра "Додати об'єкт" =====
DEAL_TYPES = ["Продаж", "Оренда"]
PROPERTY_TYPES = ["Будинок", "Квартира", "Ділянка", "Комерція"]
CURRENCIES = ["USD", "грн"]

# ===== Структура аркуша-населеного пункту в Google Таблиці =====
# Назви та порядок колонок зі специфікації (Google API.txt).
SHEET_HEADERS = [
    "Тип угоди",
    "Тип об'єкта",
    "Адреса / локація",
    "Ціна",
    "Валюта",
    "Площа, м²",
    "Площа ділянки, сот.",
    "Фото",
    "Відео",
    "Посилання",
    "Опис",
    "Коментар",
    "Статус",
]

# Статус, що встановлюється автоматично для щойно доданого об'єкта.
DEFAULT_STATUS = "Активний"
