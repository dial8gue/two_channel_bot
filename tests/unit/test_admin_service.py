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
def mock_group_repository():
    """Mock group repository."""
    return AsyncMock()


@pytest.fixture
def admin_service(
    mock_message_repository,
    mock_config_repository,
    mock_cache_repository,
    mock_group_repository,
):
    """Create admin service with mocked dependencies."""
    return AdminService(
        message_repository=mock_message_repository,
        config_repository=mock_config_repository,
        cache_repository=mock_cache_repository,
        group_repository=mock_group_repository,
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
        mock_cache_repository,
        mock_group_repository,
    ):
        """Test get_stats formats timestamps with configured timezone."""
        # Arrange
        admin_service = AdminService(
            message_repository=mock_message_repository,
            config_repository=mock_config_repository,
            cache_repository=mock_cache_repository,
            group_repository=mock_group_repository,
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
    @pytest.mark.asyncio
    async def test_get_stats_uses_utc_when_timezone_is_none(
        self,
        mock_message_repository,
        mock_config_repository,
        mock_cache_repository,
        mock_group_repository,
    ):
        """Test get_stats uses UTC when timezone is None."""
        # Arrange
        admin_service = AdminService(
            message_repository=mock_message_repository,
            config_repository=mock_config_repository,
            cache_repository=mock_cache_repository,
            group_repository=mock_group_repository,
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


@pytest.mark.unit
class TestAdminServiceGuestMode:
    """Tests for Guest Mode settings in AdminService."""

    @pytest.mark.asyncio
    async def test_toggle_guest_mode_enable(
        self, admin_service, mock_config_repository
    ):
        """toggle_guest_mode(True) persists 'true'."""
        await admin_service.toggle_guest_mode(True)
        mock_config_repository.set.assert_called_once_with(
            key="guest_mode_enabled", value="true"
        )

    @pytest.mark.asyncio
    async def test_toggle_guest_mode_disable(
        self, admin_service, mock_config_repository
    ):
        """toggle_guest_mode(False) persists 'false'."""
        await admin_service.toggle_guest_mode(False)
        mock_config_repository.set.assert_called_once_with(
            key="guest_mode_enabled", value="false"
        )

    @pytest.mark.asyncio
    async def test_is_guest_mode_enabled_true(
        self, admin_service, mock_config_repository
    ):
        """is_guest_mode_enabled returns True when stored 'true'."""
        mock_config_repository.get.return_value = "true"
        assert await admin_service.is_guest_mode_enabled() is True

    @pytest.mark.asyncio
    async def test_is_guest_mode_enabled_false(
        self, admin_service, mock_config_repository
    ):
        """is_guest_mode_enabled returns False when stored 'false'."""
        mock_config_repository.get.return_value = "false"
        assert await admin_service.is_guest_mode_enabled() is False

    @pytest.mark.asyncio
    async def test_is_guest_mode_enabled_unset_returns_none(
        self, admin_service, mock_config_repository
    ):
        """
        Unlike binary toggles, guest_mode must distinguish 'not set' from
        'explicitly false' so callers can fall back to the env default.
        """
        mock_config_repository.get.return_value = None
        assert await admin_service.is_guest_mode_enabled() is None

    @pytest.mark.asyncio
    async def test_set_guest_debounce_seconds_valid(
        self, admin_service, mock_config_repository
    ):
        """set_guest_debounce_seconds persists numeric value as string."""
        await admin_service.set_guest_debounce_seconds(120)
        mock_config_repository.set.assert_called_once_with(
            key="guest_debounce_seconds", value="120"
        )

    @pytest.mark.asyncio
    async def test_set_guest_debounce_seconds_invalid(self, admin_service):
        """Zero and negative values are rejected."""
        with pytest.raises(ValueError):
            await admin_service.set_guest_debounce_seconds(0)
        with pytest.raises(ValueError):
            await admin_service.set_guest_debounce_seconds(-5)

    @pytest.mark.asyncio
    async def test_get_guest_debounce_seconds_roundtrip(
        self, admin_service, mock_config_repository
    ):
        """Stored integer value round-trips through get_guest_debounce_seconds."""
        mock_config_repository.get.return_value = "90"
        assert await admin_service.get_guest_debounce_seconds() == 90

    @pytest.mark.asyncio
    async def test_get_guest_debounce_seconds_unset(
        self, admin_service, mock_config_repository
    ):
        """Returns None when the value was never set, so caller uses env default."""
        mock_config_repository.get.return_value = None
        assert await admin_service.get_guest_debounce_seconds() is None

    @pytest.mark.asyncio
    async def test_get_guest_debounce_seconds_invalid_db_value(
        self, admin_service, mock_config_repository
    ):
        """
        Malformed values in the DB shouldn't crash the whole stats call —
        the helper must return None so defaults kick in.
        """
        mock_config_repository.get.return_value = "not-a-number"
        assert await admin_service.get_guest_debounce_seconds() is None

    @pytest.mark.asyncio
    async def test_get_stats_includes_guest_mode_fields(
        self,
        admin_service,
        mock_message_repository,
        mock_cache_repository,
        mock_config_repository,
    ):
        """get_stats exposes guest_mode_enabled and guest_debounce_seconds."""
        mock_message_repository.count.return_value = 0
        mock_message_repository.get_by_period.return_value = []
        mock_cache_repository.count.return_value = 0

        # Simulate: guest_mode_enabled=true stored, guest_debounce_seconds=45 stored
        async def fake_get(key):
            return {
                "guest_mode_enabled": "true",
                "guest_debounce_seconds": "45",
            }.get(key)

        mock_config_repository.get.side_effect = fake_get

        stats = await admin_service.get_stats()

        assert stats["guest_mode_enabled"] is True
        assert stats["guest_debounce_seconds"] == 45
