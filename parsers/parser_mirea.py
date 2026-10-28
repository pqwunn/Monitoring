import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import sqlite3

URL = "https://www.mirea.ru/news/index.php?set_filter=Y&arrFilter_ff[TAGS]=абитуриентам"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
DB_NAME = 'news.db'


def init_db(db_name=DB_NAME):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, content TEXT,
            link TEXT UNIQUE NOT NULL, published_date TEXT NOT NULL,
            category_id INTEGER NOT NULL, university_id INTEGER NOT NULL,
            added_at TEXT DEFAULT (datetime('now'))
        );
    ''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS news_categories (category_id INTEGER NOT NULL, name TEXT NOT NULL);''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS universities (university_id INTEGER NOT NULL, name TEXT NOT NULL);''')
    cursor.execute('INSERT OR IGNORE INTO universities (university_id, name) VALUES (?, ?)', (3, 'МИРЭА'))
    conn.commit()
    return conn, cursor


def get_university_id(cursor, name='МИРЭА'):
    cursor.execute('SELECT university_id FROM universities WHERE name = ?', (name,))
    row = cursor.fetchone()
    return row[0] if row else 3


def normalize_date(date_str):
    try:
        return datetime.strptime(date_str, "%d.%m.%Y").strftime('%Y-%m-%d 00:00:00')
    except ValueError:
        pass
    months_ru = {"января": "01", "февраля": "02", "марта": "03", "апреля": "04", "мая": "05", "июня": "06",
                 "июля": "07", "августа": "08", "сентября": "09", "октября": "10", "ноября": "11", "декабря": "12"}
    match = re.match(r"(\d{1,2})\s+([а-я]+)\s+(\d{4})", date_str.lower())
    if match:
        day, month_name, year = match.groups()
        month = months_ru.get(month_name)
        if month: return f"{year}-{month}-{day.zfill(2)} 00:00:00"
    return datetime.now().strftime('%Y-%m-%d 00:00:00')


def parse():
    print("[МИРЭА] Начало парсинга...")
    conn, cursor = init_db()
    uni_id = get_university_id(cursor, 'МИРЭА')
    new_count = 0

    try:
        resp = requests.get(URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        items = soup.select(".news-item")
        if not items:
            items = soup.select("article")

        for card in items:
            title_tag = card.select_one("h2 a, .news-title a, h3 a, h2, h3, .title")
            date_tag = card.select_one(".news-date, .date, span.date, .date, time")

            if not title_tag or not date_tag: continue

            title = title_tag.get_text(strip=True)
            pub_date = normalize_date(date_tag.get_text(strip=True))

            link = ""
            if title_tag.name == 'a':
                link = title_tag.get('href', '')
            else:
                parent_a = title_tag.find_parent('a')
                if parent_a: link = parent_a.get('href', '')

            if link and not link.startswith('http'):
                link = "https://www.mirea.ru" + link

            content = ""
            cat_id = 9

            cursor.execute(
                '''INSERT OR IGNORE INTO news (title, content, link, published_date, category_id, university_id) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (title, content, link, pub_date, cat_id, uni_id)
            )
            if cursor.rowcount > 0: new_count += 1

        conn.commit()
        print(f"[МИРЭА] Успешно. Добавлено новых новостей: {new_count}")
    except Exception as e:
        print(f"[МИРЭА] Ошибка: {e}")
        conn.rollback()
    finally:
        conn.close()