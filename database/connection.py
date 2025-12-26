"""
Database connection management for SQLite.
"""
import asyncio
import aiosqlite
import logging
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager


logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages SQLite database connection with WAL mode and concurrency control."""
    
    def __init__(self, db_path: str, max_connections: int = 5):
        """
        Initialize database connection manager.
        
        Args:
            db_path: Path to the SQLite database file
            max_connections: Maximum concurrent database operations
        """
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_connections)
        self._is_initialized = False
        
    async def init_db(self) -> None:
        """
        Initialize database by creating tables and indexes if they don't exist.
        """
        # Ensure directory exists
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        conn = await self.get_connection()
        
        try:
            # Enable WAL mode for better concurrency
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA cache_size=10000")
            await conn.execute("PRAGMA temp_store=MEMORY")
            
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
            self._is_initialized = True
            logger.info(f"Database initialized successfully at {self.db_path} (WAL mode enabled)")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def get_connection(self) -> aiosqlite.Connection:
        """
        Get or create database connection with automatic reconnection.
        
        Returns:
            Active database connection
        """
        async with self._lock:
            # Check if connection is alive
            if self._connection is not None:
                try:
                    # Test connection with a simple query
                    await self._connection.execute("SELECT 1")
                except Exception as e:
                    logger.warning(f"Connection lost, reconnecting: {e}")
                    self._connection = None
            
            if self._connection is None:
                self._connection = await aiosqlite.connect(
                    self.db_path,
                    timeout=30.0  # Wait up to 30 seconds for locks
                )
                # Enable foreign keys and set row factory
                await self._connection.execute("PRAGMA foreign_keys = ON")
                self._connection.row_factory = aiosqlite.Row
                logger.debug("Database connection established")
                
        return self._connection
    
    @asynccontextmanager
    async def acquire(self):
        """
        Context manager for acquiring a connection with concurrency control.
        
        Usage:
            async with db_connection.acquire() as conn:
                await conn.execute(...)
        
        Yields:
            Database connection
        """
        async with self._semaphore:
            conn = await self.get_connection()
            try:
                yield conn
            except Exception as e:
                logger.error(f"Database operation failed: {e}")
                raise
    
    async def close(self) -> None:
        """Close database connection."""
        async with self._lock:
            if self._connection:
                await self._connection.close()
                self._connection = None
                logger.info("Database connection closed")
