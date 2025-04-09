# ===== gspread_client.py =====
import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1OaZbj_2HEPwamJwS3VBgGQBi5QY3Pl0zhIQ8Wn6hWJM/edit?usp=sharing"

spreadsheet = client.open_by_url(SPREADSHEET_URL)

def get_sheet_by_title(title):
    return spreadsheet.worksheet(title)

def list_cities():
    sheet = get_sheet_by_title("Міста")
    return sheet.col_values(1)[1:]  # пропускаємо заголовок

def list_streets(city):
    sheet = get_sheet_by_title("Вулиці")
    all_data = sheet.get_all_records()
    return [row['Назва'] for row in all_data if row['Місто'] == city]

def list_users_by_street(city, street):
    try:
        sheet = get_sheet_by_title(f"{city}_{street}")
        return sheet.get_all_records()
    except:
        return []
