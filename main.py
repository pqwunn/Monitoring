# main.py
import json
import os
import sqlite3
import importlib
import time
import sys
import logging
from datetime import datetime

# Настройка логирования (вывод в консоль и в файл monitor.log)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("monitor.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def load_config(config_path='config.json'):
    """Загружает настройки из JSON-файла."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Файл конфигурации {config_path} не найден.")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"Ошибка синтаксиса в {config_path}.")
        sys.exit(1)


def run_parsers(parsers_dir):
    """Импортирует и запускает все модули парсеров из папки."""
    logger.info("--- Запуск парсеров ---")
    if not os.path.exists(parsers_dir):
        logger.error(f"Папка {parsers_dir} не найдена.")
        return

    # Добавляем корневую директорию в путь, чтобы модули внутри parsers нашли БД
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

    for filename in os.listdir(parsers_dir):
        if filename.endswith('.py') and filename.startswith('parser_'):
            module_name = filename[:-3]  # убираем .py
            try:
                # Импортируем модуль (например, parsers.parser_kfu)
                module = importlib.import_module(f"{parsers_dir.replace('/', '.')}.{module_name}")
                # Перезагружаем на случай, если код изменился
                importlib.reload(module)

                if hasattr(module, 'parse'):
                    module.parse()
                else:
                    logger.warning(f"В модуле {module_name} нет функции parse().")
            except Exception as e:
                logger.error(f"Ошибка при запуске {module_name}: {e}")


def generate_send_list(config, last_news_id):
    """
    Формирует send_list.txt на основе новых новостей и интересов пользователей.
    Возвращает ID последней обработанной новости.
    """
    logger.info("--- Формирование списка рассылки ---")
    news_db = config['news_db']
    users_db = config['users_db']
    output_file = config['output_file']

    # Соединяемся с БД новостей
    try:
        news_conn = sqlite3.connect(news_db)
        news_cursor = news_conn.cursor()
    except sqlite3.Error as e:
        logger.error(f"Ошибка подключения к {news_db}: {e}")
        return last_news_id

    # Получаем новые новости, у которых id больше, чем в прошлый раз
    news_cursor.execute('''
        SELECT id, category_id FROM news 
        WHERE id > ?
        ORDER BY id ASC
    ''', (last_news_id,))
    new_news = news_cursor.fetchall()

    # Обновляем last_news_id для следующего цикла
    current_max_id = last_news_id
    if new_news:
        current_max_id = new_news[-1][0]

    news_conn.close()

    if not new_news:
        logger.info("Новых новостей нет. Файл рассылки не обновлён.")
        # Очищаем файл, чтобы он не содержал старых данных
        with open(output_file, 'w', encoding='utf-8') as f:
            pass
        return current_max_id

    logger.info(f"Найдено новых новостей для рассылки: {len(new_news)}")

    # Соединяемся с БД пользователей
    try:
        users_conn = sqlite3.connect(users_db)
        users_cursor = users_conn.cursor()
    except sqlite3.Error as e:
        logger.error(f"Ошибка подключения к {users_db}: {e}")
        return current_max_id

    # Получаем всех пользователей
    users_cursor.execute('SELECT id, name FROM users')
    users = users_cursor.fetchall()

    send_list = []

    for user_id, user_name in users:
        # Получаем категории, которые отслеживает пользователь
        users_cursor.execute('SELECT category_id FROM user_categories WHERE user_id = ?', (user_id,))
        user_cats = {row[0] for row in users_cursor.fetchall()}

        # Находим новости, подходящие под категории пользователя
        user_news_ids = [str(n_id) for n_id, cat_id in new_news if cat_id in user_cats]

        if user_news_ids:
            line = f"{user_id}: {', '.join(user_news_ids)}\n"
            send_list.append(line)
            logger.info(f"Пользователь {user_id} ({user_name}) получит {len(user_news_ids)} новостей.")

    users_conn.close()

    # Записываем в файл (перезаписываем)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(send_list)

    logger.info(f"Файл {output_file} успешно сформирован. Строк в файле: {len(send_list)}")
    return current_max_id


def main():
    config = load_config()
    interval_minutes = config.get('interval_minutes', 60)

    logger.info("=== Запуск программного комплекса ===")

    # При старте программы устанавливаем last_news_id = 0,
    # чтобы при первом цикле захватить всё, что есть в базе.
    last_news_id = 0

    try:
        while True:
            # 1. Запуск парсеров (они добавляют новости в news.db)
            run_parsers(config['parsers_dir'])

            # 2. Генерация списка рассылки
            # Передаем last_news_id, чтобы функция знала, с какого момента искать новое
            last_news_id = generate_send_list(config, last_news_id)

            logger.info(f"Цикл завершен. Следующий запуск через {interval_minutes} минут.")
            logger.info("Ожидание...\n")

            # Ждем указанное в конфиге количество минут
            time.sleep(interval_minutes * 60)

    except KeyboardInterrupt:
        logger.info("Программа остановлена пользователем (Ctrl+C). Выход.")
    except Exception as e:
        logger.error(f"Критическая ошибка в планировщике: {e}", exc_info=True)


if __name__ == '__main__':
    main()