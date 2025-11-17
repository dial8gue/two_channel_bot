"""
Unit tests for CacheManager.
"""
import pytest
from unittest.mock import AsyncMock

from utils.cache_manager import CacheManager


@pytest.fixture
def mock_cache_repository():
    """Mock cache repository."""
    return AsyncMock()


@pytest.fixture
def cache_manager(mock_cache_repository):
    """Create cache manager with mocked repository."""
    return CacheManager(cache_repository=mock_cache_repository)


@pytest.mark.unit
class TestCacheManager:
    """Test cases for CacheManager."""
    
    @pytest.mark.asyncio
    async def test_get_cache_hit(self, cache_manager, mock_cache_repository):
        """Test getting cached value when it exists."""
        # Arrange
        mock_cache_repository.get.return_value = "cached_value"
        
        # Act
        result = await cache_manager.get("test_key")
        
        # Assert
        assert result == "cached_value"
        mock_cache_repository.get.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache_manager, mock_cache_repository):
        """Test getting cached value when it doesn't exist."""
        # Arrange
        mock_cache_repository.get.return_value = None
        
        # Act
        result = await cache_manager.get("test_key")
        
        # Assert
        assert result is None
        mock_cache_repository.get.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_set_cache(self, cache_manager, mock_cache_repository):
        """Test setting cache value."""
        # Act
        await cache_manager.set("test_key", "test_value", 60)
        
        # Assert
        mock_cache_repository.set.assert_called_once_with(
            "test_key",
            "test_value",
            60
        )
    
    @pytest.mark.asyncio
    async def test_cleanup(self, cache_manager, mock_cache_repository):
        """Test cache cleanup."""
        # Act
        await cache_manager.cleanup()
        
        # Assert
        mock_cache_repository.cleanup_expired.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_handles_exception(self, cache_manager, mock_cache_repository):
        """Test get handles repository exceptions gracefully."""
        # Arrange
        mock_cache_repository.get.side_effect = Exception("Database error")
        
        # Act
        result = await cache_manager.get("test_key")
        
        # Assert
        assert result is None
