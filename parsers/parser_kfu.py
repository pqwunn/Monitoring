import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import sys
import os
import urllib3

# Отключаем предупреждения об отсутствии SSL-сертификатов (для Mac)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = 'https://media.kpfu.ru/news/'
MAX_PAGES = 2
DB_NAME = 'news.db'

CATEGORY_ID = {
    "Наука и инновации": 1,
    "Образование": 2,
    "Студенческая жизнь": 3,
    "Спорт": 4,
    "Культура и творчество": 5,
    "Международная деятельность": 6,
    "Сотрудничество и партнёрство": 7,
    "Объявления и события": 8,
    "Абитуриентам": 9,
    "Без категории": 10
}

CATEGORY_KEYS = {
    "Новости науки": 1, "Новости институтов": 1,
    "Новости образования": 2, "Новости клиники": 2, "Новости лицеев": 2,
    "Студенческая жизнь": 3,
    "Международное сотрудничество": 6,
    "Выпускнику": 7,
    "Новости ректора": 8, "Акции, мероприятия": 8,
    "Абитуриенту": 9
}


def init_db(db_name=DB_NAME):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            link TEXT UNIQUE NOT NULL,
            published_date TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            university_id INTEGER NOT NULL,
            added_at TEXT DEFAULT (datetime('now'))
        );
    ''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS news_categories (category_id INTEGER NOT NULL, name TEXT NOT NULL);''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS universities (university_id INTEGER NOT NULL, name TEXT NOT NULL);''')

    for name, cid in CATEGORY_ID.items():
        cursor.execute('INSERT OR IGNORE INTO news_categories (category_id, name) VALUES (?, ?)', (cid, name))

    cursor.execute('INSERT OR IGNORE INTO universities (university_id, name) VALUES (?, ?)', (1, 'КФУ'))
    conn.commit()
    return conn, cursor


def get_university_id(cursor, name='КФУ'):
    cursor.execute('SELECT university_id FROM universities WHERE name = ?', (name,))
    row = cursor.fetchone()
    return row[0] if row else 1


def fetch_html(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        # verify=False для обхода ошибок SSL на macOS
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"[КФУ] Ошибка запроса {url}: {e}")
        return None


def get_category_id(link):
    html = fetch_html(link)
    if not html: return 10
    soup = BeautifulSoup(html, 'html.parser')
    block = soup.select_one('.newsCart-cat')
    if block:
        text = block.get_text()
        for key, cid in CATEGORY_KEYS.items():
            if key in text:
                return cid
    return 10


def parse():
    print("[КФУ] Начало парсинга...")
    conn, cursor = init_db()
    uni_id = get_university_id(cursor, 'КФУ')
    page = 1
    current_url = BASE_URL
    new_count = 0

    try:
        while page <= MAX_PAGES:
            html = fetch_html(current_url)
            if not html: break

            soup = BeautifulSoup(html, 'html.parser')
            items = soup.select('.newsItem')
            if not items: break

            for block in items:
                link_tag = block.select_one('.boldLink')
                date_tag = block.select_one('.newsItem-date')
                if not link_tag or not date_tag: continue

                title = link_tag.text.strip()
                href = link_tag.get('href', '')
                link = 'https://media.kpfu.ru' + href if href.startswith('/') else href

                raw_date = date_tag.text.strip()
                try:
                    dt = datetime.strptime(raw_date, '%d.%m.%Y')
                    pub_date = dt.strftime('%Y-%m-%d 00:00:00')
                except ValueError:
                    pub_date = raw_date

                content_tag = block.select_one('.newsItem-text')
                content = content_tag.text.strip() if content_tag else None

                cat_id = get_category_id(link)

                cursor.execute(
                    '''INSERT OR IGNORE INTO news 
                       (title, content, link, published_date, category_id, university_id) 
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (title, content, link, pub_date, cat_id, uni_id)
                )
                if cursor.rowcount > 0:
                    new_count += 1

            next_btn = soup.select_one('.pager__item.pager__item--next a')
            if not next_btn: break
            current_url = BASE_URL + next_btn.get('href', '')
            page += 1

        conn.commit()
        print(f"[КФУ] Успешно. Добавлено новых новостей: {new_count}")
    except Exception as e:
        print(f"[КФУ] Критическая ошибка: {e}")
        conn.rollback()
    finally:
        conn.close()