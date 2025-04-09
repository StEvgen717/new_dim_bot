import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random

# Авторизація
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(credentials)

# Посилання на таблицю
spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1OaZbj_2HEPwamJwS3VBgGQBi5QY3Pl0zhIQ8Wn6hWJM/edit?usp=sharing")

# Структура населених пунктів та вулиць
data = {
    "Борова": ["пров.Абрикосовий", "вулиця Київська"],
    "Мотовилівка": ["вулиця Шевченка", "вулиця Л. Українки"],
    "Мот. Слобідка": ["вулиця Бендери", "вулиця Шухевича"]
}

names = [
    ("Іванов", "Іван", "Іванович"),
    ("Шевченко", "Тарас", "Григорович"),
    ("Коваленко", "Ольга", "Василівна"),
    ("Петренко", "Микола", "Ігорович"),
    ("Гончар", "Леся", "Петрівна"),
    ("Бондар", "Сергій", "Олександрович")
]

months = ["Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
          "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"]

contract_number = 1000

# Додаємо перший лист
def get_or_create_sheet(spreadsheet, title, rows="100", cols="20"):
    try:
        return spreadsheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)

# Додаємо перший лист — список населених пунктів
city_sheet = get_or_create_sheet(spreadsheet, "Міста")
city_sheet.clear()
city_sheet.update("A1", [["Назва"]])
city_sheet.update("A2", [[city] for city in data.keys()])


# Додаємо другий лист — вулиці до міст
street_sheet = get_or_create_sheet(spreadsheet,"Вулиці")
street_sheet.clear()
street_sheet.update("A1", [["Назва", "Місто"]])
street_rows = []
for city, streets in data.items():
    for street in streets:
        street_rows.append([street, city])
street_sheet.update("A2", street_rows)

# Створюємо окремі листи для кожної вулиці
for city, streets in data.items():
    for street in streets:
        sheet_name = f"{city}_{street}".replace(" ", "_")[:100]
        try:
            ws = spreadsheet.worksheet(sheet_name)
            ws.clear()
        except:
            ws = spreadsheet.add_worksheet(title=sheet_name, rows="50", cols="20")

        headers = ["№ будинку", "ПІБ", "номер договору", "кількість мішків"] + months
        rows = []

        for house_number in range(1, 3):
            full_name = random.choice(names)
            bags = random.choice([1, 2, 3])
            payment = round(bags * 42.25, 2)
            row = [
                str(house_number),
                f"{full_name[0]} {full_name[1]} {full_name[2]}",
                str(contract_number),
                bags,
            ] + [payment] * 12
            contract_number += 1
            rows.append(row)

        ws.update("A1", [headers])
        ws.update("A2", rows)
