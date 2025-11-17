"""
Message service for handling message operations.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from database.repository import MessageRepository, DebounceRepository
from database.models import MessageModel


logger = logging.getLogger(__name__)


class MessageService:
    """Service for managing message storage and retrieval operations."""
    
    # Cleanup operation name for debounce
    CLEANUP_OPERATION = "cleanup_old_messages"
    
    def __init__(
        self,
        message_repository: MessageRepository,
        debounce_repository: DebounceRepository,
        storage_period_hours: int
    ):
        """
        Initialize message service.
        
        Args:
            message_repository: Repository for message operations
            debounce_repository: Repository for debounce operations
            storage_period_hours: Maximum period to store messages in hours
        """
        self.message_repository = message_repository
        self.debounce_repository = debounce_repository
        self.storage_period_hours = storage_period_hours
    
    async def save_message(
        self,
        message_id: int,
        chat_id: int,
        user_id: int,
        username: str,
        text: str,
        timestamp: datetime,
        reactions: Optional[dict] = None,
        reply_to_message_id: Optional[int] = None
    ) -> int:
        """
        Save a message to the database.
        
        Args:
            message_id: Telegram message ID
            chat_id: Telegram chat ID
            user_id: User ID who sent the message
            username: Username of the sender
            text: Message text content
            timestamp: Message timestamp
            reactions: Optional dictionary of reactions
            reply_to_message_id: Optional ID of message being replied to
            
        Returns:
            Database ID of the saved message
        """
        try:
            message = MessageModel(
                message_id=message_id,
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                text=text,
                timestamp=timestamp,
                reactions=reactions or {},
                reply_to_message_id=reply_to_message_id
            )
            
            db_id = await self.message_repository.create(message)
            
            logger.info(
                "Message saved successfully",
                extra={
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "username": username,
                    "db_id": db_id
                }
            )
            
            return db_id
            
        except Exception as e:
            logger.error(
                f"Failed to save message: {e}",
                extra={
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "user_id": user_id
                },
                exc_info=True
            )
            raise
    
    async def update_reactions(
        self,
        message_id: int,
        chat_id: int,
        reactions: dict
    ) -> None:
        """
        Update reactions for a specific message.
        
        Args:
            message_id: Telegram message ID
            chat_id: Telegram chat ID
            reactions: Dictionary of reactions {emoji: count}
        """
        try:
            await self.message_repository.update_reactions(
                message_id=message_id,
                chat_id=chat_id,
                reactions=reactions
            )
            
            logger.info(
                "Reactions updated successfully",
                extra={
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "reaction_count": len(reactions)
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to update reactions: {e}",
                extra={
                    "message_id": message_id,
                    "chat_id": chat_id
                },
                exc_info=True
            )
            raise
    
    async def get_messages_by_period(
        self,
        hours: int,
        chat_id: Optional[int] = None
    ) -> List[MessageModel]:
        """
        Get messages from a specific time period.
        
        Args:
            hours: Number of hours to look back
            chat_id: Optional chat ID to filter by
            
        Returns:
            List of message models from the specified period
        """
        try:
            start_time = datetime.now() - timedelta(hours=hours)
            
            messages = await self.message_repository.get_by_period(
                start_time=start_time,
                chat_id=chat_id
            )
            
            logger.info(
                "Messages retrieved by period",
                extra={
                    "hours": hours,
                    "chat_id": chat_id,
                    "message_count": len(messages),
                    "start_time": start_time.isoformat()
                }
            )
            
            return messages
            
        except Exception as e:
            logger.error(
                f"Failed to get messages by period: {e}",
                extra={
                    "hours": hours,
                    "chat_id": chat_id
                },
                exc_info=True
            )
            raise
    
    async def cleanup_old_messages(self) -> int:
        """
        Delete messages older than the storage period.
        
        This method includes debounce logic to prevent frequent cleanup operations.
        Cleanup will only execute if at least 1 hour has passed since the last cleanup.
        
        Returns:
            Number of messages deleted, or 0 if cleanup was skipped due to debounce
        """
        try:
            # Check if we can execute cleanup (debounce: 1 hour = 3600 seconds)
            last_execution = await self.debounce_repository.get_last_execution(
                self.CLEANUP_OPERATION
            )
            
            if last_execution:
                time_since_last = (datetime.now() - last_execution).total_seconds()
                if time_since_last < 3600:  # Less than 1 hour
                    remaining = 3600 - time_since_last
                    logger.debug(
                        f"Cleanup skipped due to debounce. "
                        f"Wait {remaining:.0f}s more (last cleanup {time_since_last:.0f}s ago)"
                    )
                    return 0
            
            # Calculate cutoff timestamp
            cutoff_time = datetime.now() - timedelta(hours=self.storage_period_hours)
            
            # Perform cleanup
            deleted_count = await self.message_repository.delete_older_than(cutoff_time)
            
            # Update debounce timestamp
            await self.debounce_repository.update_execution(self.CLEANUP_OPERATION)
            
            logger.info(
                "Old messages cleaned up",
                extra={
                    "deleted_count": deleted_count,
                    "storage_period_hours": self.storage_period_hours,
                    "cutoff_time": cutoff_time.isoformat()
                }
            )
            
            return deleted_count
            
        except Exception as e:
            logger.error(
                f"Failed to cleanup old messages: {e}",
                extra={
                    "storage_period_hours": self.storage_period_hours
                },
                exc_info=True
            )
            raise
