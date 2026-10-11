"""Загальні обробники: /start, "🚀 РОЗПОЧАТИ", "📝 Головне меню".

Цей роутер підключається в main.py першим, тому ці кнопки працюють
з будь-якого кроку будь-якого майстра (вихід у головне меню завжди
доступний) - так само, як це було в попередній версії бота.
"""
import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import google_services as gs
from config import is_admin
from keyboards import BTN_MAIN_MENU, BTN_START, main_menu_keyboard, start_keyboard

logger = logging.getLogger(__name__)
router = Router(name="common")


async def reset_state(state: FSMContext) -> None:
    """Прибирає будь-який активний майстер і чистить за собою Drive-файли,
    які встигли завантажитись у межах незбереженої сесії."""
    data = await state.get_data()
    uploads = data.get("new_upload_ids") or []
    if uploads:
        await gs.cleanup_uploads(uploads)
    await state.clear()


@router.message(StateFilter("*"), Command("start"))
async def start_handler(message: Message, state: FSMContext) -> None:
    await reset_state(state)
    logger.info("Користувач %s запустив бота (/start)", message.from_user.id)
    await message.answer(
        "👋 Вітаємо у боті «Estate Atlas»!\n"
        "Тут можна додавати об'єкти нерухомості та шукати їх за населеним пунктом.\n\n"
        "Натисніть кнопку нижче, щоб почати:",
        reply_markup=start_keyboard(),
    )


@router.message(StateFilter("*"), F.text == BTN_START)
async def show_menu_from_start(message: Message, state: FSMContext) -> None:
    await reset_state(state)
    await message.answer("Оберіть дію:", reply_markup=main_menu_keyboard(show_add=is_admin(message.from_user.id)))


@router.message(StateFilter("*"), F.text == BTN_MAIN_MENU)
async def show_main_menu(message: Message, state: FSMContext) -> None:
    await reset_state(state)
    await message.answer("Оберіть дію:", reply_markup=main_menu_keyboard(show_add=is_admin(message.from_user.id)))
