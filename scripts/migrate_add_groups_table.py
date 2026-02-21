"""
Migration script to add groups table to existing database.

Run this if you have an existing database and need to add the groups table.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import DatabaseConnection
from config.settings import Config


async def migrate():
    """Add groups table to database."""
    print("Loading configuration...")
    config = Config.from_env()
    
    print(f"Connecting to database: {config.db_path}")
    db = DatabaseConnection(config.db_path)
    conn = await db.get_connection()
    
    try:
        # Check if groups table already exists
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='groups'"
        )
        exists = await cursor.fetchone()
        
        if exists:
            print("✅ Groups table already exists, no migration needed.")
            return
        
        print("Creating groups table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                chat_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                added_at DATETIME NOT NULL
            )
        """)
        await conn.commit()
        
        print("✅ Groups table created successfully!")
        print("\nYou can now use /manage_groups command to manage your groups.")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        await db.close()


if __name__ == "__main__":
    print("=" * 50)
    print("Database Migration: Add Groups Table")
    print("=" * 50)
    print()
    
    try:
        asyncio.run(migrate())
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user")
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        sys.exit(1)
