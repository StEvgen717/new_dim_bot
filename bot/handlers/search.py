"""Функція "🔎 Пошук": вибір населеного пункту -> список об'єктів.

Для кожного об'єкта (рядок аркуша з непорожньою колонкою "Тип угоди")
спочатку надсилається "колаж" фото - справжні зображення в Telegram (одне
фото або альбом, якщо декілька - стандартна поведінка Telegram). Формат
збереженого значення (Telegram file_id чи лінк на Google Drive) визначається
автоматично за виглядом рядка, незалежно від поточного ``MEDIA_STORAGE`` -
file_id передається напряму (без завантаження), Drive-лінк довантажується
байтами. Відео з Telegram file_id надсилаються так само напряму
(``answer_video``, нуль пам'яті бота); відео, збережені як лінк на Google
Drive, лишаються inline-кнопкою-посиланням - завантажувати важкі відеофайли
на бота немає сенсу.

Після фото йде текстова картка з основними даними + inline-кнопки:
fallback-посилання на фото/відео, які не вдалося показати напряму (лише
для справжніх Drive-лінків) та кнопка "✏️ Редагувати", яка веде у
майстер додавання об'єкта з кроку "Ціна".

Якщо об'єктів багато, вони показуються партіями по SEARCH_PAGE_SIZE
(кнопка "➡️ Показати ще" довантажує наступну партію) - це захищає від
переповнення чату й лімітів Telegram на кількість повідомлень поспіль.
"""
import logging
from typing import Optional

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InputMediaPhoto, Message

import edit_tokens
import google_services as gs
from config import SEARCH_PAGE_SIZE, is_admin
from keyboards import (
    BTN_BACK,
    BTN_SEARCH,
    main_menu_keyboard,
    object_card_keyboard,
    settlements_keyboard,
    show_more_keyboard,
)
from states import SearchStates

logger = logging.getLogger(__name__)
router = Router(name="search")

MAX_MEDIA_GROUP = 10  # лімiт Telegram на кількість фото в одному альбомі


@router.message(StateFilter(None), F.text == BTN_SEARCH)
async def start_search(message: Message, state: FSMContext) -> None:
    settlements = await gs.list_settlements()
    if not settlements:
        await message.answer(
            "У таблиці ще немає жодного населеного пункту.",
            reply_markup=main_menu_keyboard(show_add=is_admin(message.from_user.id)),
        )
        return
    await state.set_state(SearchStates.choosing_settlement)
    await message.answer("Оберіть населений пункт для пошуку:", reply_markup=settlements_keyboard(settlements))


@router.message(SearchStates.choosing_settlement, F.text == BTN_BACK)
async def search_back(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Оберіть дію:", reply_markup=main_menu_keyboard(show_add=is_admin(message.from_user.id)))


@router.message(SearchStates.choosing_settlement)
async def choose_settlement(message: Message, state: FSMContext) -> None:
    settlement = (message.text or "").strip()
    settlements = await gs.list_settlements()
    if settlement not in settlements:
        await message.answer(
            "Будь ласка, оберіть населений пункт із кнопок нижче.",
            reply_markup=settlements_keyboard(settlements),
        )
        return

    try:
        objects = await gs.list_objects(settlement)
    except Exception:
        logger.exception("Не вдалося отримати список об'єктів (settlement=%s)", settlement)
        await message.answer(
            "⚠️ Сталася помилка під час читання даних із таблиці.",
            reply_markup=main_menu_keyboard(show_add=is_admin(message.from_user.id)),
        )
        await state.clear()
        return

    if not objects:
        await message.answer(
            f"У «{settlement}» ще немає жодного активного об'єкта.",
            reply_markup=settlements_keyboard(settlements),
        )
        return

    await state.update_data(search_settlement=settlement, search_offset=0)
    await message.answer(f"Знайдено об'єктів у «{settlement}»: {len(objects)}.")
    await _send_batch(message, state, settlement, objects, offset=0)


async def _send_batch(message: Message, state: FSMContext, settlement: str, objects: list, offset: int) -> None:
    batch = objects[offset:offset + SEARCH_PAGE_SIZE]
    for row_idx, row in batch:
        await _send_object_card(message, settlement, row_idx, row)

    new_offset = offset + len(batch)
    remaining = len(objects) - new_offset
    await state.update_data(search_offset=new_offset)
    if remaining > 0:
        await message.answer(
            f"Показано {new_offset} з {len(objects)}.",
            reply_markup=show_more_keyboard(remaining),
        )


async def _fetch_photo_input(link: str) -> Optional[BufferedInputFile | str]:
    """Повертає готовий для ``answer_photo``/``InputMediaPhoto`` об'єкт:
    рядок (Telegram file_id - без жодного мережевого звернення, Telegram
    сам роздає байти) або завантажені байти з Google Drive. Формат
    визначається автоматично за виглядом збереженого значення, а не за
    поточним ``MEDIA_STORAGE`` - перемикання налаштування в будь-який
    момент не ламає раніше збережені об'єкти в іншому форматі."""
    file_id = gs.extract_drive_file_id(link)
    if file_id is None:
        return link  # вже готовий Telegram file_id
    try:
        content = await gs.download_from_drive(file_id)
    except Exception:
        logger.exception("Не вдалося завантажити фото з Google Drive (file_id=%s)", file_id)
        return None
    return BufferedInputFile(content, filename=f"{file_id}.jpg")


async def _send_photos(message: Message, photos: list[str]) -> list[str]:
    """Надсилає фото як справжні зображення (одне фото або альбом-"колаж",
    якщо декілька - стандартна поведінка Telegram). Байти з Drive
    завантажуються послідовно (не паралельно - клієнт Google API не
    гарантує безпеку одночасних звернень з кількох потоків, саме це
    спричиняло таймаути при завантаженні декількох файлів одночасно);
    Telegram file_id передаються одразу, без завантаження.

    Повертає список посилань, які НЕ вдалося показати як зображення -
    щоб хоча б дати на них кнопку-посилання (лише для справжніх Drive-
    посилань - Telegram file_id кнопкою-URL показати неможливо, такі при
    збої просто пропускаються з логуванням, без фолбек-кнопки)."""
    if not photos:
        return []

    inputs: list[BufferedInputFile | str] = []
    failed: list[str] = []
    for link in photos:
        file_input = await _fetch_photo_input(link)
        if file_input is None:
            failed.append(link)
        else:
            inputs.append(file_input)

    if not inputs:
        return failed

    try:
        if len(inputs) == 1:
            await message.answer_photo(inputs[0])
        else:
            for start in range(0, len(inputs), MAX_MEDIA_GROUP):
                chunk = inputs[start:start + MAX_MEDIA_GROUP]
                await message.answer_media_group([InputMediaPhoto(media=item) for item in chunk])
    except Exception:
        logger.exception("Не вдалося надіслати фото-колаж (%s фото)", len(inputs))
        # Кнопкою-URL можна показати лише справжні Drive-посилання -
        # Telegram file_id так не покажеш, тож такі просто пропускаємо.
        return failed + [link for link in photos if gs.extract_drive_file_id(link) is not None]

    return failed


async def _send_videos(message: Message, videos: list[str]) -> list[str]:
    """Відео, збережені як Telegram file_id, надсилаються напряму
    (``answer_video``) - без завантаження, Telegram сам роздає байти, тож
    пам'ять бота це не навантажує (на відміну від фото з Google Drive, тут
    нема що завантажувати). Відео, збережені як лінк на Google Drive (інший
    ``MEDIA_STORAGE`` або старі записи), лишаються кнопкою-посиланням, як і
    раніше - завантажувати важкі відеофайли на бота немає сенсу.

    Повертає список лінків для фолбек-кнопок (лише справжні Drive-лінки)."""
    fallback: list[str] = []
    for link in videos:
        if gs.extract_drive_file_id(link) is not None:
            fallback.append(link)  # Drive-лінк - як і раніше, лише кнопка
            continue
        try:
            await message.answer_video(link)  # це Telegram file_id
        except Exception:
            logger.exception("Не вдалося надіслати відео напряму (можливо, застарілий file_id)")
    return fallback


async def _send_object_card(message: Message, settlement: str, row_idx: int, row: dict) -> None:
    photos = gs.split_links(row.get("Фото", ""))
    videos = gs.split_links(row.get("Відео", ""))

    fallback_photos = await _send_photos(message, photos)
    fallback_videos = await _send_videos(message, videos)

    text = _format_card(settlement, row)
    token = edit_tokens.register(settlement, row_idx)
    keyboard = object_card_keyboard(fallback_photos, fallback_videos, token)
    await message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)


def _format_card(settlement: str, row: dict) -> str:
    deal = row.get("Тип угоди") or "—"
    kind = row.get("Тип об'єкта") or "—"
    price = row.get("Ціна") or ""
    currency = row.get("Валюта") or ""
    area_m2 = row.get("Площа, м²") or ""
    area_sot = row.get("Площа ділянки, сот.") or ""
    address = row.get("Адреса / локація") or ""
    link = row.get("Посилання") or ""
    tiktok = row.get("Відео TikTok") or ""
    description = row.get("Опис") or ""

    lines = [f"🏷 {deal} • {kind} • {settlement}"]
    if price:
        lines.append(f"💰 Ціна: {price} {currency}".strip())
    if area_m2:
        lines.append(f"📐 Площа, м²: {area_m2}")
    if area_sot:
        lines.append(f"📐 Площа ділянки: {area_sot} сот.")
    if address:
        lines.append(f"📍 Адреса/локація: {address}")
    if description:
        lines.append(f"📝 {description}")
    if link:
        lines.append(f"🔗 Оголошення: {link}")
    if tiktok:
        lines.append(f"🎵 Відео TikTok: {tiktok}")
    if not (row.get("Фото") or row.get("Відео")):
        lines.append("Фото/відео відсутні.")
    return "\n".join(lines)


@router.callback_query(F.data == "search_more")
async def search_more(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    settlement = data.get("search_settlement")
    offset = data.get("search_offset", 0)
    if not settlement:
        await callback.message.answer("Пошук застарів, спробуйте, будь ласка, ще раз.")
        return

    try:
        objects = await gs.list_objects(settlement)
    except Exception:
        logger.exception("Не вдалося отримати список об'єктів (settlement=%s)", settlement)
        await callback.message.answer("⚠️ Сталася помилка під час читання даних із таблиці.")
        return

    await _send_batch(callback.message, state, settlement, objects, offset=offset)
