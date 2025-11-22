"""
Unit tests for Config timezone validation.
"""
import pytest
import os
from unittest.mock import patch

from config.settings import Config


@pytest.mark.unit
class TestConfigTimezone:
    """Test cases for Config timezone validation."""
    
    def test_valid_timezone_loading(self):
        """Test loading valid timezone from environment."""
        # Arrange
        with patch.dict(os.environ, {
            "BOT_TOKEN": "test_token",
            "ADMIN_ID": "123456",
            "OPENAI_API_KEY": "test_key",
            "TIMEZONE": "Europe/Moscow"
        }):
            # Act
            config = Config.from_env()
            
            # Assert
            assert config.timezone == "Europe/Moscow"
    
    def test_invalid_timezone_fallback_to_utc_with_warning(self, caplog):
        """Test invalid timezone falls back to UTC with warning."""
        # Arrange
        with patch.dict(os.environ, {
            "BOT_TOKEN": "test_token",
            "ADMIN_ID": "123456",
            "OPENAI_API_KEY": "test_key",
            "TIMEZONE": "Invalid/Timezone"
        }):
            # Act
            config = Config.from_env()
            
            # Assert
            assert config.timezone is None
            assert "Invalid timezone 'Invalid/Timezone', defaulting to UTC" in caplog.text
    
    def test_missing_timezone_defaults_to_none(self):
        """Test missing timezone defaults to None."""
        # Arrange
        with patch.dict(os.environ, {
            "BOT_TOKEN": "test_token",
            "ADMIN_ID": "123456",
            "OPENAI_API_KEY": "test_key"
        }, clear=True):
            # Mock load_dotenv to prevent loading actual .env file
            with patch('config.settings.load_dotenv'):
                # Act
                config = Config.from_env()
                
                # Assert
                assert config.timezone is None
    
    def test_various_valid_timezones(self):
        """Test various valid IANA timezone identifiers."""
        valid_timezones = [
            "America/New_York",
            "Asia/Tokyo",
            "Europe/London",
            "UTC"
        ]
        
        for tz in valid_timezones:
            with patch.dict(os.environ, {
                "BOT_TOKEN": "test_token",
                "ADMIN_ID": "123456",
                "OPENAI_API_KEY": "test_key",
                "TIMEZONE": tz
            }):
                # Act
                config = Config.from_env()
                
                # Assert
                assert config.timezone == tz, f"Failed for timezone: {tz}"
