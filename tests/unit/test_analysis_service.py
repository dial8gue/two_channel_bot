"""
Unit tests for AnalysisService.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from services.analysis_service import AnalysisService
from database.models import MessageModel


@pytest.fixture
def mock_message_repository():
    """Mock message repository."""
    return AsyncMock()


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client."""
    return AsyncMock()


@pytest.fixture
def mock_cache_manager():
    """Mock cache manager."""
    return AsyncMock()


@pytest.fixture
def mock_debounce_manager():
    """Mock debounce manager."""
    mock = AsyncMock()
    mock.debounce_repository = AsyncMock()
    return mock


@pytest.fixture
def analysis_service(mock_message_repository, mock_openai_client, mock_cache_manager, mock_debounce_manager):
    """Create analysis service with mocked dependencies."""
    return AnalysisService(
        message_repository=mock_message_repository,
        openai_client=mock_openai_client,
        cache_manager=mock_cache_manager,
        debounce_manager=mock_debounce_manager,
        debounce_interval_seconds=300,
        cache_ttl_minutes=60,
        analysis_period_hours=24
    )


@pytest.fixture
def sample_messages():
    """Sample messages for testing."""
    now = datetime.now()
    return [
        MessageModel(
            id=1,
            message_id=1,
            chat_id=-100123456789,
            user_id=1,
            username="user1",
            text="Hello everyone!",
            timestamp=now - timedelta(hours=1),
            reactions={"👍": 5}
        ),
        MessageModel(
            id=2,
            message_id=2,
            chat_id=-100123456789,
            user_id=2,
            username="user2",
            text="Great discussion!",
            timestamp=now - timedelta(hours=2),
            reactions={"❤️": 3}
        )
    ]


@pytest.mark.unit
class TestAnalysisService:
    """Test cases for AnalysisService."""
    
    @pytest.mark.asyncio
    async def test_analyze_messages_success(
        self, 
        analysis_service, 
        mock_message_repository,
        mock_openai_client,
        mock_cache_manager,
        mock_debounce_manager,
        sample_messages
    ):
        """Test successful message analysis."""
        # Arrange
        mock_debounce_manager.can_execute.return_value = (True, 0.0)
        mock_message_repository.get_by_period.return_value = sample_messages
        mock_cache_manager.get.return_value = None
        mock_openai_client.analyze_messages.return_value = "Analysis result"
        
        # Act
        result, from_cache = await analysis_service.analyze_messages(hours=24)
        
        # Assert
        assert result == "Analysis result"
        assert from_cache is False
        mock_openai_client.analyze_messages.assert_called_once()
        mock_cache_manager.set.assert_called_once()
        mock_debounce_manager.mark_executed.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_messages_from_cache(
        self,
        analysis_service,
        mock_message_repository,
        mock_cache_manager,
        mock_debounce_manager,
        sample_messages
    ):
        """Test analysis returns cached result."""
        # Arrange
        mock_debounce_manager.can_execute.return_value = (True, 0.0)
        mock_message_repository.get_by_period.return_value = sample_messages
        mock_cache_manager.get.return_value = "Cached analysis"
        
        # Act
        result, from_cache = await analysis_service.analyze_messages()
        
        # Assert
        assert result == "Cached analysis"
        assert from_cache is True
    
    @pytest.mark.asyncio
    async def test_analyze_messages_debounced(
        self,
        analysis_service,
        mock_message_repository,
        mock_cache_manager,
        mock_debounce_manager
    ):
        """Test analysis is blocked by debounce when no cache available."""
        # Arrange
        # Setup messages but no cache
        mock_message_repository.get_by_period.return_value = [
            MessageModel(
                message_id=1,
                chat_id=0,
                user_id=1,
                username="user1",
                text="test",
                timestamp=datetime.now(),
                reactions={}
            )
        ]
        mock_cache_manager.get.return_value = None  # No cache
        mock_debounce_manager.can_execute.return_value = (False, 150.0)
        
        # Act & Assert
        with pytest.raises(ValueError, match="150"):
            await analysis_service.analyze_messages()
    
    @pytest.mark.asyncio
    async def test_analyze_messages_no_messages(
        self,
        analysis_service,
        mock_message_repository,
        mock_debounce_manager
    ):
        """Test analysis with no messages."""
        # Arrange
        mock_debounce_manager.can_execute.return_value = (True, 0.0)
        mock_message_repository.get_by_period.return_value = []
        
        # Act
        result, from_cache = await analysis_service.analyze_messages()
        
        # Assert
        assert "Нет сообщений" in result
        assert from_cache is False
    
    @pytest.mark.asyncio
    async def test_generate_cache_key_consistency(self, analysis_service, sample_messages):
        """Test cache key generation is consistent."""
        # Act
        key1 = analysis_service._generate_cache_key(sample_messages)
        key2 = analysis_service._generate_cache_key(sample_messages)
        
        # Assert
        assert key1 == key2
        assert len(key1) == 64  # SHA256 hash length
    
    @pytest.mark.asyncio
    async def test_generate_cache_key_different_messages(self, analysis_service, sample_messages):
        """Test cache key changes with different messages."""
        # Arrange - Create a deep copy with modified text
        from datetime import datetime, timedelta
        from database.models import MessageModel
        
        now = datetime.now()
        modified_messages = [
            MessageModel(
                id=1,
                message_id=1,
                chat_id=-100123456789,
                user_id=1,
                username="user1",
                text="Different text",  # Changed text
                timestamp=now - timedelta(hours=1),
                reactions={"👍": 5}
            ),
            sample_messages[1]  # Keep second message the same
        ]
        
        # Act
        key1 = analysis_service._generate_cache_key(sample_messages)
        key2 = analysis_service._generate_cache_key(modified_messages)
        
        # Assert
        assert key1 != key2
