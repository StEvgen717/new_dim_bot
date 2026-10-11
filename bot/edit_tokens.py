"""Короткоживучий реєстр токенів для кнопки "✏️ Редагувати".

Telegram callback_data обмежений 64 байтами, а назва населеного пункту
(аркуша) може бути довгою, тож замість того, щоб кодувати
"settlement:row" прямо в callback_data, кожній картці об'єкта у видачі
пошуку присвоюється короткий одноразовий токен, який мапиться на
конкретні (settlement, row_idx) тут, у пам'яті процесу.

Це свідомо просте in-memory рішення: бот працює в одному процесі, і
втрата токенів після перезапуску некритична - користувачу достатньо
повторити пошук.
"""
from __future__ import annotations

from collections import OrderedDict
from itertools import count

_tokens: "OrderedDict[str, tuple[str, int]]" = OrderedDict()
_counter = count(1)

# Щоб словник не ріс необмежено на довготривалому проді, тримаємо лише
# останні N виданих токенів.
_MAX_TOKENS = 2000


def register(settlement: str, row_idx: int) -> str:
    """Реєструє пару (аркуш, рядок) і повертає короткий токен для неї."""
    token = f"{next(_counter):x}"
    _tokens[token] = (settlement, row_idx)
    while len(_tokens) > _MAX_TOKENS:
        _tokens.popitem(last=False)
    return token


def resolve(token: str) -> tuple[str, int] | None:
    """Повертає (аркуш, рядок) для токена або None, якщо він застарів."""
    return _tokens.get(token)
