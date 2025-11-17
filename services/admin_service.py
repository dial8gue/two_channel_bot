"""
Admin service for administrative operations.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from database.repository import MessageRepository, ConfigRepository, CacheRepository


logger = logging.getLogger(__name__)


class AdminService:
    """Service for administrative operations and configuration management."""
    
    # Configuration keys
    CONFIG_STORAGE_PERIOD = "storage_period_hours"
    CONFIG_ANALYSIS_PERIOD = "analysis_period_hours"
    CONFIG_COLLECTION_ENABLED = "collection_enabled"
    
    def __init__(
        self,
        message_repository: MessageRepository,
        config_repository: ConfigRepository,
        cache_repository: CacheRepository
    ):
        """
        Initialize admin service.
        
        Args:
            message_repository: Repository for message operations
            config_repository: Repository for configuration operations
            cache_repository: Repository for cache operations
        """
        self.message_repository = message_repository
        self.config_repository = config_repository
        self.cache_repository = cache_repository
    
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
                all_messages = await self.message_repository.get_by_period(
                    start_time=datetime.now() - timedelta(days=365 * 10)  # 10 years back
                )
                
                if all_messages:
                    timestamps = [msg.timestamp for msg in all_messages]
                    stats['oldest_message'] = min(timestamps).strftime("%Y-%m-%d %H:%M:%S")
                    stats['newest_message'] = max(timestamps).strftime("%Y-%m-%d %H:%M:%S")
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
            
            logger.info(
                "Statistics gathered successfully",
                extra={"total_messages": stats['total_messages']}
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}", exc_info=True)
            raise
