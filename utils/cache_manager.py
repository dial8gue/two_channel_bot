"""
Cache manager for storing and retrieving analysis results.
"""
import logging
from typing import Optional

from database.repository import CacheRepository


logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching of analysis results to reduce OpenAI API calls."""
    
    def __init__(self, cache_repository: CacheRepository):
        """
        Initialize cache manager.
        
        Args:
            cache_repository: Repository for cache operations
        """
        self.cache_repository = cache_repository
    
    async def get(self, key: str) -> Optional[str]:
        """
        Get cached value by key.
        
        Automatically checks TTL expiration - expired entries return None.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
        """
        try:
            value = await self.cache_repository.get(key)
            
            if value:
                logger.info(f"Cache hit for key: {key[:50]}...")
            else:
                logger.info(f"Cache miss for key: {key[:50]}...")
            
            return value
            
        except Exception as e:
            logger.error(f"Error getting cache for key {key[:50]}...: {e}")
            return None
    
    async def set(self, key: str, value: str, ttl_minutes: int) -> None:
        """
        Set cached value with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_minutes: Time to live in minutes
        """
        try:
            await self.cache_repository.set(key, value, ttl_minutes)
            logger.info(f"Cache set for key: {key[:50]}... (TTL: {ttl_minutes}m)")
            
        except Exception as e:
            logger.error(f"Error setting cache for key {key[:50]}...: {e}")
            raise
    
    async def cleanup(self) -> None:
        """
        Clean up expired cache entries.
        
        This should be called periodically to remove stale data.
        """
        try:
            await self.cache_repository.cleanup_expired()
            logger.debug("Cache cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")
            raise
