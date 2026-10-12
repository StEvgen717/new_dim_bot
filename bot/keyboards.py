"""Клавіатури бота.

Дизайн свідомо успадкований від попередньої версії бота: звичайні
ReplyKeyboardMarkup-кнопки з emoji (🔙 Назад, 📝 Головне меню,
🚀 РОЗПОЧАТИ) для навігації, а вибір варіанту = натискання відповідної
кнопки. Inline-кнопки використовуються лише там, де це дає явну користь:
посилання на фото/відео в Google Drive та кнопка "✏️ Редагувати" під
конкретною карткою об'єкта в результатах пошуку.
"""
from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

BTN_START = "🚀 РОЗПОЧАТИ"
BTN_MAIN_MENU = "📝 Головне меню"
BTN_BACK = "🔙 Назад"
BTN_NEXT = "➡️ Далі"
BTN_SAVE = "✅ Зберегти"
BTN_ADD_OBJECT = "➕ Додати об'єкт"
BTN_SEARCH = "🔎 Пошук"
BTN_EDIT = "✏️ Редагувати"
BTN_SHOW_MORE = "➡️ Показати ще"


def start_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_START)]],
        resize_keyboard=True,
    )


def main_menu_keyboard(show_add: bool = True) -> ReplyKeyboardMarkup:
    keyboard = []
    if show_add:
        keyboard.append([KeyboardButton(text=BTN_ADD_OBJECT)])
    keyboard.append([KeyboardButton(text=BTN_SEARCH)])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def _nav_row(back: bool, main_menu: bool) -> list[KeyboardButton]:
    row = []
    if back:
        row.append(KeyboardButton(text=BTN_BACK))
    if main_menu:
        row.append(KeyboardButton(text=BTN_MAIN_MENU))
    return row


def options_keyboard(
    options: list[str],
    back: bool = True,
    main_menu: bool = True,
) -> ReplyKeyboardMarkup:
    """Клавіатура для обов'язкових кроків з вибором (населений пункт,
    тип угоди, тип об'єкта): натискання варіанту = вибір і перехід далі."""
    keyboard = [[KeyboardButton(text=opt)] for opt in options]
    nav = _nav_row(back, main_menu)
    if nav:
        keyboard.append(nav)
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def skip_keyboard(
    options: list[str] | None = None,
    back: bool = True,
    main_menu: bool = True,
) -> ReplyKeyboardMarkup:
    """Клавіатура для необов'язкових кроків: (опційні варіанти) + Далі +
    навігація. Кнопка "➡️ Далі" завжди доступна, навіть без введення."""
    keyboard = []
    if options:
        keyboard.append([KeyboardButton(text=opt) for opt in options])
    keyboard.append([KeyboardButton(text=BTN_NEXT)])
    nav = _nav_row(back, main_menu)
    if nav:
        keyboard.append(nav)
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def finish_keyboard(back: bool = True, main_menu: bool = True) -> ReplyKeyboardMarkup:
    """Клавіатура останнього кроку майстра ("Посилання"): замість "Далі" -
    "✅ Зберегти", що завершує додавання/редагування об'єкта."""
    keyboard = [[KeyboardButton(text=BTN_SAVE)]]
    nav = _nav_row(back, main_menu)
    if nav:
        keyboard.append(nav)
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def settlements_keyboard(
    settlements: list[str],
    back: bool = False,
    main_menu: bool = True,
) -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text=s)] for s in settlements]
    nav = _nav_row(back, main_menu)
    if nav:
        keyboard.append(nav)
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def object_card_keyboard(
    fallback_photos: list[str],
    fallback_videos: list[str],
    edit_token: str,
    show_edit: bool = True,
) -> InlineKeyboardMarkup | None:
    """Inline-кнопки під карткою: лише фолбек-посилання на фото/відео, які
    НЕ вдалося (чи не було сенсу) показати напряму вище - тобто довантажені
    з Google Drive (решта, показана прямо як колаж/відео, кнопки не
    потребує) - + кнопка редагування."""
    buttons = [InlineKeyboardButton(text=f"🖼 Фото (посилання) {i + 1}", url=link) for i, link in enumerate(fallback_photos)]
    buttons += [InlineKeyboardButton(text=f"🎬 Відео {i + 1}", url=link) for i, link in enumerate(fallback_videos)]

    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    if show_edit:
        rows.append([InlineKeyboardButton(text=BTN_EDIT, callback_data=f"edit:{edit_token}")])

    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def show_more_keyboard(remaining: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=f"{BTN_SHOW_MORE} ({remaining})", callback_data="search_more"),
        ]]
    )
