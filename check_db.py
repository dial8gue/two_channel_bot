"""
Проверка состояния БД.

Этот скрипт перенесен в scripts/check_database.py
Используйте: python scripts/check_database.py
"""
import sys
from pathlib import Path

# Импортируем и запускаем новый скрипт
sys.path.insert(0, str(Path(__file__).parent))
from scripts.check_database import check_database

if __name__ == "__main__":
    check_database()
