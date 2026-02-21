"""
Script to sync groups from messages table to groups table.

Finds all unique chat_ids from messages and registers them as groups.
Useful after upgrading to the version with group management.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aiogram import Bot
from config.settings import Config
from database.connection import DatabaseConnection
from database.models import GroupModel
from database.repository import GroupRepository
from datetime import datetime


async def sync_groups():
    """Sync groups from messages table to groups table."""
    config = Config.from_env()
    bot = Bot(token=config.bot_token)
    
    db = DatabaseConnection(config.db_path)
    await db.init_db()
    
    group_repo = GroupRepository(db)
    conn = await db.get_connection()
    
    try:
        # Get all unique chat_ids from messages
        cursor = await conn.execute(
            "SELECT DISTINCT chat_id FROM messages WHERE chat_id < 0"
        )
        rows = await cursor.fetchall()
        
        if not rows:
            print("❌ Нет групп в таблице messages.")
            return
        
        print(f"📋 Найдено {len(rows)} уникальных групп в messages.\n")
        
        synced = 0
        skipped = 0
        
        for row in rows:
            chat_id = row['chat_id']
            
            # Check if already registered
            existing = await group_repo.get(chat_id)
            if existing:
                print(f"  ⏭️  {existing.title} ({chat_id}) — уже зарегистрирована")
                skipped += 1
                continue
            
            # Try to get chat info from Telegram
            try:
                chat_info = await bot.get_chat(chat_id)
                title = chat_info.title or f"Group {chat_id}"
            except Exception as e:
                title = f"Group {chat_id}"
                print(f"  ⚠️  Не удалось получить название для {chat_id}: {e}")
            
            # Register group
            group = GroupModel(
                chat_id=chat_id,
                title=title,
                is_enabled=True,
                added_at=datetime.now()
            )
            await group_repo.add_or_update(group)
            print(f"  ✅ {title} ({chat_id}) — зарегистрирована")
            synced += 1
        
        print(f"\n📊 Итого: {synced} добавлено, {skipped} уже были.")
        
    finally:
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    print("=" * 50)
    print("Синхронизация групп из messages в groups")
    print("=" * 50)
    print()
    
    try:
        asyncio.run(sync_groups())
    except KeyboardInterrupt:
        print("\n\nОтменено.")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)
