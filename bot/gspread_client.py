# ===== gspread_client.py =====
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from tenacity import retry, stop_after_attempt, wait_fixed

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1vGeHL_HXL_xvu_tNgEiFOrwI9_w4hmrZqweMJn7NEzg/edit?usp=sharing"

spreadsheet = client.open_by_url(SPREADSHEET_URL)

def get_sheet_by_title(title):
    return spreadsheet.worksheet(title)

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def safe_get_all_records(sheet):
    return sheet.get_all_records()

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def safe_col_values(sheet, col):
    return sheet.col_values(col)

def list_cities():
    sheet = get_sheet_by_title("Міста")
    return safe_col_values(sheet, 1)[1:]  # пропускаємо заголовок

def list_streets(city):
    sheet = get_sheet_by_title("Вулиці")
    all_data = safe_get_all_records(sheet)
    return [row['Назва'] for row in all_data if row['Місто'] == city]


def list_users_by_street(city, street):
    try:
        target_title = f"{city}_{street}"
        target_title_lower = target_title.lower()
        found_sheet = None

        # Перебираємо всі аркуші та знаходимо той, назва якого співпадає незалежно від регістра
        for ws in spreadsheet.worksheets():
            if ws.title.lower() == target_title_lower:
                found_sheet = ws
                break

        if not found_sheet:
            raise Exception(f"[Помилка] Лист '{city}_{street}' не знайдено або інша помилка")

        all_data = safe_get_all_records(found_sheet)
        return [row for row in all_data if str(row.get("ПІБ", "")).strip()]  # ігноруємо порожні ПІБ
    except Exception as e:
        print(f"[Помилка] Лист '{city}_{street}' не знайдено або інша помилка: {e}")
        return []

def get_user_by_contract_or_name(query):
    query = str(query).strip().lower()
    matched_users = []

    # підтримка форматів:
    # "Іванов І.І.", "Іванов І.І", "Іванов І. В.", "Іванов І В" — з крапками або без
    short_name_pattern = re.compile(r"^([а-щьюяєіїґa-z'-]+)\s+([а-щьюяєіїґa-z])\.?\s*([а-щьюяєіїґa-z])\.?$", re.IGNORECASE)

    for worksheet in spreadsheet.worksheets():
        title = worksheet.title
        if title in ["Міста", "Вулиці"]:
            continue

        try:
            data = safe_get_all_records(worksheet)
        except Exception as e:
            print(f"[Помилка при читанні листа {title}]: {e}")
            continue

        for row in data:
            contract = str(row.get("номер договору", "")).strip().lower()
            name = str(row.get("ПІБ", "")).strip()

            if not name:
                continue  # ігноруємо пусті ПІБ

            name_lower = name.lower()

            # точне співпадіння по договору
            if query == contract:
                return row

            # ПІБ в форматі Прізвище І.П. або Прізвище І П
            match = short_name_pattern.match(query)
            if match:
                surname, initial1, initial2 = match.groups()
                if name_lower.startswith(surname.lower()) and \
                   initial1.lower() in name_lower and \
                   initial2.lower() in name_lower:
                    matched_users.append(row)

    if len(matched_users) == 1:
        return matched_users[0]
    elif len(matched_users) > 1:
        return {"message": "multiple", "count": len(matched_users)}

    return None