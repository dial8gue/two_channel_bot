"""
Admin service for administrative operations.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from database.repository import MessageRepository, ConfigRepository, CacheRepository, GroupRepository


logger = logging.getLogger(__name__)


class AdminService:
    """Service for administrative operations and configuration management."""
    
    # Configuration keys
    CONFIG_STORAGE_PERIOD = "storage_period_hours"
    CONFIG_ANALYSIS_PERIOD = "analysis_period_hours"
    CONFIG_COLLECTION_ENABLED = "collection_enabled"
    CONFIG_OPENAI_MODEL = "openai_model"
    CONFIG_VISION_ENABLED = "vision_enabled"
    
    def __init__(
        self,
        message_repository: MessageRepository,
        config_repository: ConfigRepository,
        cache_repository: CacheRepository,
        group_repository: GroupRepository,
        timezone: Optional[str] = None
    ):
        """
        Initialize admin service.
        
        Args:
            message_repository: Repository for message operations
            config_repository: Repository for configuration operations
            cache_repository: Repository for cache operations
            group_repository: Repository for group operations
            timezone: IANA timezone identifier for timestamp formatting (optional)
        """
        self.message_repository = message_repository
        self.config_repository = config_repository
        self.cache_repository = cache_repository
        self.group_repository = group_repository
        self.timezone = timezone
    
    async def clear_database(self) -> None:
        """
        Clear all messages from the database.
        
        This operation also clears the cache to ensure consistency.
        """
        try:
            logger.info("Starting database clear operation")
            
            # Clear all messages
            await self.message_repository.clear_all()
            
            # Clear cache as well
            await self.cache_repository.clear_all()
            
            logger.info("Database cleared successfully")
            
        except Exception as e:
            logger.error(f"Failed to clear database: {e}", exc_info=True)
            raise
    
    async def set_storage_period(self, hours: int) -> None:
        """
        Set the storage period for messages.
        
        Args:
            hours: Number of hours to store messages
            
        Raises:
            ValueError: If hours is not positive
        """
        try:
            if hours <= 0:
                raise ValueError("Storage period must be positive")
            
            await self.config_repository.set(
                key=self.CONFIG_STORAGE_PERIOD,
                value=str(hours)
            )
            
            logger.info(
                "Storage period updated",
                extra={"storage_period_hours": hours}
            )
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to set storage period: {e}",
                extra={"hours": hours},
                exc_info=True
            )
            raise
    
    async def get_storage_period(self) -> Optional[int]:
        """
        Get the current storage period setting.
        
        Returns:
            Storage period in hours, or None if not set
        """
        try:
            value = await self.config_repository.get(self.CONFIG_STORAGE_PERIOD)
            if value:
                return int(value)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get storage period: {e}", exc_info=True)
            return None
    
    async def set_analysis_period(self, hours: int) -> None:
        """
        Set the default analysis period.
        
        Args:
            hours: Number of hours for analysis period
            
        Raises:
            ValueError: If hours is not positive
        """
        try:
            if hours <= 0:
                raise ValueError("Analysis period must be positive")
            
            await self.config_repository.set(
                key=self.CONFIG_ANALYSIS_PERIOD,
                value=str(hours)
            )
            
            logger.info(
                "Analysis period updated",
                extra={"analysis_period_hours": hours}
            )
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to set analysis period: {e}",
                extra={"hours": hours},
                exc_info=True
            )
            raise
    
    async def get_analysis_period(self) -> Optional[int]:
        """
        Get the current analysis period setting.
        
        Returns:
            Analysis period in hours, or None if not set
        """
        try:
            value = await self.config_repository.get(self.CONFIG_ANALYSIS_PERIOD)
            if value:
                return int(value)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get analysis period: {e}", exc_info=True)
            return None
    
    async def toggle_collection(self, enabled: bool) -> None:
        """
        Enable or disable message collection.
        
        Args:
            enabled: True to enable collection, False to disable
        """
        try:
            await self.config_repository.set(
                key=self.CONFIG_COLLECTION_ENABLED,
                value="true" if enabled else "false"
            )
            
            status = "enabled" if enabled else "disabled"
            logger.info(
                f"Message collection {status}",
                extra={"collection_enabled": enabled}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to toggle collection: {e}",
                extra={"enabled": enabled},
                exc_info=True
            )
            raise
    
    async def is_collection_enabled(self) -> bool:
        """
        Check if message collection is enabled.
        
        Returns:
            True if collection is enabled, False otherwise (defaults to True)
        """
        try:
            value = await self.config_repository.get(self.CONFIG_COLLECTION_ENABLED)
            if value is None:
                # Default to enabled if not set
                return True
            return value.lower() == "true"
            
        except Exception as e:
            logger.error(f"Failed to check collection status: {e}", exc_info=True)
            # Default to enabled on error
            return True
    
    async def set_openai_model(self, model: str) -> None:
        """
        Set the OpenAI model to use for analysis.
        
        Args:
            model: Model name (e.g., 'gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo')
            
        Raises:
            ValueError: If model name is empty
        """
        try:
            if not model or not model.strip():
                raise ValueError("Model name cannot be empty")
            
            model = model.strip()
            
            await self.config_repository.set(
                key=self.CONFIG_OPENAI_MODEL,
                value=model
            )
            
            logger.info(
                "OpenAI model updated",
                extra={"openai_model": model}
            )
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to set OpenAI model: {e}",
                extra={"model": model},
                exc_info=True
            )
            raise
    
    async def get_openai_model(self) -> Optional[str]:
        """
        Get the current OpenAI model setting.
        
        Returns:
            Model name, or None if not set (uses default from config)
        """
        try:
            value = await self.config_repository.get(self.CONFIG_OPENAI_MODEL)
            return value if value else None
            
        except Exception as e:
            logger.error(f"Failed to get OpenAI model: {e}", exc_info=True)
            return None
    
    async def toggle_vision(self, enabled: bool) -> None:
        """
        Enable or disable image recognition (vision).
        
        Args:
            enabled: True to enable vision, False to disable
        """
        try:
            await self.config_repository.set(
                key=self.CONFIG_VISION_ENABLED,
                value="true" if enabled else "false"
            )
            
            status = "enabled" if enabled else "disabled"
            logger.info(
                f"Vision {status}",
                extra={"vision_enabled": enabled}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to toggle vision: {e}",
                extra={"enabled": enabled},
                exc_info=True
            )
            raise
    
    async def is_vision_enabled(self) -> bool:
        """
        Check if image recognition (vision) is enabled.
        
        Returns:
            True if vision is enabled, False otherwise (defaults to True)
        """
        try:
            value = await self.config_repository.get(self.CONFIG_VISION_ENABLED)
            if value is None:
                return True
            return value.lower() == "true"
            
        except Exception as e:
            logger.error(f"Failed to check vision status: {e}", exc_info=True)
            return True
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary containing various statistics:
                - total_messages: Total number of messages
                - oldest_message: Timestamp of oldest message
                - newest_message: Timestamp of newest message
                - cache_entries: Number of cache entries
                - storage_period_hours: Current storage period setting
                - analysis_period_hours: Current analysis period setting
                - collection_enabled: Whether collection is enabled
        """
        try:
            logger.info("Gathering database statistics")
            
            stats = {}
            
            # Get message count
            stats['total_messages'] = await self.message_repository.count()
            
            # Get oldest and newest message timestamps
            if stats['total_messages'] > 0:
                # Get all messages to find oldest and newest
                # This is not optimal for large datasets, but works for now
                from datetime import timedelta
                from utils.timezone_helper import format_datetime
                
                all_messages = await self.message_repository.get_by_period(
                    start_time=datetime.now() - timedelta(days=365 * 10)  # 10 years back
                )
                
                if all_messages:
                    timestamps = [msg.timestamp for msg in all_messages]
                    oldest = min(timestamps)
                    newest = max(timestamps)
                    
                    # Format with timezone
                    stats['oldest_message'] = format_datetime(oldest, self.timezone)
                    stats['newest_message'] = format_datetime(newest, self.timezone)
                else:
                    stats['oldest_message'] = None
                    stats['newest_message'] = None
            else:
                stats['oldest_message'] = None
                stats['newest_message'] = None
            
            # Get cache entry count (non-expired entries)
            try:
                cache_count = await self.cache_repository.count()
                stats['cache_entries'] = cache_count
            except Exception as e:
                logger.error(f"Failed to count cache entries: {e}", exc_info=True)
                stats['cache_entries'] = "Error"
            
            # Get configuration settings
            storage_period = await self.get_storage_period()
            stats['storage_period_hours'] = storage_period if storage_period else "Not set"
            
            analysis_period = await self.get_analysis_period()
            stats['analysis_period_hours'] = analysis_period if analysis_period else "Not set"
            
            stats['collection_enabled'] = await self.is_collection_enabled()
            
            # Get OpenAI model setting
            openai_model = await self.get_openai_model()
            stats['openai_model'] = openai_model if openai_model else "Default (from env)"
            
            # Get vision setting
            stats['vision_enabled'] = await self.is_vision_enabled()
            
            logger.info(
                "Statistics gathered successfully",
                extra={"total_messages": stats['total_messages']}
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}", exc_info=True)
            raise

    
    async def get_all_groups(self) -> list:
        """
        Get all groups from database.
        
        Returns:
            List of group models
        """
        try:
            groups = await self.group_repository.get_all()
            logger.info(f"Retrieved {len(groups)} groups")
            return groups
            
        except Exception as e:
            logger.error(f"Failed to get all groups: {e}", exc_info=True)
            raise
    
    async def add_or_update_group(self, chat_id: int, title: str) -> None:
        """
        Add or update group information.
        
        Args:
            chat_id: Telegram chat ID
            title: Group title
        """
        try:
            from database.models import GroupModel
            
            group = GroupModel(
                chat_id=chat_id,
                title=title,
                is_enabled=True,
                added_at=datetime.now()
            )
            
            await self.group_repository.add_or_update(group)
            logger.info(f"Group {chat_id} ({title}) added/updated")
            
        except Exception as e:
            logger.error(f"Failed to add/update group: {e}", exc_info=True)
            raise
    
    async def toggle_group(self, chat_id: int, enabled: bool) -> None:
        """
        Enable or disable a group.
        
        Args:
            chat_id: Telegram chat ID
            enabled: True to enable, False to disable
        """
        try:
            await self.group_repository.set_enabled(chat_id, enabled)
            status = "enabled" if enabled else "disabled"
            logger.info(f"Group {chat_id} {status}")
            
        except Exception as e:
            logger.error(f"Failed to toggle group: {e}", exc_info=True)
            raise
    
    async def is_group_enabled(self, chat_id: int) -> bool:
        """
        Check if group is enabled.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            True if enabled, False if disabled
        """
        try:
            return await self.group_repository.is_enabled(chat_id)
            
        except Exception as e:
            logger.error(f"Failed to check if group is enabled: {e}", exc_info=True)
            return True
    
    async def remove_group(self, chat_id: int) -> None:
        """
        Remove group from database and clear its messages.
        
        Args:
            chat_id: Telegram chat ID
        """
        try:
            # Clear messages for this group
            deleted_count = await self.message_repository.delete_by_chat_id(chat_id)
            logger.info(f"Deleted {deleted_count} messages for group {chat_id}")
            
            # Remove group record
            await self.group_repository.delete(chat_id)
            logger.info(f"Group {chat_id} removed from database")
            
        except Exception as e:
            logger.error(f"Failed to remove group: {e}", exc_info=True)
            raise
