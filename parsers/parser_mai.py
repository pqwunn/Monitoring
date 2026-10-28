import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import sqlite3
import urllib3

# Отключаем предупреждения об отсутствии SSL-сертификатов (для Mac)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://mai.ru/press/news/?tags=7462"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}
MAX_PAGES = 2
DB_NAME = 'news.db'

MONTHS_RU = {'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'мая': 5, 'июн': 6, 'июл': 7, 'авг': 8, 'сен': 9,
             'окт': 10, 'ноя': 11, 'дек': 12}


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

    categories = [(1, "Наука и инновации"), (2, "Образование"), (3, "Студенческая жизнь"), (4, "Спорт"),
                  (5, "Культура и творчество"), (6, "Международная деятельность"), (7, "Сотрудничество и партнёрство"),
                  (8, "Объявления и события"), (9, "Абитуриентам"), (10, "Без категории")]
    cursor.executemany('INSERT OR IGNORE INTO news_categories (category_id, name) VALUES (?, ?)', categories)
    cursor.execute('INSERT OR IGNORE INTO universities (university_id, name) VALUES (?, ?)', (2, 'МАИ'))

    conn.commit()
    return conn, cursor


def get_university_id(cursor, name='МАИ'):
    cursor.execute('SELECT university_id FROM universities WHERE name = ?', (name,))
    row = cursor.fetchone()
    return row[0] if row else 2


def parse_mai_date(date_text, default_year=None):
    if default_year is None: default_year = datetime.now().year
    text = date_text.strip().lower()
    m = re.match(r'(\d{1,2})\s+([а-яё]+)(?:\s+(\d{4}))?', text)
    if not m: return None

    day = int(m.group(1))
    month_key = m.group(2)[:3]
    year_str = m.group(3)
    month = MONTHS_RU.get(month_key)

    if not month: return None

    year = int(year_str) if year_str else default_year
    try:
        return datetime(year, month, day).strftime('%Y-%m-%d 00:00:00')
    except ValueError:
        return None


def parse():
    print("[МАИ] Начало парсинга...")
    conn, cursor = init_db()
    uni_id = get_university_id(cursor, 'МАИ')
    session = requests.Session()
    session.headers.update(HEADERS)
    new_count = 0

    try:
        # verify=False для обхода SSL-ошибки
        r = session.get(BASE_URL, timeout=30, verify=False)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'lxml')

        articles = soup.find_all('article')
        for art in articles:
            h5 = art.find('h5', class_='mb-3')
            if not h5: continue

            title = h5.get_text(strip=True)

            date_span = art.find('span', class_='badge')
            if not date_span: continue

            pub_date = parse_mai_date(date_span.get_text(strip=True))
            if not pub_date: continue

            a_tag = art.find_parent('a')
            href = a_tag.get('href', '') if a_tag else ''
            link = href if href.startswith('http') else f"https://mai.ru/press/news/{href}"

            content = ""
            cat_id = 9

            cursor.execute(
                '''INSERT OR IGNORE INTO news (title, content, link, published_date, category_id, university_id) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (title, content, link, pub_date, cat_id, uni_id)
            )
            if cursor.rowcount > 0:
                new_count += 1

        conn.commit()
        print(f"[МАИ] Успешно. Добавлено новых новостей: {new_count}")
    except Exception as e:
        print(f"[МАИ] Ошибка: {e}")
        conn.rollback()
    finally:
        conn.close()