"""Майстер "➕ Додати об'єкт" (13 кроків) та редагування існуючого об'єкта.

Кожен крок - окремий FSM-стан. Кнопка "🔙 Назад" повертає на попередній
крок, "📝 Головне меню" (обробляється глобально в handlers/common.py)
скасовує майстер з будь-якого кроку. Для обов'язкових кроків (населений
пункт/тип угоди/тип об'єкта) натискання варіанту = одразу перехід далі;
для необов'язкових є кнопка "➡️ Далі", яка працює навіть без введення.

Редагування ("✏️ Редагувати" у картці пошуку) переходить одразу на крок
4 ("Ціна") з уже заповненими поточними значеннями - рівно так, як
описано у специфікації. Якщо на кроці користувач просто натискає
"➡️ Далі" без нового введення, поточне значення зберігається незмінним
(це працює "само собою", бо FSM-дані вже містять старе значення).
"""
import asyncio
import logging
from collections import defaultdict
from typing import Optional

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import edit_tokens
import google_services as gs
from config import CURRENCIES, DEAL_TYPES, DEFAULT_STATUS, MEDIA_STORAGE, PROPERTY_TYPES, is_admin
from keyboards import (
    BTN_ADD_OBJECT,
    BTN_BACK,
    BTN_NEXT,
    BTN_SAVE,
    finish_keyboard,
    main_menu_keyboard,
    options_keyboard,
    skip_keyboard,
)
from states import AddObjectStates

logger = logging.getLogger(__name__)
router = Router(name="add_object")

STEP_ORDER = [
    "settlement", "deal_type", "property_type", "price", "currency",
    "area_sqm", "area_sot", "description", "photos", "videos", "address", "link", "tiktok",
]
STEP_NUMBER = {step: i + 1 for i, step in enumerate(STEP_ORDER)}
STATE_BY_STEP = {step: getattr(AddObjectStates, step) for step in STEP_ORDER}
STEP_BY_RAW_STATE = {state.state: step for step, state in STATE_BY_STEP.items()}
PREV_STEP = {step: STEP_ORDER[i - 1] for i, step in enumerate(STEP_ORDER) if i > 0}


def _parse_number(text: str) -> Optional[str]:
    normalized = text.strip().replace(" ", "").replace(",", ".")
    if not normalized:
        return None
    try:
        float(normalized)
    except ValueError:
        return None
    return normalized


# ---------------------------------------------------------------------------
# Відображення кроків
# ---------------------------------------------------------------------------

async def _render(step: str, data: dict, error: Optional[str] = None):
    is_edit = data.get("mode") == "edit"
    prefix = f"⚠️ {error}\n\n" if error else ""
    n = STEP_NUMBER[step]

    def current(field: str, label: str = "Поточне значення") -> str:
        value = data.get(field)
        return f"\n{label}: {value}" if is_edit and value else ""

    if step == "settlement":
        settlements = await gs.list_settlements()
        text = f"{prefix}Крок {n}/13. Оберіть населений пункт:"
        return text, options_keyboard(settlements, back=False, main_menu=True)

    if step == "deal_type":
        text = f"{prefix}Крок {n}/13. Оберіть тип угоди:"
        return text, options_keyboard(DEAL_TYPES)

    if step == "property_type":
        text = f"{prefix}Крок {n}/13. Оберіть тип об'єкта:"
        return text, options_keyboard(PROPERTY_TYPES)

    if step == "price":
        text = (
            f"{prefix}Крок {n}/13. Введіть ціну (наприклад: 115000) "
            f"або натисніть «➡️ Далі», щоб залишити порожнім.{current('price', 'Поточна ціна')}"
        )
        return text, skip_keyboard()

    if step == "currency":
        text = f"{prefix}Крок {n}/13. Оберіть валюту:{current('currency', 'Поточна валюта')}"
        return text, skip_keyboard(CURRENCIES)

    if step == "area_sqm":
        text = (
            f"{prefix}Крок {n}/13. Введіть «Площа, м²» "
            f"або натисніть «➡️ Далі», щоб залишити порожнім.{current('area_sqm', 'Поточна площа, м²')}"
        )
        return text, skip_keyboard()

    if step == "area_sot":
        text = (
            f"{prefix}Крок {n}/13. Введіть «Площа ділянки, сот.» "
            f"або натисніть «➡️ Далі», щоб залишити порожнім.{current('area_sot', 'Поточна площа ділянки')}"
        )
        return text, skip_keyboard()

    if step == "description":
        text = (
            f"{prefix}Крок {n}/13. Введіть опис об'єкта "
            f"або натисніть «➡️ Далі».{current('description', 'Поточний опис')}"
        )
        return text, skip_keyboard()

    if step == "photos":
        count = len(data.get("photos") or [])
        text = (
            f"{prefix}Крок {n}/13. Надішліть фото об'єкта (можна декілька, одне за одним). "
            f"Додано: {count}.\nКоли завершите - натисніть «➡️ Далі»."
        )
        return text, skip_keyboard()

    if step == "videos":
        count = len(data.get("videos") or [])
        text = (
            f"{prefix}Крок {n}/13. Надішліть відео об'єкта (можна декілька). "
            f"Додано: {count}.\nКоли завершите - натисніть «➡️ Далі»."
        )
        return text, skip_keyboard()

    if step == "address":
        text = (
            f"{prefix}Крок {n}/13. Надішліть адресу/локацію текстом, геолокацією "
            f"або посиланням Google Maps, або натисніть «➡️ Далі».{current('address')}"
        )
        return text, skip_keyboard()

    if step == "link":
        text = (
            f"{prefix}Крок {n}/13. Надішліть посилання на оголошення "
            f"або натисніть «➡️ Далі».{current('link')}"
        )
        return text, skip_keyboard()

    if step == "tiktok":
        text = (
            f"{prefix}Крок {n}/13. Надішліть посилання на відео TikTok "
            f"або натисніть «✅ Зберегти».{current('tiktok', 'Поточне відео TikTok')}"
        )
        return text, finish_keyboard()

    raise ValueError(f"Невідомий крок майстра: {step}")


async def show_step(message: Message, state: FSMContext, step: str, error: Optional[str] = None) -> None:
    await state.set_state(STATE_BY_STEP[step])
    data = await state.get_data()
    text, keyboard = await _render(step, data, error=error)
    await message.answer(text, reply_markup=keyboard)


async def cancel_wizard(message: Message, state: FSMContext, note: str) -> None:
    data = await state.get_data()
    await gs.cleanup_uploads(data.get("new_upload_ids") or [])
    await state.clear()
    await message.answer(note, reply_markup=main_menu_keyboard(show_add=is_admin(message.from_user.id)))


# ---------------------------------------------------------------------------
# Вхід у майстер / загальна навігація
# ---------------------------------------------------------------------------

@router.message(StateFilter(None), F.text == BTN_ADD_OBJECT)
async def start_add_object(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        logger.info("Користувач %s без прав спробував додати об'єкт", message.from_user.id)
        await message.answer(
            "⛔ У вас немає прав для додавання об'єктів.",
            reply_markup=main_menu_keyboard(show_add=False),
        )
        return

    await state.clear()
    await state.update_data(mode="add", new_upload_ids=[])
    await show_step(message, state, "settlement")


@router.message(StateFilter(AddObjectStates), F.text == BTN_BACK)
async def go_back(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    raw_state = await state.get_state()
    step = STEP_BY_RAW_STATE.get(raw_state)

    # Під час редагування кроки 1-3 (населений пункт/тип угоди/тип об'єкта)
    # зафіксовані й недоступні - "Назад" із першого редагованого кроку
    # ("Ціна") означає вихід із редагування, а не повернення туди.
    if data.get("mode") == "edit" and step == "price":
        await cancel_wizard(message, state, "➡️ Редагування скасовано.")
        return

    prev = PREV_STEP.get(step) if step else None
    if prev is None:
        await cancel_wizard(message, state, "➡️ Додавання об'єкта скасовано.")
        return
    await show_step(message, state, prev)


# ---------------------------------------------------------------------------
# Крок 1-3: обов'язкові варіанти вибору
# ---------------------------------------------------------------------------

@router.message(AddObjectStates.settlement)
async def step_settlement(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    settlements = await gs.list_settlements()
    if text not in settlements:
        await show_step(message, state, "settlement", error="Будь ласка, оберіть населений пункт із кнопок нижче.")
        return
    await state.update_data(settlement=text)
    await show_step(message, state, "deal_type")


@router.message(AddObjectStates.deal_type)
async def step_deal_type(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text not in DEAL_TYPES:
        await show_step(message, state, "deal_type", error="Будь ласка, оберіть тип угоди із кнопок нижче.")
        return
    await state.update_data(deal_type=text)
    await show_step(message, state, "property_type")


@router.message(AddObjectStates.property_type)
async def step_property_type(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text not in PROPERTY_TYPES:
        await show_step(message, state, "property_type", error="Будь ласка, оберіть тип об'єкта із кнопок нижче.")
        return
    await state.update_data(property_type=text)
    await show_step(message, state, "price")


# ---------------------------------------------------------------------------
# Крок 4-5: ціна, валюта
# ---------------------------------------------------------------------------

@router.message(AddObjectStates.price, F.text == BTN_NEXT)
async def step_price_skip(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "currency")


@router.message(AddObjectStates.price, F.text)
async def step_price_value(message: Message, state: FSMContext) -> None:
    value = _parse_number(message.text)
    if value is None:
        await show_step(message, state, "price", error="Ціна має бути числом, напр. 115000.")
        return
    await state.update_data(price=value)
    await show_step(message, state, "currency")


@router.message(AddObjectStates.price)
async def step_price_invalid(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "price", error="Введіть число або натисніть «➡️ Далі».")


@router.message(AddObjectStates.currency, F.text == BTN_NEXT)
async def step_currency_skip(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "area_sqm")


@router.message(AddObjectStates.currency, F.text.in_(CURRENCIES))
async def step_currency_value(message: Message, state: FSMContext) -> None:
    await state.update_data(currency=message.text.strip())
    await show_step(message, state, "area_sqm")


@router.message(AddObjectStates.currency)
async def step_currency_invalid(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "currency", error="Оберіть USD або грн, або натисніть «➡️ Далі».")


# ---------------------------------------------------------------------------
# Крок 6: площа, м²
# ---------------------------------------------------------------------------

@router.message(AddObjectStates.area_sqm, F.text == BTN_NEXT)
async def step_area_sqm_skip(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "area_sot")


@router.message(AddObjectStates.area_sqm, F.text)
async def step_area_sqm_value(message: Message, state: FSMContext) -> None:
    value = _parse_number(message.text)
    if value is None:
        await show_step(message, state, "area_sqm", error="Введіть число, напр. 115.")
        return
    await state.update_data(area_sqm=value)
    await show_step(message, state, "area_sot")


@router.message(AddObjectStates.area_sqm)
async def step_area_sqm_invalid(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "area_sqm", error="Введіть число або натисніть «➡️ Далі».")


# ---------------------------------------------------------------------------
# Крок 7: площа ділянки, сот.
# ---------------------------------------------------------------------------

@router.message(AddObjectStates.area_sot, F.text == BTN_NEXT)
async def step_area_sot_skip(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "description")


@router.message(AddObjectStates.area_sot, F.text)
async def step_area_sot_value(message: Message, state: FSMContext) -> None:
    value = _parse_number(message.text)
    if value is None:
        await show_step(message, state, "area_sot", error="Введіть число, напр. 6.")
        return
    await state.update_data(area_sot=value)
    await show_step(message, state, "description")


@router.message(AddObjectStates.area_sot)
async def step_area_sot_invalid(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "area_sot", error="Введіть число або натисніть «➡️ Далі».")


# ---------------------------------------------------------------------------
# Крок 8: опис
# ---------------------------------------------------------------------------

@router.message(AddObjectStates.description, F.text == BTN_NEXT)
async def step_description_skip(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "photos")


@router.message(AddObjectStates.description, F.text)
async def step_description_value(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await show_step(message, state, "photos")


@router.message(AddObjectStates.description)
async def step_description_invalid(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "description", error="Введіть текст або натисніть «➡️ Далі».")


# ---------------------------------------------------------------------------
# Крок 9-10: фото, відео
# ---------------------------------------------------------------------------

# Якщо надіслати декілька фото/відео "стеком" (альбомом), Telegram доставляє
# їх боту окремими повідомленнями майже одночасно. Без серіалізації по
# користувачу паралельні виклики читають однакове "старе" значення
# data.get(field) ще до свого довгого завантаження, і той, хто записує
# останнім, затирає результат іншого (файл лишається сиротою в Drive, але
# губиться з таблиці) - а паралельні завантаження в Drive також конкурують
# за мережу, що й спричиняло TimeoutError при пачці файлів.
_upload_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


async def _handle_media_upload(message: Message, state: FSMContext, field: str, tg_file, mime_type: str, ext: str) -> None:
    async with _upload_locks[message.from_user.id]:
        data = await state.get_data()
        label = "Фото" if field == "photos" else "Відео"

        if MEDIA_STORAGE == "googledrive":
            settlement = data.get("settlement", "object")
            deal_type = data.get("deal_type", "")
            index = len(data.get(field) or []) + 1
            filename = f"{settlement}_{deal_type}_{field}_{index}_{tg_file.file_unique_id}.{ext}".replace(" ", "_")

            status_msg = await message.answer("⏳ Завантажую у Google Drive...")
            try:
                buffer = await message.bot.download(tg_file)
                drive_id, value = await gs.upload_to_drive(buffer.read(), filename, mime_type)
            except Exception:
                logger.exception("Не вдалося завантажити %s у Google Drive (user_id=%s)", field, message.from_user.id)
                await status_msg.edit_text("⚠️ Не вдалося завантажити файл у Google Drive. Спробуйте ще раз.")
                return

            uploads = list(data.get("new_upload_ids") or [])
            uploads.append(drive_id)
            await state.update_data(new_upload_ids=uploads)

            items = list(data.get(field) or [])
            items.append(value)
            await state.update_data(**{field: items})
            await status_msg.edit_text(f"✅ {label} додано ({len(items)}). Надішліть ще або натисніть «➡️ Далі».")
            return

        # MEDIA_STORAGE="telegram" (за замовчуванням) - file_id вже готовий
        # у самому повідомленні, жодного завантаження/мережевого звернення
        # не потрібно - і, відповідно, нема що класти в new_upload_ids
        # (нічого видаляти з Google Drive при скасуванні майстра не буде).
        items = list(data.get(field) or [])
        items.append(tg_file.file_id)
        await state.update_data(**{field: items})
        await message.answer(f"✅ {label} додано ({len(items)}). Надішліть ще або натисніть «➡️ Далі».")


@router.message(AddObjectStates.photos, F.photo)
async def step_photos_add(message: Message, state: FSMContext) -> None:
    await _handle_media_upload(message, state, "photos", message.photo[-1], "image/jpeg", "jpg")


@router.message(AddObjectStates.photos, F.text == BTN_NEXT)
async def step_photos_skip(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "videos")


@router.message(AddObjectStates.photos)
async def step_photos_invalid(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "photos", error="Надішліть фото або натисніть «➡️ Далі».")


@router.message(AddObjectStates.videos, F.video)
async def step_videos_add(message: Message, state: FSMContext) -> None:
    mime_type = message.video.mime_type or "video/mp4"
    await _handle_media_upload(message, state, "videos", message.video, mime_type, "mp4")


@router.message(AddObjectStates.videos, F.text == BTN_NEXT)
async def step_videos_skip(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "address")


@router.message(AddObjectStates.videos)
async def step_videos_invalid(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "videos", error="Надішліть відео або натисніть «➡️ Далі».")


# ---------------------------------------------------------------------------
# Крок 11-13: адреса/локація, посилання, відео TikTok (= завершення)
# ---------------------------------------------------------------------------

@router.message(AddObjectStates.address, F.text == BTN_NEXT)
async def step_address_skip(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "link")


@router.message(AddObjectStates.address, F.location)
async def step_address_location(message: Message, state: FSMContext) -> None:
    loc = message.location
    link = f"https://www.google.com/maps?q={loc.latitude},{loc.longitude}"
    await state.update_data(address=link)
    await show_step(message, state, "link")


@router.message(AddObjectStates.address, F.text)
async def step_address_text(message: Message, state: FSMContext) -> None:
    await state.update_data(address=message.text.strip())
    await show_step(message, state, "link")


@router.message(AddObjectStates.address)
async def step_address_invalid(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "address", error="Надішліть текст, геолокацію або натисніть «➡️ Далі».")


@router.message(AddObjectStates.link, F.text == BTN_NEXT)
async def step_link_skip(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "tiktok")


@router.message(AddObjectStates.link, F.text)
async def step_link_value(message: Message, state: FSMContext) -> None:
    await state.update_data(link=message.text.strip())
    await show_step(message, state, "tiktok")


@router.message(AddObjectStates.link)
async def step_link_invalid(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "link", error="Надішліть посилання текстом або натисніть «➡️ Далі».")


@router.message(AddObjectStates.tiktok, F.text == BTN_SAVE)
async def step_tiktok_save(message: Message, state: FSMContext) -> None:
    await _finalize(message, state)


@router.message(AddObjectStates.tiktok, F.text)
async def step_tiktok_value(message: Message, state: FSMContext) -> None:
    await state.update_data(tiktok=message.text.strip())
    await _finalize(message, state)


@router.message(AddObjectStates.tiktok)
async def step_tiktok_invalid(message: Message, state: FSMContext) -> None:
    await show_step(message, state, "tiktok", error="Надішліть посилання текстом або натисніть «✅ Зберегти».")


# ---------------------------------------------------------------------------
# Збереження
# ---------------------------------------------------------------------------

def _build_summary(settlement: str, field_values: dict, title: str) -> str:
    area_sqm = field_values.get("Площа, м²")
    area_sot = field_values.get("Площа ділянки, сот.")

    property_type_value = field_values.get("Тип об'єкта", "—")
    lines = [
        title,
        f"📍 Населений пункт: {settlement}",
        f"🏷 {field_values.get('Тип угоди', '—')} • {property_type_value}",
    ]
    price = field_values.get("Ціна")
    if price:
        lines.append(f"💰 Ціна: {price} {field_values.get('Валюта', '')}".strip())
    if area_sqm:
        lines.append(f"📐 Площа, м²: {area_sqm}")
    if area_sot:
        lines.append(f"📐 Площа ділянки: {area_sot} сот.")
    if field_values.get("Адреса / локація"):
        lines.append(f"📍 Адреса/локація: {field_values['Адреса / локація']}")
    if field_values.get("Посилання"):
        lines.append(f"🔗 Посилання: {field_values['Посилання']}")
    if field_values.get("Відео TikTok"):
        lines.append(f"🎵 Відео TikTok: {field_values['Відео TikTok']}")

    photos_n = len(gs.split_links(field_values.get("Фото", "")))
    videos_n = len(gs.split_links(field_values.get("Відео", "")))
    lines.append(f"🖼 Фото: {photos_n} | 🎬 Відео: {videos_n}")
    return "\n".join(lines)


async def _finalize(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    settlement = data["settlement"]
    property_type = data.get("property_type", "")

    field_values = {
        "Тип угоди": data.get("deal_type", "") or "",
        "Тип об'єкта": property_type,
        "Адреса / локація": data.get("address") or "",
        "Ціна": data.get("price") or "",
        "Валюта": data.get("currency") or "",
        "Площа, м²": data.get("area_sqm") or "",
        "Площа ділянки, сот.": data.get("area_sot") or "",
        "Фото": "\n".join(data.get("photos") or []),
        "Відео": "\n".join(data.get("videos") or []),
        "Посилання": data.get("link") or "",
        "Відео TikTok": data.get("tiktok") or "",
        "Опис": data.get("description") or "",
    }

    is_edit = data.get("mode") == "edit"
    try:
        if is_edit:
            row_idx = data["row_idx"]
            await gs.update_object(settlement, row_idx, field_values)
            summary = _build_summary(settlement, field_values, "✅ Об'єкт оновлено!")
            logger.info("Користувач %s оновив об'єкт %s (рядок %s)", message.from_user.id, settlement, row_idx)
        else:
            field_values["Статус"] = DEFAULT_STATUS
            row_idx = await gs.append_object(settlement, field_values)
            summary = _build_summary(settlement, field_values, "✅ Об'єкт додано!")
            logger.info("Користувач %s додав об'єкт %s (рядок %s)", message.from_user.id, settlement, row_idx)
    except Exception:
        logger.exception("Не вдалося зберегти об'єкт у Google Sheets (user_id=%s)", message.from_user.id)
        await message.answer(
            "⚠️ Сталася помилка під час збереження у Google Таблицю. "
            "Дані не було збережено, спробуйте, будь ласка, ще раз.",
            reply_markup=main_menu_keyboard(show_add=is_admin(message.from_user.id)),
        )
        await state.clear()
        return

    await state.clear()
    await message.answer(summary, reply_markup=main_menu_keyboard(show_add=is_admin(message.from_user.id)))


# ---------------------------------------------------------------------------
# Редагування існуючого об'єкта (кнопка "✏️ Редагувати" з картки пошуку)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("edit:"))
async def start_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()

    if not is_admin(callback.from_user.id):
        await callback.message.answer("⛔ У вас немає прав для редагування об'єктів.")
        return

    token = callback.data.split(":", 1)[1]
    target = edit_tokens.resolve(token)
    if not target:
        await callback.message.answer("⚠️ Це посилання для редагування вже застаріло. Повторіть пошук, будь ласка.")
        return
    settlement, row_idx = target

    try:
        row = await gs.get_object(settlement, row_idx)
    except Exception:
        logger.exception("Не вдалося прочитати об'єкт для редагування (settlement=%s, row=%s)", settlement, row_idx)
        await callback.message.answer("⚠️ Сталася помилка під час читання даних із таблиці.")
        return

    if row is None:
        await callback.message.answer("⚠️ Цей об'єкт більше не знайдено в таблиці (можливо, його видалили).")
        return

    await state.clear()
    await state.update_data(
        mode="edit",
        settlement=settlement,
        row_idx=row_idx,
        deal_type=row.get("Тип угоди", ""),
        property_type=row.get("Тип об'єкта", ""),
        price=row.get("Ціна") or None,
        currency=row.get("Валюта") or None,
        area_sqm=row.get("Площа, м²") or None,
        area_sot=row.get("Площа ділянки, сот.") or None,
        description=row.get("Опис") or None,
        photos=gs.split_links(row.get("Фото", "")),
        videos=gs.split_links(row.get("Відео", "")),
        address=row.get("Адреса / локація") or None,
        link=row.get("Посилання") or None,
        tiktok=row.get("Відео TikTok") or None,
        new_upload_ids=[],
    )

    logger.info("Користувач %s розпочав редагування %s (рядок %s)", callback.from_user.id, settlement, row_idx)
    deal_type_value = row.get("Тип угоди", "—")
    property_type_value = row.get("Тип об'єкта", "—")
    await callback.message.answer(
        f"✏️ Редагування об'єкта: {deal_type_value}, {property_type_value}, {settlement}.\n"
        "Кроки 1-3 (населений пункт/тип угоди/тип об'єкта) залишаються незмінними. "
        "Якщо на кроці нічого не ввести й натиснути «➡️ Далі» - поточне значення збережеться."
    )
    await show_step(callback.message, state, "price")
