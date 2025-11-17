"""
Unit tests for MessageService.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from services.message_service import MessageService
from database.models import MessageModel


@pytest.fixture
def mock_message_repository():
    """Mock message repository."""
    return AsyncMock()


@pytest.fixture
def mock_debounce_repository():
    """Mock debounce repository."""
    return AsyncMock()


@pytest.fixture
def message_service(mock_message_repository, mock_debounce_repository):
    """Create message service with mocked dependencies."""
    return MessageService(
        message_repository=mock_message_repository,
        debounce_repository=mock_debounce_repository,
        storage_period_hours=168
    )


@pytest.mark.unit
class TestMessageService:
    """Test cases for MessageService."""
    
    @pytest.mark.asyncio
    async def test_save_message(self, message_service, mock_message_repository):
        """Test saving a message."""
        # Arrange
        mock_message_repository.create.return_value = 1
        timestamp = datetime.now()
        
        # Act
        result = await message_service.save_message(
            message_id=12345,
            chat_id=-100123456789,
            user_id=987654321,
            username="testuser",
            text="Test message",
            timestamp=timestamp,
            reactions={"👍": 5},
            reply_to_message_id=None
        )
        
        # Assert
        assert result == 1
        mock_message_repository.create.assert_called_once()
        call_args = mock_message_repository.create.call_args[0][0]
        assert isinstance(call_args, MessageModel)
        assert call_args.message_id == 12345
        assert call_args.text == "Test message"
    
    @pytest.mark.asyncio
    async def test_update_reactions(self, message_service, mock_message_repository):
        """Test updating message reactions."""
        # Arrange
        reactions = {"👍": 5, "❤️": 3}
        
        # Act
        await message_service.update_reactions(
            message_id=12345,
            chat_id=-100123456789,
            reactions=reactions
        )
        
        # Assert
        mock_message_repository.update_reactions.assert_called_once_with(
            message_id=12345,
            chat_id=-100123456789,
            reactions=reactions
        )
    
    @pytest.mark.asyncio
    async def test_get_messages_by_period(self, message_service, mock_message_repository):
        """Test retrieving messages by period."""
        # Arrange
        now = datetime.now()
        messages = [
            MessageModel(
                id=1,
                message_id=1,
                chat_id=-100123456789,
                user_id=1,
                username="user1",
                text="Message 1",
                timestamp=now - timedelta(hours=1)
            ),
            MessageModel(
                id=2,
                message_id=2,
                chat_id=-100123456789,
                user_id=2,
                username="user2",
                text="Message 2",
                timestamp=now - timedelta(hours=2)
            )
        ]
        mock_message_repository.get_by_period.return_value = messages
        
        # Act
        result = await message_service.get_messages_by_period(hours=24)
        
        # Assert
        assert len(result) == 2
        assert result[0].text == "Message 1"
        mock_message_repository.get_by_period.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_old_messages_first_time(self, message_service, mock_message_repository, mock_debounce_repository):
        """Test cleanup when never executed before."""
        # Arrange
        mock_debounce_repository.get_last_execution.return_value = None
        mock_message_repository.delete_older_than.return_value = 10
        
        # Act
        result = await message_service.cleanup_old_messages()
        
        # Assert
        assert result == 10
        mock_message_repository.delete_older_than.assert_called_once()
        mock_debounce_repository.update_execution.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_old_messages_debounced(self, message_service, mock_debounce_repository):
        """Test cleanup is skipped when in debounce period."""
        # Arrange
        mock_debounce_repository.get_last_execution.return_value = datetime.now() - timedelta(minutes=30)
        
        # Act
        result = await message_service.cleanup_old_messages()
        
        # Assert
        assert result == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_old_messages_after_debounce(self, message_service, mock_message_repository, mock_debounce_repository):
        """Test cleanup executes after debounce period."""
        # Arrange
        mock_debounce_repository.get_last_execution.return_value = datetime.now() - timedelta(hours=2)
        mock_message_repository.delete_older_than.return_value = 5
        
        # Act
        result = await message_service.cleanup_old_messages()
        
        # Assert
        assert result == 5
        mock_message_repository.delete_older_than.assert_called_once()
