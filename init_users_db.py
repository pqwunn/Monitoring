# init_users_db.py
import sqlite3

def init_users_db(db_name='users.db'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_categories (
            user_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    ''')

    # Очистим таблицы перед заполнением (для тестов)
    cursor.execute('DELETE FROM users')
    cursor.execute('DELETE FROM user_categories')

    # Тестовые пользователи (id от 1 до 5)
    users = [
        (1, 'Иван Иванов', 'ivan@example.com'),
        (2, 'Мария Петрова', 'maria@example.com'),
        (3, 'Алексей Смирнов', 'alex@example.com'),
        (4, 'Елена Кузнецова', 'elena@example.com'),
        (5, 'Дмитрий Попов', 'dmitry@example.com')
    ]
    cursor.executemany('INSERT INTO users (id, name, email) VALUES (?, ?, ?)', users)

    # Категории (id соответствуют тем, что мы зададим в парсерах)
    # 1 - Наука, 2 - Образование, 3 - Студенческая жизнь, 4 - Спорт,
    # 5 - Культура, 6 - Международная, 7 - Сотрудничество, 8 - Объявления,
    # 9 - Абитуриентам, 10 - Без категории
    user_categories = [
        (1, 1), (1, 9),           # Иван: Наука, Абитуриентам
        (2, 2), (2, 3), (2, 5),   # Мария: Образование, Студ.жизнь, Культура
        (3, 4), (3, 8),           # Алексей: Спорт, Объявления
        (4, 1), (4, 2), (4, 6),   # Елена: Наука, Образование, Международная
        (5, 3), (5, 9), (5, 10)   # Дмитрий: Студ.жизнь, Абитуриентам, Без категории
    ]
    cursor.executemany('INSERT INTO user_categories (user_id, category_id) VALUES (?, ?)', user_categories)

    conn.commit()
    conn.close()
    print(f"База данных {db_name} успешно инициализирована тестовыми данными.")

if __name__ == '__main__':
    init_users_db()