"""Інтеграція з Google Sheets та Google Drive для бота Estate Atlas.

Автентифікація - через OAuth-клієнт типу "Desktop app" (``gspread.oauth``):
при першому запуску відкриється браузер із запитом увійти Google-акаунтом,
який має доступ до таблиці й папки на Drive. Після підтвердження токен
кешується у файлі ``GOOGLE_OAUTH_TOKEN_FILE`` (``token.json``) і надалі
оновлюється автоматично, без повторного входу.

Ті самі credentials використовуються і для gspread (Sheets), і для
Google Drive API - окремий сервісний акаунт не потрібен.
"""
from __future__ import annotations

import asyncio
import logging
import re
from io import BytesIO
from typing import Optional

import gspread
from gspread.auth import DEFAULT_SCOPES, local_server_flow
from gspread.exceptions import WorksheetNotFound
from gspread.utils import rowcol_to_a1
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from tenacity import retry, stop_after_attempt, wait_fixed

from config import (
    EXCLUDED_SHEETS,
    GOOGLE_DRIVE_FOLDER_ID,
    GOOGLE_OAUTH_CLIENT_FILE,
    GOOGLE_OAUTH_TOKEN_FILE,
    GOOGLE_SHEET_NAME,
    GOOGLE_SPREADSHEET_ID,
    SHEET_HEADERS,
)

logger = logging.getLogger(__name__)

# Усі синхронні звернення до Google API повторюємо до 3 разів - API Sheets
# та Drive інколи повертають тимчасові 429/5xx помилки.
_retry = retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)

_gc = gspread.oauth(
    scopes=DEFAULT_SCOPES,  # spreadsheets + drive (read/write)
    flow=local_server_flow,
    credentials_filename=str(GOOGLE_OAUTH_CLIENT_FILE),
    authorized_user_filename=str(GOOGLE_OAUTH_TOKEN_FILE),
)
_spreadsheet = _gc.open_by_key(GOOGLE_SPREADSHEET_ID)
_drive = build("drive", "v3", credentials=_gc.http_client.auth, cache_discovery=False)

if GOOGLE_SHEET_NAME and _spreadsheet.title != GOOGLE_SHEET_NAME:
    logger.warning(
        "GOOGLE_SHEET_NAME='%s' не збігається з назвою відкритої таблиці '%s'. "
        "Перевірте GOOGLE_SPREADSHEET_ID у .env, якщо це не очікувано.",
        GOOGLE_SHEET_NAME, _spreadsheet.title,
    )

logger.info("Google Sheets/Drive: авторизація успішна, таблиця '%s'.", _spreadsheet.title)


# ---------------------------------------------------------------------------
# Допоміжні функції
# ---------------------------------------------------------------------------

def split_links(raw: str) -> list[str]:
    """Розбиває комірку з кількома посиланнями (по рядку/комі) на список."""
    if not raw:
        return []
    return [piece.strip() for piece in re.split(r"[\n,]+", raw) if piece.strip()]


def _header_map(worksheet: gspread.Worksheet) -> dict[str, int]:
    """Назва колонки -> її номер (1-based). Порядок колонок не важливий."""
    headers = worksheet.row_values(1)
    return {name.strip(): idx + 1 for idx, name in enumerate(headers) if name.strip()}


def _ensure_headers(worksheet: gspread.Worksheet) -> None:
    """Створює рядок заголовків, якщо аркуш порожній; попереджає, якщо
    на наявному аркуші відсутні очікувані колонки (бот тоді просто не
    зможе записати відповідне поле)."""
    current = worksheet.row_values(1)
    cleaned = [h.strip() for h in current if h.strip()]
    if cleaned == SHEET_HEADERS:
        return
    if not cleaned:
        worksheet.update(values=[SHEET_HEADERS], range_name="A1", value_input_option="RAW")
        return
    missing = [h for h in SHEET_HEADERS if h not in cleaned]
    if missing:
        logger.warning(
            "Аркуш '%s' не містить колонок: %s. Ці значення не будуть збережені.",
            worksheet.title, ", ".join(missing),
        )


def _get_worksheet(settlement: str) -> gspread.Worksheet:
    try:
        return _spreadsheet.worksheet(settlement)
    except WorksheetNotFound as exc:
        raise ValueError(f"Населений пункт (аркуш) '{settlement}' не знайдено.") from exc


# ---------------------------------------------------------------------------
# Населені пункти
# ---------------------------------------------------------------------------

@_retry
def _list_settlements_sync() -> list[str]:
    return [ws.title for ws in _spreadsheet.worksheets() if ws.title not in EXCLUDED_SHEETS]


async def list_settlements() -> list[str]:
    """Список населених пунктів = список назв аркушів таблиці."""
    return await asyncio.to_thread(_list_settlements_sync)


# ---------------------------------------------------------------------------
# Об'єкти нерухомості: створення / читання / оновлення
# ---------------------------------------------------------------------------

@_retry
def _append_object_sync(settlement: str, field_values: dict[str, str]) -> int:
    worksheet = _get_worksheet(settlement)
    _ensure_headers(worksheet)
    headers = _header_map(worksheet)
    if not headers:
        raise RuntimeError(f"Аркуш '{settlement}' не має заголовків колонок.")

    max_col = max(headers.values())
    row: list[str] = [""] * max_col
    for name, value in field_values.items():
        col = headers.get(name)
        if col:
            row[col - 1] = value
        else:
            logger.warning("Колонку '%s' не знайдено в аркуші '%s' - значення пропущено.", name, settlement)

    response = worksheet.append_row(row, value_input_option="USER_ENTERED")
    updated_range = ""
    if isinstance(response, dict):
        updated_range = response.get("updates", {}).get("updatedRange", "")
    match = re.search(r"![A-Za-z]+(\d+)", updated_range)
    if match:
        return int(match.group(1))
    # fallback, якщо API не повернув updatedRange (малоймовірно)
    return len(worksheet.get_all_values())


async def append_object(settlement: str, field_values: dict[str, str]) -> int:
    """Додає новий рядок об'єкта в аркуш населеного пункту.

    ``field_values`` - словник {назва_колонки: значення}; колонки, яких
    немає в словнику, залишаються порожніми.
    Повертає номер щойно створеного рядка (1-based, з урахуванням заголовка).
    """
    return await asyncio.to_thread(_append_object_sync, settlement, field_values)


@_retry
def _update_object_sync(settlement: str, row_idx: int, field_values: dict[str, str]) -> None:
    worksheet = _get_worksheet(settlement)
    _ensure_headers(worksheet)
    headers = _header_map(worksheet)
    if not headers:
        raise RuntimeError(f"Аркуш '{settlement}' не має заголовків колонок.")

    max_col = max(headers.values())
    current = worksheet.row_values(row_idx)
    current = current + [""] * (max_col - len(current))
    for name, value in field_values.items():
        col = headers.get(name)
        if col:
            current[col - 1] = value

    start = rowcol_to_a1(row_idx, 1)
    end = rowcol_to_a1(row_idx, max_col)
    worksheet.update(
        values=[current[:max_col]],
        range_name=f"{start}:{end}",
        value_input_option="USER_ENTERED",
    )


async def update_object(settlement: str, row_idx: int, field_values: dict[str, str]) -> None:
    """Оновлює лише перелічені в ``field_values`` колонки конкретного рядка,
    решту колонок (напр. "Коментар", "Статус") залишає незмінними."""
    await asyncio.to_thread(_update_object_sync, settlement, row_idx, field_values)


@_retry
def _get_object_sync(settlement: str, row_idx: int) -> Optional[dict[str, str]]:
    worksheet = _get_worksheet(settlement)
    headers = worksheet.row_values(1)
    if row_idx < 2:
        return None
    values = worksheet.row_values(row_idx)
    if not values or not any(v.strip() for v in values):
        return None
    return {
        headers[i].strip(): (values[i] if i < len(values) else "")
        for i in range(len(headers))
        if headers[i].strip()
    }


async def get_object(settlement: str, row_idx: int) -> Optional[dict[str, str]]:
    """Повертає {назва_колонки: значення} для рядка або None, якщо рядок
    порожній / видалений."""
    return await asyncio.to_thread(_get_object_sync, settlement, row_idx)


@_retry
def _list_objects_sync(settlement: str) -> list[tuple[int, dict[str, str]]]:
    worksheet = _get_worksheet(settlement)
    all_values = worksheet.get_all_values()
    if not all_values:
        return []

    headers = [h.strip() for h in all_values[0]]
    if "Тип угоди" not in headers:
        return []
    deal_col = headers.index("Тип угоди")

    results: list[tuple[int, dict[str, str]]] = []
    for offset, row in enumerate(all_values[1:], start=2):
        if deal_col < len(row) and row[deal_col].strip():
            data = {
                headers[i]: (row[i] if i < len(row) else "")
                for i in range(len(headers))
                if headers[i]
            }
            results.append((offset, data))
    return results


async def list_objects(settlement: str) -> list[tuple[int, dict[str, str]]]:
    """Повертає [(номер_рядка, {колонка: значення})] для рядків аркуша,
    де колонка "Тип угоди" не порожня (критерій пошуку зі специфікації)."""
    return await asyncio.to_thread(_list_objects_sync, settlement)


# ---------------------------------------------------------------------------
# Google Drive: завантаження фото/відео
# ---------------------------------------------------------------------------

@_retry
def _upload_to_drive_sync(content: bytes, filename: str, mime_type: str) -> tuple[str, str]:
    media = MediaIoBaseUpload(BytesIO(content), mimetype=mime_type, resumable=True)
    file = _drive.files().create(
        body={"name": filename, "parents": [GOOGLE_DRIVE_FOLDER_ID]},
        media_body=media,
        fields="id, webViewLink",
    ).execute()
    file_id = file["id"]

    # Робимо файл доступним за посиланням, щоб клієнти могли відкрити й
    # завантажити фото/відео прямо з браузера (без доступу до самого Google-акаунта бота).
    try:
        _drive.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            fields="id",
        ).execute()
    except Exception:
        logger.exception("Не вдалося встановити публічний доступ для файлу %s", file_id)

    link = file.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view"
    return file_id, link


async def upload_to_drive(content: bytes, filename: str, mime_type: str) -> tuple[str, str]:
    """Завантажує байти файлу в папку GOOGLE_DRIVE_FOLDER_ID.

    Повертає (file_id, link_для_перегляду).
    """
    return await asyncio.to_thread(_upload_to_drive_sync, content, filename, mime_type)


_DRIVE_ID_PATTERNS = (
    re.compile(r"/file/d/([a-zA-Z0-9_-]{10,})"),
    re.compile(r"[?&]id=([a-zA-Z0-9_-]{10,})"),
)


def extract_drive_file_id(link: str) -> Optional[str]:
    """Витягує ID файлу Google Drive з посилання (``.../file/d/<ID>/view``,
    ``...?id=<ID>`` тощо - основні формати, які повертає Drive API або які
    могли вставити вручну)."""
    link = (link or "").strip()
    for pattern in _DRIVE_ID_PATTERNS:
        match = pattern.search(link)
        if match:
            return match.group(1)
    return None


@_retry
def _download_from_drive_sync(file_id: str) -> bytes:
    return _drive.files().get_media(fileId=file_id).execute()


async def download_from_drive(file_id: str) -> bytes:
    """Завантажує байти файлу з Google Drive (щоб показати фото прямо в
    Telegram, а не лише посиланням)."""
    return await asyncio.to_thread(_download_from_drive_sync, file_id)


@_retry
def _delete_from_drive_sync(file_id: str) -> None:
    _drive.files().delete(fileId=file_id).execute()


async def delete_from_drive(file_id: str) -> None:
    await asyncio.to_thread(_delete_from_drive_sync, file_id)


async def cleanup_uploads(file_ids: list[str]) -> None:
    """Видаляє з Drive файли, завантажені в межах скасованої/незбереженої
    сесії (щоб не накопичувалось сміття в папці), ігноруючи помилки."""
    for file_id in file_ids:
        try:
            await delete_from_drive(file_id)
        except Exception:
            logger.exception("Не вдалося видалити тимчасовий файл %s із Google Drive", file_id)
