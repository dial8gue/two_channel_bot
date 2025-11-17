"""Скрипт для проверки состояния базы данных."""
import sqlite3
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import Config


def check_database():
    """Проверка состояния БД."""
    # Загрузка конфигурации
    try:
        config = Config.from_env()
        db_path = config.db_path
    except Exception as e:
        print(f"Ошибка загрузки конфигурации: {e}")
        print("Используется путь по умолчанию: /app/data/bot.db")
        db_path = "/app/data/bot.db"
    
    # Проверка существования БД
    if not Path(db_path).exists():
        print(f"❌ База данных не найдена: {db_path}")
        print("\nСоздайте БД, запустив бота:")
        print("  python -m bot.main")
        return
    
    print(f"✅ База данных найдена: {db_path}\n")
    
    # Подключение к БД
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Проверка таблиц
    cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
    tables = [row[0] for row in cursor.fetchall()]
    print(f"📋 Таблицы в БД: {', '.join(tables)}\n")
    
    # Проверка количества записей
    cursor.execute('SELECT COUNT(*) FROM messages')
    messages_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM cache WHERE expires_at > datetime("now")')
    cache_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM config')
    config_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM debounce')
    debounce_count = cursor.fetchone()[0]
    
    print("📊 Статистика:")
    print(f"  Сообщений: {messages_count}")
    print(f"  Активных записей кеша: {cache_count}")
    print(f"  Настроек: {config_count}")
    print(f"  Debounce записей: {debounce_count}")
    print()
    
    # Если есть сообщения, показать последние
    if messages_count > 0:
        cursor.execute('''
            SELECT message_id, chat_id, username, 
                   substr(text, 1, 40) as text_preview, 
                   timestamp 
            FROM messages 
            ORDER BY timestamp DESC 
            LIMIT 5
        ''')
        print("📝 Последние сообщения:")
        for row in cursor.fetchall():
            print(f"  [{row[4]}] {row[2]}: {row[3]}...")
        print()
    else:
        print("ℹ️  В БД нет сообщений")
        print("\nВозможные причины:")
        print("  1. Бот не запущен")
        print("  2. Бот не добавлен в групповой чат")
        print("  3. Бот не имеет прав на чтение сообщений")
        print("  4. В группе не было сообщений с момента запуска бота")
        print("\nПроверьте:")
        print("  - Бот добавлен в группу: ✓")
        print("  - Privacy mode отключен в @BotFather: ✓")
        print("  - Бот запущен: python -m bot.main")
        print()
    
    # Если есть кеш, показать записи
    if cache_count > 0:
        cursor.execute('''
            SELECT substr(key, 1, 50) as key_preview, 
                   created_at, expires_at 
            FROM cache 
            WHERE expires_at > datetime("now")
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        print("💾 Активные записи кеша:")
        for row in cursor.fetchall():
            print(f"  {row[0]}...")
            print(f"    Создан: {row[1]}, Истекает: {row[2]}")
        print()
    
    # Показать настройки
    if config_count > 0:
        cursor.execute('SELECT key, value FROM config')
        print("⚙️  Настройки:")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]}")
        print()
    
    conn.close()


if __name__ == "__main__":
    check_database()
