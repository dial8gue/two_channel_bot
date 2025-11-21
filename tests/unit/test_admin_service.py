"""
Unit tests for AdminService.
"""
import pytest
from unittest.mock import AsyncMock
from datetime import datetime

from services.admin_service import AdminService
from database.models import MessageModel


@pytest.fixture
def mock_message_repository():
    """Mock message repository."""
    return AsyncMock()


@pytest.fixture
def mock_config_repository():
    """Mock config repository."""
    return AsyncMock()


@pytest.fixture
def mock_cache_repository():
    """Mock cache repository."""
    return AsyncMock()


@pytest.fixture
def admin_service(mock_message_repository, mock_config_repository, mock_cache_repository):
    """Create admin service with mocked dependencies."""
    return AdminService(
        message_repository=mock_message_repository,
        config_repository=mock_config_repository,
        cache_repository=mock_cache_repository
    )


@pytest.mark.unit
class TestAdminService:
    """Test cases for AdminService."""
    
    @pytest.mark.asyncio
    async def test_clear_database(
        self,
        admin_service,
        mock_message_repository,
        mock_cache_repository
    ):
        """Test clearing database."""
        # Act
        await admin_service.clear_database()
        
        # Assert
        mock_message_repository.clear_all.assert_called_once()
        mock_cache_repository.clear_all.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_set_storage_period_valid(
        self,
        admin_service,
        mock_config_repository
    ):
        """Test setting valid storage period."""
        # Act
        await admin_service.set_storage_period(168)
        
        # Assert
        mock_config_repository.set.assert_called_once_with(
            key="storage_period_hours",
            value="168"
        )
    
    @pytest.mark.asyncio
    async def test_set_storage_period_invalid(self, admin_service):
        """Test setting invalid storage period."""
        # Act & Assert
        with pytest.raises(ValueError, match="Storage period must be positive"):
            await admin_service.set_storage_period(0)
        
        with pytest.raises(ValueError, match="Storage period must be positive"):
            await admin_service.set_storage_period(-10)
    
    @pytest.mark.asyncio
    async def test_get_storage_period(
        self,
        admin_service,
        mock_config_repository
    ):
        """Test getting storage period."""
        # Arrange
        mock_config_repository.get.return_value = "168"
        
        # Act
        result = await admin_service.get_storage_period()
        
        # Assert
        assert result == 168
        mock_config_repository.get.assert_called_once_with("storage_period_hours")
    
    @pytest.mark.asyncio
    async def test_get_storage_period_not_set(
        self,
        admin_service,
        mock_config_repository
    ):
        """Test getting storage period when not set."""
        # Arrange
        mock_config_repository.get.return_value = None
        
        # Act
        result = await admin_service.get_storage_period()
        
        # Assert
        assert result is None
    
    @pytest.mark.asyncio
    async def test_set_analysis_period_valid(
        self,
        admin_service,
        mock_config_repository
    ):
        """Test setting valid analysis period."""
        # Act
        await admin_service.set_analysis_period(24)
        
        # Assert
        mock_config_repository.set.assert_called_once_with(
            key="analysis_period_hours",
            value="24"
        )
    
    @pytest.mark.asyncio
    async def test_set_analysis_period_invalid(self, admin_service):
        """Test setting invalid analysis period."""
        # Act & Assert
        with pytest.raises(ValueError, match="Analysis period must be positive"):
            await admin_service.set_analysis_period(0)
    
    @pytest.mark.asyncio
    async def test_toggle_collection_enable(
        self,
        admin_service,
        mock_config_repository
    ):
        """Test enabling collection."""
        # Act
        await admin_service.toggle_collection(True)
        
        # Assert
        mock_config_repository.set.assert_called_once_with(
            key="collection_enabled",
            value="true"
        )
    
    @pytest.mark.asyncio
    async def test_toggle_collection_disable(
        self,
        admin_service,
        mock_config_repository
    ):
        """Test disabling collection."""
        # Act
        await admin_service.toggle_collection(False)
        
        # Assert
        mock_config_repository.set.assert_called_once_with(
            key="collection_enabled",
            value="false"
        )
    
    @pytest.mark.asyncio
    async def test_is_collection_enabled_true(
        self,
        admin_service,
        mock_config_repository
    ):
        """Test checking collection status when enabled."""
        # Arrange
        mock_config_repository.get.return_value = "true"
        
        # Act
        result = await admin_service.is_collection_enabled()
        
        # Assert
        assert result is True
    
    @pytest.mark.asyncio
    async def test_is_collection_enabled_false(
        self,
        admin_service,
        mock_config_repository
    ):
        """Test checking collection status when disabled."""
        # Arrange
        mock_config_repository.get.return_value = "false"
        
        # Act
        result = await admin_service.is_collection_enabled()
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_is_collection_enabled_default(
        self,
        admin_service,
        mock_config_repository
    ):
        """Test checking collection status defaults to enabled."""
        # Arrange
        mock_config_repository.get.return_value = None
        
        # Act
        result = await admin_service.is_collection_enabled()
        
        # Assert
        assert result is True
    
    @pytest.mark.asyncio
    async def test_get_stats_with_cache_count(
        self,
        admin_service,
        mock_message_repository,
        mock_cache_repository,
        mock_config_repository
    ):
        """Test getting stats with actual cache count."""
        # Arrange
        mock_message_repository.count.return_value = 10
        mock_message_repository.get_by_period.return_value = []
        mock_cache_repository.count.return_value = 5
        mock_config_repository.get.return_value = None
        
        # Act
        stats = await admin_service.get_stats()
        
        # Assert
        assert stats['total_messages'] == 10
        assert stats['cache_entries'] == 5
        mock_cache_repository.count.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_stats_cache_count_error(
        self,
        admin_service,
        mock_message_repository,
        mock_cache_repository,
        mock_config_repository
    ):
        """Test getting stats when cache count fails."""
        # Arrange
        mock_message_repository.count.return_value = 10
        mock_message_repository.get_by_period.return_value = []
        mock_cache_repository.count.side_effect = Exception("Database error")
        mock_config_repository.get.return_value = None
        
        # Act
        stats = await admin_service.get_stats()
        
        # Assert
        assert stats['total_messages'] == 10
        assert stats['cache_entries'] == "Error"
    
    @pytest.mark.asyncio
    async def test_get_stats_formats_timestamps_with_timezone(
        self,
        mock_message_repository,
        mock_config_repository,
        mock_cache_repository
    ):
        """Test get_stats formats timestamps with configured timezone."""
        # Arrange
        admin_service = AdminService(
            message_repository=mock_message_repository,
            config_repository=mock_config_repository,
            cache_repository=mock_cache_repository,
            timezone="Europe/Moscow"
        )
        
        # Create test messages with known UTC timestamps
        test_messages = [
            MessageModel(
                message_id=1,
                chat_id=-100123456789,
                user_id=111,
                username="user1",
                text="First message",
                timestamp=datetime(2024, 1, 15, 10, 0, 0),  # 10:00 UTC
                reactions=None,
                reply_to_message_id=None
            ),
            MessageModel(
                message_id=2,
                chat_id=-100123456789,
                user_id=222,
                username="user2",
                text="Second message",
                timestamp=datetime(2024, 1, 15, 14, 0, 0),  # 14:00 UTC
                reactions=None,
                reply_to_message_id=None
            )
        ]
        
        mock_message_repository.count.return_value = 2
        mock_message_repository.get_by_period.return_value = test_messages
        mock_cache_repository.count.return_value = 0
        mock_config_repository.get.return_value = None
        
        # Act
        stats = await admin_service.get_stats()
        
        # Assert
        assert stats['total_messages'] == 2
        # Moscow is UTC+3, so 10:00 UTC = 13:00 MSK, 14:00 UTC = 17:00 MSK
        assert stats['oldest_message'] == "2024-01-15 13:00:00"
        assert stats['newest_message'] == "2024-01-15 17:00:00"
    
    @pytest.mark.asyncio
    async def test_get_stats_uses_utc_when_timezone_is_none(
        self,
        mock_message_repository,
        mock_config_repository,
        mock_cache_repository
    ):
        """Test get_stats uses UTC when timezone is None."""
        # Arrange
        admin_service = AdminService(
            message_repository=mock_message_repository,
            config_repository=mock_config_repository,
            cache_repository=mock_cache_repository,
            timezone=None
        )
        
        # Create test messages with known UTC timestamps
        test_messages = [
            MessageModel(
                message_id=1,
                chat_id=-100123456789,
                user_id=111,
                username="user1",
                text="First message",
                timestamp=datetime(2024, 1, 15, 10, 0, 0),  # 10:00 UTC
                reactions=None,
                reply_to_message_id=None
            ),
            MessageModel(
                message_id=2,
                chat_id=-100123456789,
                user_id=222,
                username="user2",
                text="Second message",
                timestamp=datetime(2024, 1, 15, 14, 0, 0),  # 14:00 UTC
                reactions=None,
                reply_to_message_id=None
            )
        ]
        
        mock_message_repository.count.return_value = 2
        mock_message_repository.get_by_period.return_value = test_messages
        mock_cache_repository.count.return_value = 0
        mock_config_repository.get.return_value = None
        
        # Act
        stats = await admin_service.get_stats()
        
        # Assert
        assert stats['total_messages'] == 2
        # Should remain in UTC
        assert stats['oldest_message'] == "2024-01-15 10:00:00"
        assert stats['newest_message'] == "2024-01-15 14:00:00"
