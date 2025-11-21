"""
Integration tests for end-to-end timezone functionality.
"""
import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
import pytz

from database.connection import DatabaseConnection
from database.repository import (
    MessageRepository,
    ConfigRepository,
    CacheRepository,
    DebounceRepository
)
from database.models import MessageModel
from services.admin_service import AdminService
from services.analysis_service import AnalysisService
from openai_client.client import OpenAIClient
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


@pytest.mark.integration
class TestTimezoneEndToEnd:
    """Integration tests for timezone functionality across the system."""
    
    @pytest.mark.asyncio
    async def test_stats_command_with_timezone_configured(self, repositories):
        """
        Test that stats command with timezone configured returns formatted timestamps.
        Requirements: 1.1, 1.2
        """
        # Arrange
        timezone = "Europe/Moscow"
        admin_service = AdminService(
            message_repository=repositories['message'],
            config_repository=repositories['config'],
            cache_repository=repositories['cache'],
            timezone=timezone
        )
        
        # Create test messages with known UTC timestamps
        utc_tz = pytz.UTC
        moscow_tz = pytz.timezone(timezone)
        
        # Create a UTC timestamp: 2024-01-15 12:00:00 UTC
        utc_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=utc_tz)
        
        # Save messages
        message1 = MessageModel(
            message_id=1,
            chat_id=-100123456789,
            user_id=1,
            username='user1',
            text='First message',
            timestamp=utc_time,
            reactions={}
        )
        await repositories['message'].create(message1)
        
        message2 = MessageModel(
            message_id=2,
            chat_id=-100123456789,
            user_id=2,
            username='user2',
            text='Second message',
            timestamp=utc_time + timedelta(hours=2),
            reactions={}
        )
        await repositories['message'].create(message2)
        
        # Act
        stats = await admin_service.get_stats()
        
        # Assert
        # UTC 12:00 should be 15:00 in Moscow (UTC+3)
        expected_oldest = utc_time.astimezone(moscow_tz).strftime("%Y-%m-%d %H:%M:%S")
        expected_newest = (utc_time + timedelta(hours=2)).astimezone(moscow_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        assert stats['oldest_message'] == expected_oldest
        assert stats['newest_message'] == expected_newest
        assert "15:00:00" in stats['oldest_message']  # Moscow time
        assert "17:00:00" in stats['newest_message']  # Moscow time
    
    @pytest.mark.asyncio
    async def test_stats_command_without_timezone_uses_utc(self, repositories):
        """
        Test that stats command without timezone uses UTC.
        Requirements: 1.1, 1.2
        """
        # Arrange
        admin_service = AdminService(
            message_repository=repositories['message'],
            config_repository=repositories['config'],
            cache_repository=repositories['cache'],
            timezone=None  # No timezone configured
        )
        
        # Create test message with known UTC timestamp
        utc_tz = pytz.UTC
        utc_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=utc_tz)
        
        message = MessageModel(
            message_id=1,
            chat_id=-100123456789,
            user_id=1,
            username='user1',
            text='Test message',
            timestamp=utc_time,
            reactions={}
        )
        await repositories['message'].create(message)
        
        # Act
        stats = await admin_service.get_stats()
        
        # Assert
        # Should remain in UTC
        expected_time = utc_time.strftime("%Y-%m-%d %H:%M:%S")
        assert stats['oldest_message'] == expected_time
        assert "12:00:00" in stats['oldest_message']  # UTC time
    
    @pytest.mark.asyncio
    async def test_analysis_command_with_timezone_sends_formatted_timestamps(self, repositories):
        """
        Test that analysis command with timezone sends formatted timestamps to OpenAI.
        Requirements: 2.1, 2.2
        """
        # Arrange
        timezone = "America/New_York"
        
        # Mock OpenAI client that captures the prompt
        captured_prompt = None
        
        async def mock_analyze(messages):
            nonlocal captured_prompt
            # Build the prompt to capture it
            client = OpenAIClient(
                api_key="test_key",
                timezone=timezone
            )
            captured_prompt = client._build_prompt(messages)
            return "Test analysis result"
        
        mock_openai_client = AsyncMock()
        mock_openai_client.analyze_messages = mock_analyze
        
        cache_manager = CacheManager(repositories['cache'])
        debounce_manager = DebounceManager(repositories['debounce'])
        
        analysis_service = AnalysisService(
            message_repository=repositories['message'],
            openai_client=mock_openai_client,
            cache_manager=cache_manager,
            debounce_manager=debounce_manager,
            debounce_interval_seconds=0,  # Disable debounce for test
            cache_ttl_minutes=60,
            analysis_period_hours=24
        )
        
        # Create test messages with known UTC timestamps
        utc_tz = pytz.UTC
        ny_tz = pytz.timezone(timezone)
        
        # Create a recent UTC timestamp (within last 24 hours)
        utc_time = datetime.now(utc_tz) - timedelta(hours=1)
        
        message = MessageModel(
            message_id=1,
            chat_id=-100123456789,
            user_id=1,
            username='user1',
            text='Test message for analysis',
            timestamp=utc_time,
            reactions={}
        )
        await repositories['message'].create(message)
        
        # Act
        result, from_cache = await analysis_service.analyze_messages(hours=24)
        
        # Assert
        assert captured_prompt is not None
        
        # Verify the timestamp was converted to New York timezone
        expected_ny_time = utc_time.astimezone(ny_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        assert expected_ny_time in captured_prompt
        # Verify the hour is different from UTC (timezone conversion happened)
        utc_hour = utc_time.strftime("%H")
        ny_hour = utc_time.astimezone(ny_tz).strftime("%H")
        assert utc_hour != ny_hour or utc_time.astimezone(ny_tz).strftime("%Y-%m-%d") != utc_time.strftime("%Y-%m-%d")
        assert "user1" in captured_prompt
        assert "Test message for analysis" in captured_prompt
    
    @pytest.mark.asyncio
    async def test_analysis_command_without_timezone_uses_utc(self, repositories):
        """
        Test that analysis command without timezone uses UTC in prompts.
        Requirements: 2.1, 2.2
        """
        # Arrange
        captured_prompt = None
        
        async def mock_analyze(messages):
            nonlocal captured_prompt
            # Build the prompt without timezone
            client = OpenAIClient(
                api_key="test_key",
                timezone=None
            )
            captured_prompt = client._build_prompt(messages)
            return "Test analysis result"
        
        mock_openai_client = AsyncMock()
        mock_openai_client.analyze_messages = mock_analyze
        
        cache_manager = CacheManager(repositories['cache'])
        debounce_manager = DebounceManager(repositories['debounce'])
        
        analysis_service = AnalysisService(
            message_repository=repositories['message'],
            openai_client=mock_openai_client,
            cache_manager=cache_manager,
            debounce_manager=debounce_manager,
            debounce_interval_seconds=0,
            cache_ttl_minutes=60,
            analysis_period_hours=24
        )
        
        # Create test message with known UTC timestamp (within last 24 hours)
        utc_tz = pytz.UTC
        utc_time = datetime.now(utc_tz) - timedelta(hours=1)
        
        message = MessageModel(
            message_id=1,
            chat_id=-100123456789,
            user_id=1,
            username='user1',
            text='Test message',
            timestamp=utc_time,
            reactions={}
        )
        await repositories['message'].create(message)
        
        # Act
        result, from_cache = await analysis_service.analyze_messages(hours=24)
        
        # Assert
        assert captured_prompt is not None
        
        # Should remain in UTC
        expected_utc_time = utc_time.strftime("%Y-%m-%d %H:%M:%S")
        assert expected_utc_time in captured_prompt
        assert "user1" in captured_prompt
        assert "Test message" in captured_prompt
