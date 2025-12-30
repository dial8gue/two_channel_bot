"""
Database connection management for SQLite.
"""
import aiosqlite
import logging
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages SQLite database connection and initialization."""
    
    def __init__(self, db_path: str):
        """
        Initialize database connection manager.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
        
    async def init_db(self) -> None:
        """
        Initialize database by creating tables and indexes if they don't exist.
        """
        # Ensure directory exists
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        conn = await self.get_connection()
        
        try:
            # Create messages table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    text TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    reactions TEXT,
                    reply_to_message_id INTEGER,
                    UNIQUE(message_id, chat_id)
                )
            """)
            
            # Create indexes for messages table
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp 
                ON messages(timestamp)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_chat_id 
                ON messages(chat_id)
            """)
            
            # Create config table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            
            # Create cache table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    expires_at DATETIME NOT NULL
                )
            """)
            
            # Create index for cache expiration
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_expires 
                ON cache(expires_at)
            """)
            
            # Create debounce table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS debounce (
                    operation TEXT PRIMARY KEY,
                    last_execution DATETIME NOT NULL
                )
            """)
            
            await conn.commit()
            logger.info(f"Database initialized successfully at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def get_connection(self) -> aiosqlite.Connection:
        """
        Get or create database connection.
        
        Returns:
            Active database connection
        """
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
            # Enable foreign keys and set row factory
            await self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.row_factory = aiosqlite.Row
            
        return self._connection
    
    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Database connection closed")
