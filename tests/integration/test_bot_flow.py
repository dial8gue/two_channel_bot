"""
Integration tests for bot message flow.
"""
import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from database.connection import DatabaseConnection
from database.repository import (
    MessageRepository,
    ConfigRepository,
    CacheRepository,
    DebounceRepository
)
from services.message_service import MessageService
from services.analysis_service import AnalysisService
from services.admin_service import AdminService
from utils.cache_manager import CacheManager
from utils.debounce_manager import DebounceManager


@pytest.fixture
async def temp_db():
    """Create temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    db_connection = DatabaseConnection(path)
    await db_connection.init_db()
    
    yield db_connection
    
    await db_connection.close()
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
async def repositories(temp_db):
    """Create all repositories."""
    return {
        'message': MessageRepository(temp_db),
        'config': ConfigRepository(temp_db),
        'cache': CacheRepository(temp_db),
        'debounce': DebounceRepository(temp_db)
    }


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client."""
    mock = AsyncMock()
    mock.analyze_messages.return_value = "Анализ: Пользователи обсуждали тестирование."
    return mock


@pytest.fixture
async def services(repositories, mock_openai_client):
    """Create all services."""
    cache_manager = CacheManager(repositories['cache'])
    debounce_manager = DebounceManager(repositories['debounce'])
    
    message_service = MessageService(
        message_repository=repositories['message'],
        debounce_repository=repositories['debounce'],
        storage_period_hours=168
    )
    
    analysis_service = AnalysisService(
        message_repository=repositories['message'],
        openai_client=mock_openai_client,
        cache_manager=cache_manager,
        debounce_manager=debounce_manager,
        debounce_interval_seconds=300,
        cache_ttl_minutes=60,
        analysis_period_hours=24
    )
    
    admin_service = AdminService(
        message_repository=repositories['message'],
        config_repository=repositories['config'],
        cache_repository=repositories['cache']
    )
    
    return {
        'message': message_service,
        'analysis': analysis_service,
        'admin': admin_service
    }


@pytest.mark.integration
class TestBotFlow:
    """Integration tests for complete bot workflows."""
    
    @pytest.mark.asyncio
    async def test_message_save_and_retrieve_flow(self, services):
        """Test complete flow of saving and retrieving messages."""
        # Arrange
        message_service = services['message']
        now = datetime.now()
        
        # Act - Save messages
        await message_service.save_message(
            message_id=1,
            chat_id=-100123456789,
            user_id=1,
            username="user1",
            text="Hello everyone!",
            timestamp=now - timedelta(hours=1)
        )
        
        await message_service.save_message(
            message_id=2,
            chat_id=-100123456789,
            user_id=2,
            username="user2",
            text="Great discussion!",
            timestamp=now - timedelta(hours=2)
        )
        
        # Act - Retrieve messages
        messages = await message_service.get_messages_by_period(hours=24)
        
        # Assert
        assert len(messages) == 2
        assert messages[0].text == "Great discussion!"
        assert messages[1].text == "Hello everyone!"
    
    @pytest.mark.asyncio
    async def test_analysis_flow_with_cache(self, services, mock_openai_client, temp_db):
        """Test complete analysis flow with caching."""
        # Arrange
        message_service = services['message']
        analysis_service = services['analysis']
        now = datetime.now()
        
        # Save test messages
        await message_service.save_message(
            message_id=1,
            chat_id=-100123456789,
            user_id=1,
            username="user1",
            text="Test message 1",
            timestamp=now
        )
        
        # Act - First analysis (should call OpenAI)
        result1, from_cache1 = await analysis_service.analyze_messages(hours=24)
        
        # Clear debounce by setting old execution time directly in database
        conn = await temp_db.get_connection()
        old_time = now - timedelta(seconds=400)
        await conn.execute(
            """
            UPDATE debounce 
            SET last_execution = ? 
            WHERE operation = ?
            """,
            (old_time, analysis_service.ANALYSIS_OPERATION)
        )
        await conn.commit()
        
        # Act - Second analysis (should use cache, not debounced)
        result2, from_cache2 = await analysis_service.analyze_messages(hours=24)
        
        # Assert
        assert result1 == "Анализ: Пользователи обсуждали тестирование."
        assert from_cache1 is False
        assert result2 == result1
        assert from_cache2 is True
        mock_openai_client.analyze_messages.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reaction_update_flow(self, services):
        """Test flow of updating message reactions."""
        # Arrange
        message_service = services['message']
        now = datetime.now()
        
        # Save message
        await message_service.save_message(
            message_id=1,
            chat_id=-100123456789,
            user_id=1,
            username="user1",
            text="Test message",
            timestamp=now,
            reactions={"👍": 5}
        )
        
        # Act - Update reactions
        await message_service.update_reactions(
            message_id=1,
            chat_id=-100123456789,
            reactions={"👍": 10, "❤️": 3}
        )
        
        # Retrieve and verify
        messages = await message_service.get_messages_by_period(hours=1)
        
        # Assert
        assert len(messages) == 1
        assert messages[0].reactions == {"👍": 10, "❤️": 3}
    
    @pytest.mark.asyncio
    async def test_admin_clear_database_flow(self, services):
        """Test admin flow for clearing database."""
        # Arrange
        message_service = services['message']
        admin_service = services['admin']
        now = datetime.now()
        
        # Save messages
        for i in range(3):
            await message_service.save_message(
                message_id=i,
                chat_id=-100123456789,
                user_id=i,
                username=f"user{i}",
                text=f"Message {i}",
                timestamp=now
            )
        
        # Verify messages exist
        messages_before = await message_service.get_messages_by_period(hours=1)
        assert len(messages_before) == 3
        
        # Act - Clear database
        await admin_service.clear_database()
        
        # Assert
        messages_after = await message_service.get_messages_by_period(hours=1)
        assert len(messages_after) == 0
    
    @pytest.mark.asyncio
    async def test_admin_config_flow(self, services):
        """Test admin configuration management flow."""
        # Arrange
        admin_service = services['admin']
        
        # Act - Set storage period
        await admin_service.set_storage_period(72)
        storage_period = await admin_service.get_storage_period()
        
        # Act - Set analysis period
        await admin_service.set_analysis_period(12)
        analysis_period = await admin_service.get_analysis_period()
        
        # Act - Toggle collection
        await admin_service.toggle_collection(False)
        collection_enabled = await admin_service.is_collection_enabled()
        
        # Assert
        assert storage_period == 72
        assert analysis_period == 12
        assert collection_enabled is False
    
    @pytest.mark.asyncio
    async def test_cleanup_old_messages_flow(self, services):
        """Test cleanup of old messages."""
        # Arrange
        message_service = services['message']
        now = datetime.now()
        
        # Save old and new messages
        await message_service.save_message(
            message_id=1,
            chat_id=-100123456789,
            user_id=1,
            username="user1",
            text="Old message",
            timestamp=now - timedelta(days=200)
        )
        
        await message_service.save_message(
            message_id=2,
            chat_id=-100123456789,
            user_id=2,
            username="user2",
            text="New message",
            timestamp=now
        )
        
        # Act - Cleanup (storage period is 168 hours = 7 days)
        deleted_count = await message_service.cleanup_old_messages()
        
        # Assert
        assert deleted_count == 1
        remaining_messages = await message_service.get_messages_by_period(hours=24*365)
        assert len(remaining_messages) == 1
        assert remaining_messages[0].text == "New message"
