"""
Unit tests for timezone_helper.
"""
import pytest
from datetime import datetime
import pytz

from utils.timezone_helper import convert_to_timezone, format_datetime


@pytest.mark.unit
class TestTimezoneHelper:
    """Test cases for timezone helper functions."""
    
    def test_convert_to_timezone_with_valid_timezone(self):
        """Test timezone conversion with valid timezone identifier."""
        # Arrange
        utc_dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=pytz.UTC)
        
        # Act
        result = convert_to_timezone(utc_dt, "Europe/Moscow")
        
        # Assert
        assert result.tzinfo is not None
        assert result.hour == 15  # Moscow is UTC+3
        assert result.strftime("%Y-%m-%d") == "2024-01-15"
    
    def test_convert_to_timezone_with_none_timezone(self):
        """Test timezone conversion with None timezone defaults to UTC."""
        # Arrange
        utc_dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=pytz.UTC)
        
        # Act
        result = convert_to_timezone(utc_dt, None)
        
        # Assert
        assert result.tzinfo == pytz.UTC
        assert result.hour == 12
    
    def test_convert_to_timezone_with_naive_datetime(self):
        """Test timezone conversion with naive datetime (no timezone info)."""
        # Arrange
        naive_dt = datetime(2024, 1, 15, 12, 0, 0)
        
        # Act
        result = convert_to_timezone(naive_dt, "America/New_York")
        
        # Assert
        assert result.tzinfo is not None
        assert result.hour == 7  # New York is UTC-5
    
    def test_convert_to_timezone_with_naive_datetime_and_none_timezone(self):
        """Test naive datetime with None timezone gets UTC timezone."""
        # Arrange
        naive_dt = datetime(2024, 1, 15, 12, 0, 0)
        
        # Act
        result = convert_to_timezone(naive_dt, None)
        
        # Assert
        assert result.tzinfo == pytz.UTC
        assert result.hour == 12

    def test_format_datetime_with_timezone(self):
        """Test datetime formatting with timezone."""
        # Arrange
        utc_dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=pytz.UTC)
        
        # Act
        result = format_datetime(utc_dt, "Europe/Moscow")
        
        # Assert
        assert result == "2024-01-15 15:00:00"
    
    def test_format_datetime_without_timezone(self):
        """Test datetime formatting without timezone uses UTC."""
        # Arrange
        utc_dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=pytz.UTC)
        
        # Act
        result = format_datetime(utc_dt, None)
        
        # Assert
        assert result == "2024-01-15 12:00:00"
    
    def test_format_datetime_with_custom_format(self):
        """Test datetime formatting with custom format string."""
        # Arrange
        utc_dt = datetime(2024, 1, 15, 12, 30, 45, tzinfo=pytz.UTC)
        
        # Act
        result = format_datetime(utc_dt, "Asia/Tokyo", "%d/%m/%Y %H:%M")
        
        # Assert
        assert result == "15/01/2024 21:30"  # Tokyo is UTC+9
    
    def test_format_datetime_with_dst_transition(self):
        """Test datetime formatting handles DST transitions correctly."""
        # Arrange - Summer time in New York (EDT, UTC-4)
        summer_dt = datetime(2024, 7, 15, 12, 0, 0, tzinfo=pytz.UTC)
        # Winter time in New York (EST, UTC-5)
        winter_dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=pytz.UTC)
        
        # Act
        summer_result = format_datetime(summer_dt, "America/New_York")
        winter_result = format_datetime(winter_dt, "America/New_York")
        
        # Assert
        assert summer_result == "2024-07-15 08:00:00"  # UTC-4 during DST
        assert winter_result == "2024-01-15 07:00:00"  # UTC-5 during standard time
    
    def test_convert_to_timezone_with_invalid_timezone_fallback(self):
        """Test timezone conversion with invalid timezone falls back to UTC."""
        # Arrange
        utc_dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=pytz.UTC)
        
        # Act
        result = convert_to_timezone(utc_dt, "Invalid/Timezone")
        
        # Assert
        assert result.tzinfo == pytz.UTC
        assert result.hour == 12
    
    def test_format_datetime_with_naive_datetime(self):
        """Test formatting naive datetime assumes UTC."""
        # Arrange
        naive_dt = datetime(2024, 1, 15, 12, 0, 0)
        
        # Act
        result = format_datetime(naive_dt, "Europe/Moscow")
        
        # Assert
        assert result == "2024-01-15 15:00:00"
