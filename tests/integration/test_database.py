"""
Integration tests for database operations.
"""
import pytest
import tempfile
import os
from datetime import datetime, timedelta

from database.connection import DatabaseConnection
from database.repository import (
    MessageRepository,
    ConfigRepository,
    CacheRepository,
    DebounceRepository
)
from database.models import MessageModel


@pytest.fixture
async def temp_db():
    """Create temporary database for testing."""
    # Create temporary file
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Initialize database
    db_connection = DatabaseConnection(path)
    await db_connection.init_db()
    
    yield db_connection
    
    # Cleanup
    await db_connection.close()
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
async def message_repo(temp_db):
    """Create message repository with temp database."""
    return MessageRepository(temp_db)


@pytest.fixture
async def config_repo(temp_db):
    """Create config repository with temp database."""
    return ConfigRepository(temp_db)


@pytest.fixture
async def cache_repo(temp_db):
    """Create cache repository with temp database."""
    return CacheRepository(temp_db)


@pytest.fixture
async def debounce_repo(temp_db):
    """Create debounce repository with temp database."""
    return DebounceRepository(temp_db)


@pytest.mark.integration
class TestMessageRepository:
    """Integration tests for MessageRepository."""
    
    @pytest.mark.asyncio
    async def test_create_and_retrieve_message(self, message_repo):
        """Test creating and retrieving a message."""
        # Arrange
        now = datetime.now()
        message = MessageModel(
            message_id=12345,
            chat_id=-100123456789,
            user_id=987654321,
            username="testuser",
            text="Test message",
            timestamp=now,
            reactions={"👍": 5}
        )
        
        # Act
        message_id = await message_repo.create(message)
        messages = await message_repo.get_by_period(now - timedelta(hours=1))
        
        # Assert
        assert message_id > 0
        assert len(messages) == 1
        assert messages[0].text == "Test message"
        assert messages[0].reactions == {"👍": 5}
    
    @pytest.mark.asyncio
    async def test_update_reactions(self, message_repo):
        """Test updating message reactions."""
        # Arrange
        now = datetime.now()
        message = MessageModel(
            message_id=12345,
            chat_id=-100123456789,
            user_id=987654321,
            username="testuser",
            text="Test message",
            timestamp=now,
            reactions={"👍": 5}
        )
        await message_repo.create(message)
        
        # Act
        new_reactions = {"👍": 10, "❤️": 3}
        await message_repo.update_reactions(12345, -100123456789, new_reactions)
        messages = await message_repo.get_by_period(now - timedelta(hours=1))
        
        # Assert
        assert len(messages) == 1
        assert messages[0].reactions == new_reactions
    
    @pytest.mark.asyncio
    async def test_delete_older_than(self, message_repo):
        """Test deleting old messages."""
        # Arrange
        now = datetime.now()
        old_message = MessageModel(
            message_id=1,
            chat_id=-100123456789,
            user_id=1,
            username="user1",
            text="Old message",
            timestamp=now - timedelta(days=10)
        )
        new_message = MessageModel(
            message_id=2,
            chat_id=-100123456789,
            user_id=2,
            username="user2",
            text="New message",
            timestamp=now
        )
        await message_repo.create(old_message)
        await message_repo.create(new_message)
        
        # Act
        deleted_count = await message_repo.delete_older_than(now - timedelta(days=7))
        remaining_messages = await message_repo.get_by_period(now - timedelta(days=30))
        
        # Assert
        assert deleted_count == 1
        assert len(remaining_messages) == 1
        assert remaining_messages[0].text == "New message"
    
    @pytest.mark.asyncio
    async def test_clear_all(self, message_repo):
        """Test clearing all messages."""
        # Arrange
        now = datetime.now()
        for i in range(3):
            message = MessageModel(
                message_id=i,
                chat_id=-100123456789,
                user_id=i,
                username=f"user{i}",
                text=f"Message {i}",
                timestamp=now
            )
            await message_repo.create(message)
        
        # Act
        await message_repo.clear_all()
        count = await message_repo.count()
        
        # Assert
        assert count == 0


@pytest.mark.integration
class TestConfigRepository:
    """Integration tests for ConfigRepository."""
    
    @pytest.mark.asyncio
    async def test_set_and_get_config(self, config_repo):
        """Test setting and getting configuration."""
        # Act
        await config_repo.set("test_key", "test_value")
        value = await config_repo.get("test_key")
        
        # Assert
        assert value == "test_value"
    
    @pytest.mark.asyncio
    async def test_update_config(self, config_repo):
        """Test updating existing configuration."""
        # Arrange
        await config_repo.set("test_key", "old_value")
        
        # Act
        await config_repo.set("test_key", "new_value")
        value = await config_repo.get("test_key")
        
        # Assert
        assert value == "new_value"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_config(self, config_repo):
        """Test getting non-existent configuration."""
        # Act
        value = await config_repo.get("nonexistent_key")
        
        # Assert
        assert value is None


@pytest.mark.integration
class TestCacheRepository:
    """Integration tests for CacheRepository."""
    
    @pytest.mark.asyncio
    async def test_set_and_get_cache(self, cache_repo):
        """Test setting and getting cache."""
        # Act
        await cache_repo.set("test_key", "test_value", ttl_minutes=60)
        value = await cache_repo.get("test_key")
        
        # Assert
        assert value == "test_value"
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache_repo):
        """Test cache expiration."""
        # Arrange
        await cache_repo.set("test_key", "test_value", ttl_minutes=-1)
        
        # Act
        value = await cache_repo.get("test_key")
        
        # Assert
        assert value is None
    
    @pytest.mark.asyncio
    async def test_cleanup_expired(self, cache_repo):
        """Test cleanup of expired cache entries."""
        # Arrange
        await cache_repo.set("expired_key", "value1", ttl_minutes=-1)
        await cache_repo.set("valid_key", "value2", ttl_minutes=60)
        
        # Act
        await cache_repo.cleanup_expired()
        expired_value = await cache_repo.get("expired_key")
        valid_value = await cache_repo.get("valid_key")
        
        # Assert
        assert expired_value is None
        assert valid_value == "value2"
    
    @pytest.mark.asyncio
    async def test_count_cache_entries(self, cache_repo):
        """Test counting non-expired cache entries."""
        # Arrange
        await cache_repo.set("key1", "value1", ttl_minutes=60)
        await cache_repo.set("key2", "value2", ttl_minutes=60)
        await cache_repo.set("expired_key", "value3", ttl_minutes=-1)
        
        # Act
        count = await cache_repo.count()
        
        # Assert
        assert count == 2  # Only non-expired entries


@pytest.mark.integration
class TestDebounceRepository:
    """Integration tests for DebounceRepository."""
    
    @pytest.mark.asyncio
    async def test_update_and_get_execution(self, debounce_repo):
        """Test updating and getting execution time."""
        # Act
        await debounce_repo.update_execution("test_operation")
        last_execution = await debounce_repo.get_last_execution("test_operation")
        
        # Assert
        assert last_execution is not None
        assert isinstance(last_execution, datetime)
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_execution(self, debounce_repo):
        """Test getting non-existent execution."""
        # Act
        last_execution = await debounce_repo.get_last_execution("nonexistent_operation")
        
        # Assert
        assert last_execution is None
