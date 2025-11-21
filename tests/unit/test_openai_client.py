"""
Unit tests for OpenAIClient.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from openai_client.client import OpenAIClient
from database.models import MessageModel


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Test analysis result"
    response.usage.total_tokens = 100
    return response


@pytest.fixture
def openai_client_with_timezone():
    """Create OpenAI client with timezone configured."""
    client = OpenAIClient(
        api_key="test-api-key",
        model="gpt-4o-mini",
        max_tokens=4000,
        timezone="Europe/Moscow"
    )
    # Mock the actual OpenAI client
    client.client = AsyncMock()
    return client


@pytest.fixture
def openai_client_without_timezone():
    """Create OpenAI client without timezone (UTC default)."""
    client = OpenAIClient(
        api_key="test-api-key",
        model="gpt-4o-mini",
        max_tokens=4000,
        timezone=None
    )
    # Mock the actual OpenAI client
    client.client = AsyncMock()
    return client


@pytest.fixture
def test_messages():
    """Create test messages with known timestamps."""
    return [
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
            timestamp=datetime(2024, 1, 15, 14, 30, 0),  # 14:30 UTC
            reactions={"👍": 5, "❤️": 3},
            reply_to_message_id=None
        )
    ]


@pytest.mark.unit
class TestOpenAIClient:
    """Test cases for OpenAIClient."""
    
    def test_build_prompt_formats_timestamps_with_timezone(
        self,
        openai_client_with_timezone,
        test_messages
    ):
        """Test _build_prompt formats message timestamps with configured timezone."""
        # Act
        prompt = openai_client_with_timezone._build_prompt(test_messages)
        
        # Assert
        # Moscow is UTC+3, so 10:00 UTC = 13:00 MSK, 14:30 UTC = 17:30 MSK
        assert "[2024-01-15 13:00:00] @user1: First message" in prompt
        assert "[2024-01-15 17:30:00] @user2: Second message" in prompt
        assert "Реакции: 👍: 5, ❤️: 3" in prompt
    
    def test_build_prompt_uses_utc_when_timezone_is_none(
        self,
        openai_client_without_timezone,
        test_messages
    ):
        """Test _build_prompt uses UTC when timezone is None."""
        # Act
        prompt = openai_client_without_timezone._build_prompt(test_messages)
        
        # Assert
        # Should remain in UTC
        assert "[2024-01-15 10:00:00] @user1: First message" in prompt
        assert "[2024-01-15 14:30:00] @user2: Second message" in prompt
        assert "Реакции: 👍: 5, ❤️: 3" in prompt
    
    def test_build_prompt_sorts_messages_by_timestamp(
        self,
        openai_client_with_timezone
    ):
        """Test _build_prompt sorts messages chronologically."""
        # Arrange - messages in reverse order
        messages = [
            MessageModel(
                message_id=2,
                chat_id=-100123456789,
                user_id=222,
                username="user2",
                text="Second message",
                timestamp=datetime(2024, 1, 15, 14, 0, 0),
                reactions=None,
                reply_to_message_id=None
            ),
            MessageModel(
                message_id=1,
                chat_id=-100123456789,
                user_id=111,
                username="user1",
                text="First message",
                timestamp=datetime(2024, 1, 15, 10, 0, 0),
                reactions=None,
                reply_to_message_id=None
            )
        ]
        
        # Act
        prompt = openai_client_with_timezone._build_prompt(messages)
        
        # Assert - should be sorted by timestamp
        first_msg_pos = prompt.find("First message")
        second_msg_pos = prompt.find("Second message")
        assert first_msg_pos < second_msg_pos
    
    @pytest.mark.asyncio
    async def test_analyze_messages_with_timezone(
        self,
        openai_client_with_timezone,
        test_messages,
        mock_openai_response
    ):
        """Test analyze_messages includes timezone-formatted timestamps in prompt."""
        # Arrange
        openai_client_with_timezone.client.chat.completions.create = AsyncMock(
            return_value=mock_openai_response
        )
        
        # Act
        result = await openai_client_with_timezone.analyze_messages(test_messages)
        
        # Assert
        assert result == "Test analysis result"
        
        # Verify the prompt was built with timezone formatting
        call_args = openai_client_with_timezone.client.chat.completions.create.call_args
        prompt = call_args.kwargs['messages'][1]['content']
        
        # Moscow is UTC+3
        assert "[2024-01-15 13:00:00]" in prompt
        assert "[2024-01-15 17:30:00]" in prompt
