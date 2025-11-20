"""
Repository layer for database operations.
"""
import logging
from datetime import datetime
from typing import List, Optional

from database.connection import DatabaseConnection
from database.models import MessageModel, ConfigModel, CacheModel, DebounceModel


logger = logging.getLogger(__name__)


class MessageRepository:
    """Repository for message-related database operations."""
    
    def __init__(self, db_connection: DatabaseConnection):
        """
        Initialize message repository.
        
        Args:
            db_connection: Database connection manager
        """
        self.db_connection = db_connection
    
    async def create(self, message: MessageModel) -> int:
        """
        Insert a new message into the database.
        
        Args:
            message: Message model to insert
            
        Returns:
            ID of the inserted message
        """
        conn = await self.db_connection.get_connection()
        
        try:
            logger.debug(
                "Attempting to save message to database",
                extra={
                    "message_id": message.message_id,
                    "chat_id": message.chat_id,
                    "user_id": message.user_id,
                    "username": message.username,
                    "text_length": len(message.text)
                }
            )
            
            cursor = await conn.execute(
                """
                INSERT INTO messages 
                (message_id, chat_id, user_id, username, text, timestamp, reactions, reply_to_message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id, chat_id) DO UPDATE SET
                    text = excluded.text,
                    reactions = excluded.reactions
                """,
                (
                    message.message_id,
                    message.chat_id,
                    message.user_id,
                    message.username,
                    message.text,
                    message.timestamp,
                    message.reactions_to_json(),
                    message.reply_to_message_id
                )
            )
            await conn.commit()
            
            message_id = cursor.lastrowid
            logger.debug(
                "Message saved to database successfully",
                extra={
                    "db_id": message_id,
                    "message_id": message.message_id,
                    "chat_id": message.chat_id
                }
            )
            return message_id
            
        except Exception as e:
            logger.error(
                f"Failed to create message: {e}",
                extra={
                    "message_id": message.message_id,
                    "chat_id": message.chat_id,
                    "user_id": message.user_id
                },
                exc_info=True
            )
            await conn.rollback()
            raise
    
    async def update_reactions(self, message_id: int, chat_id: int, reactions: dict) -> None:
        """
        Update reactions for a specific message.
        
        Args:
            message_id: Telegram message ID
            chat_id: Telegram chat ID
            reactions: Dictionary of reactions
        """
        conn = await self.db_connection.get_connection()
        
        try:
            # Create a temporary MessageModel to use serialization
            temp_model = MessageModel(
                message_id=message_id,
                chat_id=chat_id,
                user_id=0,
                username="",
                text="",
                timestamp=datetime.now(),
                reactions=reactions
            )
            
            await conn.execute(
                """
                UPDATE messages 
                SET reactions = ?
                WHERE message_id = ? AND chat_id = ?
                """,
                (temp_model.reactions_to_json(), message_id, chat_id)
            )
            await conn.commit()
            logger.debug(f"Reactions updated for message {message_id}")
            
        except Exception as e:
            logger.error(
                f"Failed to update reactions: {e}",
                extra={
                    "message_id": message_id,
                    "chat_id": chat_id
                },
                exc_info=True
            )
            await conn.rollback()
            raise
    
    async def get_by_period(self, start_time: datetime, chat_id: Optional[int] = None) -> List[MessageModel]:
        """
        Get messages from a specific time period.
        
        Args:
            start_time: Start of the time period
            chat_id: Optional chat ID to filter by
            
        Returns:
            List of message models
        """
        conn = await self.db_connection.get_connection()
        
        try:
            if chat_id:
                cursor = await conn.execute(
                    """
                    SELECT id, message_id, chat_id, user_id, username, text, 
                           timestamp, reactions, reply_to_message_id
                    FROM messages
                    WHERE timestamp >= ? AND chat_id = ?
                    ORDER BY timestamp ASC
                    """,
                    (start_time, chat_id)
                )
            else:
                cursor = await conn.execute(
                    """
                    SELECT id, message_id, chat_id, user_id, username, text, 
                           timestamp, reactions, reply_to_message_id
                    FROM messages
                    WHERE timestamp >= ?
                    ORDER BY timestamp ASC
                    """,
                    (start_time,)
                )
            
            rows = await cursor.fetchall()
            messages = []
            
            for row in rows:
                message = MessageModel(
                    id=row['id'],
                    message_id=row['message_id'],
                    chat_id=row['chat_id'],
                    user_id=row['user_id'],
                    username=row['username'],
                    text=row['text'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    reactions=MessageModel.reactions_from_json(row['reactions']),
                    reply_to_message_id=row['reply_to_message_id']
                )
                messages.append(message)
            
            logger.debug(f"Retrieved {len(messages)} messages from period")
            return messages
            
        except Exception as e:
            logger.error(
                f"Failed to get messages by period: {e}",
                extra={
                    "start_time": start_time.isoformat(),
                    "chat_id": chat_id
                },
                exc_info=True
            )
            raise
    
    async def delete_older_than(self, timestamp: datetime) -> int:
        """
        Delete messages older than specified timestamp.
        
        Args:
            timestamp: Cutoff timestamp
            
        Returns:
            Number of deleted messages
        """
        conn = await self.db_connection.get_connection()
        
        try:
            cursor = await conn.execute(
                "DELETE FROM messages WHERE timestamp < ?",
                (timestamp,)
            )
            await conn.commit()
            
            deleted_count = cursor.rowcount
            logger.info(f"Deleted {deleted_count} old messages")
            return deleted_count
            
        except Exception as e:
            logger.error(
                f"Failed to delete old messages: {e}",
                extra={
                    "timestamp": timestamp.isoformat()
                },
                exc_info=True
            )
            await conn.rollback()
            raise
    
    async def clear_all(self) -> None:
        """Delete all messages from the database."""
        conn = await self.db_connection.get_connection()
        
        try:
            await conn.execute("DELETE FROM messages")
            await conn.commit()
            logger.info("All messages cleared from database")
            
        except Exception as e:
            logger.error(f"Failed to clear all messages: {e}", exc_info=True)
            await conn.rollback()
            raise
    
    async def count(self) -> int:
        """
        Get total count of messages.
        
        Returns:
            Total number of messages
        """
        conn = await self.db_connection.get_connection()
        
        try:
            cursor = await conn.execute("SELECT COUNT(*) as count FROM messages")
            row = await cursor.fetchone()
            return row['count'] if row else 0
            
        except Exception as e:
            logger.error(f"Failed to count messages: {e}", exc_info=True)
            raise
    
    async def get_distinct_chats(self) -> List[dict]:
        """
        Get list of distinct chats with message counts.
        
        Returns:
            List of dicts with chat_id and message_count
        """
        conn = await self.db_connection.get_connection()
        
        try:
            cursor = await conn.execute(
                """
                SELECT chat_id, COUNT(*) as message_count
                FROM messages
                GROUP BY chat_id
                ORDER BY message_count DESC
                """
            )
            rows = await cursor.fetchall()
            
            chats = [
                {"chat_id": row["chat_id"], "message_count": row["message_count"]}
                for row in rows
            ]
            
            logger.debug(f"Found {len(chats)} distinct chats")
            return chats
            
        except Exception as e:
            logger.error(f"Failed to get distinct chats: {e}", exc_info=True)
            raise


class ConfigRepository:
    """Repository for configuration-related database operations."""
    
    def __init__(self, db_connection: DatabaseConnection):
        """
        Initialize config repository.
        
        Args:
            db_connection: Database connection manager
        """
        self.db_connection = db_connection
    
    async def get(self, key: str) -> Optional[str]:
        """
        Get configuration value by key.
        
        Args:
            key: Configuration key
            
        Returns:
            Configuration value or None if not found
        """
        conn = await self.db_connection.get_connection()
        
        try:
            cursor = await conn.execute(
                "SELECT value FROM config WHERE key = ?",
                (key,)
            )
            row = await cursor.fetchone()
            
            if row:
                logger.debug(f"Config retrieved: {key}")
                return row['value']
            return None
            
        except Exception as e:
            logger.error(f"Failed to get config: {e}", exc_info=True)
            raise
    
    async def set(self, key: str, value: str) -> None:
        """
        Set configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        conn = await self.db_connection.get_connection()
        
        try:
            await conn.execute(
                """
                INSERT INTO config (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value)
            )
            await conn.commit()
            logger.debug(f"Config set: {key}")
            
        except Exception as e:
            logger.error(f"Failed to set config: {e}", exc_info=True)
            await conn.rollback()
            raise
    
    async def delete(self, key: str) -> None:
        """
        Delete configuration by key.
        
        Args:
            key: Configuration key
        """
        conn = await self.db_connection.get_connection()
        
        try:
            await conn.execute("DELETE FROM config WHERE key = ?", (key,))
            await conn.commit()
            logger.debug(f"Config deleted: {key}")
            
        except Exception as e:
            logger.error(f"Failed to delete config: {e}", exc_info=True)
            await conn.rollback()
            raise


class CacheRepository:
    """Repository for cache-related database operations."""
    
    def __init__(self, db_connection: DatabaseConnection):
        """
        Initialize cache repository.
        
        Args:
            db_connection: Database connection manager
        """
        self.db_connection = db_connection
    
    async def get(self, key: str) -> Optional[str]:
        """
        Get cached value by key, checking expiration.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
        """
        conn = await self.db_connection.get_connection()
        
        try:
            cursor = await conn.execute(
                """
                SELECT value, expires_at FROM cache 
                WHERE key = ? AND expires_at > ?
                """,
                (key, datetime.now())
            )
            row = await cursor.fetchone()
            
            if row:
                logger.debug(f"Cache hit: {key}")
                return row['value']
            
            logger.debug(f"Cache miss: {key}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cache: {e}", exc_info=True)
            raise
    
    async def set(self, key: str, value: str, ttl_minutes: int) -> None:
        """
        Set cached value with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_minutes: Time to live in minutes
        """
        conn = await self.db_connection.get_connection()
        
        try:
            from datetime import timedelta
            
            created_at = datetime.now()
            expires_at = created_at + timedelta(minutes=ttl_minutes)
            
            await conn.execute(
                """
                INSERT INTO cache (key, value, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                """,
                (key, value, created_at, expires_at)
            )
            await conn.commit()
            logger.debug(f"Cache set: {key} (TTL: {ttl_minutes}m)")
            
        except Exception as e:
            logger.error(f"Failed to set cache: {e}", exc_info=True)
            await conn.rollback()
            raise
    
    async def cleanup_expired(self) -> None:
        """Delete expired cache entries."""
        conn = await self.db_connection.get_connection()
        
        try:
            cursor = await conn.execute(
                "DELETE FROM cache WHERE expires_at <= ?",
                (datetime.now(),)
            )
            await conn.commit()
            
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired cache entries")
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired cache: {e}", exc_info=True)
            await conn.rollback()
            raise
    
    async def clear_all(self) -> None:
        """Delete all cache entries."""
        conn = await self.db_connection.get_connection()
        
        try:
            await conn.execute("DELETE FROM cache")
            await conn.commit()
            logger.info("All cache entries cleared")
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}", exc_info=True)
            await conn.rollback()
            raise
    
    async def count(self) -> int:
        """
        Get count of non-expired cache entries.
        
        Returns:
            Number of cache entries that haven't expired
        """
        conn = await self.db_connection.get_connection()
        
        try:
            cursor = await conn.execute(
                "SELECT COUNT(*) as count FROM cache WHERE expires_at > ?",
                (datetime.now(),)
            )
            row = await cursor.fetchone()
            count = row['count'] if row else 0
            logger.debug(f"Cache count: {count}")
            return count
            
        except Exception as e:
            logger.error(f"Failed to count cache entries: {e}")
            return 0


class DebounceRepository:
    """Repository for debounce-related database operations."""
    
    def __init__(self, db_connection: DatabaseConnection):
        """
        Initialize debounce repository.
        
        Args:
            db_connection: Database connection manager
        """
        self.db_connection = db_connection
    
    async def get_last_execution(self, operation: str) -> Optional[datetime]:
        """
        Get last execution time for an operation.
        
        Args:
            operation: Operation name
            
        Returns:
            Last execution datetime or None if not found
        """
        conn = await self.db_connection.get_connection()
        
        try:
            cursor = await conn.execute(
                "SELECT last_execution FROM debounce WHERE operation = ?",
                (operation,)
            )
            row = await cursor.fetchone()
            
            if row:
                return datetime.fromisoformat(row['last_execution'])
            return None
            
        except Exception as e:
            logger.error(f"Failed to get last execution: {e}", exc_info=True)
            raise
    
    async def update_execution(self, operation: str) -> None:
        """
        Update execution time for an operation.
        
        Args:
            operation: Operation name
        """
        conn = await self.db_connection.get_connection()
        
        try:
            now = datetime.now()
            
            await conn.execute(
                """
                INSERT INTO debounce (operation, last_execution)
                VALUES (?, ?)
                ON CONFLICT(operation) DO UPDATE SET last_execution = excluded.last_execution
                """,
                (operation, now)
            )
            await conn.commit()
            logger.debug(f"Debounce updated for operation: {operation}")
            
        except Exception as e:
            logger.error(f"Failed to update execution: {e}", exc_info=True)
            await conn.rollback()
            raise
