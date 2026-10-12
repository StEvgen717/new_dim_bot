"""FSM-стани бота."""
from aiogram.fsm.state import State, StatesGroup


class AddObjectStates(StatesGroup):
    """13 кроків майстра "Додати об'єкт" (ті самі кроки використовуються
    і для редагування - воно просто стартує з кроку ``price``)."""

    settlement = State()      # 1. Населений пункт
    deal_type = State()       # 2. Тип угоди
    property_type = State()   # 3. Тип об'єкта
    price = State()           # 4. Ціна
    currency = State()        # 5. Валюта
    area_sqm = State()        # 6. Площа, м² (окремий крок, незалежно від типу об'єкта)
    area_sot = State()        # 7. Площа ділянки, сот. (окремий крок, незалежно від типу об'єкта)
    description = State()     # 8. Опис
    photos = State()          # 9. Фото
    videos = State()          # 10. Відео
    address = State()         # 11. Адреса / локація
    link = State()            # 12. Посилання
    tiktok = State()          # 13. Відео TikTok (посилання)


class SearchStates(StatesGroup):
    """Єдиний стан на весь час пошуку: клавіатура з населеними пунктами
    лишається активною, тож користувач може будь-коли обрати інший
    населений пункт. Пагінація ("Показати ще") - це inline-кнопка,
    яка обробляється окремим callback-хендлером і не залежить від стану."""

    choosing_settlement = State()
