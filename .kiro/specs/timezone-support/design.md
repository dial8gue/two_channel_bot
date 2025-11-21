# Design Document: Timezone Support

## Overview

This design implements timezone support for the Telegram Analytics Bot by adding timezone-aware datetime formatting throughout the system. The implementation uses Python's `pytz` library for robust timezone handling including daylight saving time transitions. The timezone is configured via the `TIMEZONE` environment variable and applied consistently across statistics output and OpenAI API prompts.

## Architecture

### High-Level Design

The timezone support follows a centralized configuration approach:

1. **Configuration Layer**: Load and validate timezone from environment variable
2. **Utility Layer**: Provide timezone conversion utilities
3. **Service Layer**: Apply timezone conversion in admin and analysis services
4. **Presentation Layer**: Format timestamps for display and API communication

### Key Principles

- **UTC Storage**: All timestamps remain stored in UTC in the database (no schema changes)
- **Display Conversion**: Timezone conversion happens only at display/output time
- **Graceful Degradation**: Invalid timezone configuration falls back to UTC with warning
- **Consistency**: Same timezone applied across all user-facing timestamps

## Components and Interfaces

### 1. Configuration Module (`config/settings.py`)

**Changes Required:**
- Add `timezone: Optional[str]` field to `Config` dataclass
- Add timezone validation in `from_env()` method
- Load `TIMEZONE` environment variable with default to `None` (UTC)

**Interface:**
```python
@dataclass
class Config:
    # ... existing fields ...
    timezone: Optional[str]  # IANA timezone identifier (e.g., "Europe/Moscow")
    
    @classmethod
    def from_env(cls) -> "Config":
        # Load TIMEZONE with validation
        timezone = cls._get_validated_timezone_env("TIMEZONE", default=None)
        # ... rest of loading logic ...
```

**Validation Logic:**
```python
@staticmethod
def _get_validated_timezone_env(key: str, default: Optional[str]) -> Optional[str]:
    """
    Get and validate timezone environment variable.
    
    Returns:
        Valid timezone identifier or None (UTC)
        
    Logs warning if invalid timezone provided.
    """
    value = os.getenv(key)
    if value is None:
        return default
    
    try:
        import pytz
        pytz.timezone(value)  # Validate timezone exists
        return value
    except pytz.exceptions.UnknownTimeZoneError:
        logger.warning(f"Invalid timezone '{value}', defaulting to UTC")
        return None
```

### 2. Timezone Utility Module (`utils/timezone_helper.py`)

**New Module**: Create utility functions for timezone conversion.

**Interface:**
```python
from datetime import datetime
from typing import Optional
import pytz

def convert_to_timezone(
    dt: datetime,
    timezone_str: Optional[str]
) -> datetime:
    """
    Convert UTC datetime to specified timezone.
    
    Args:
        dt: UTC datetime (naive or aware)
        timezone_str: IANA timezone identifier or None for UTC
        
    Returns:
        Timezone-aware datetime in specified timezone
    """
    # If no timezone specified, return as UTC
    if timezone_str is None:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=pytz.UTC)
        return dt
    
    # Ensure datetime is UTC-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    
    # Convert to target timezone
    target_tz = pytz.timezone(timezone_str)
    return dt.astimezone(target_tz)

def format_datetime(
    dt: datetime,
    timezone_str: Optional[str],
    format_str: str = "%Y-%m-%d %H:%M:%S"
) -> str:
    """
    Format datetime in specified timezone.
    
    Args:
        dt: UTC datetime
        timezone_str: IANA timezone identifier or None for UTC
        format_str: strftime format string
        
    Returns:
        Formatted datetime string
    """
    converted_dt = convert_to_timezone(dt, timezone_str)
    return converted_dt.strftime(format_str)
```

**Dependencies:**
- Add `pytz` to `requirements.txt`

### 3. Admin Service (`services/admin_service.py`)

**Changes Required:**
- Inject timezone configuration into `AdminService.__init__()`
- Update `get_stats()` method to format timestamps with timezone

**Modified Interface:**
```python
class AdminService:
    def __init__(
        self,
        message_repository: MessageRepository,
        config_repository: ConfigRepository,
        cache_repository: CacheRepository,
        timezone: Optional[str] = None  # NEW PARAMETER
    ):
        self.timezone = timezone
        # ... existing initialization ...
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics with timezone-formatted timestamps."""
        # ... existing logic to get timestamps ...
        
        if stats['total_messages'] > 0 and all_messages:
            timestamps = [msg.timestamp for msg in all_messages]
            oldest = min(timestamps)
            newest = max(timestamps)
            
            # Format with timezone
            from utils.timezone_helper import format_datetime
            stats['oldest_message'] = format_datetime(oldest, self.timezone)
            stats['newest_message'] = format_datetime(newest, self.timezone)
        
        # ... rest of method ...
```

### 4. OpenAI Client (`openai_client/client.py`)

**Changes Required:**
- Inject timezone configuration into `OpenAIClient.__init__()`
- Update `_build_prompt()` method to format message timestamps with timezone

**Modified Interface:**
```python
class OpenAIClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = None,
        model: str = "gpt-4o-mini",
        max_tokens: int = 4000,
        timezone: Optional[str] = None  # NEW PARAMETER
    ):
        self.timezone = timezone
        # ... existing initialization ...
    
    def _build_prompt(self, messages: List[MessageModel]) -> str:
        """Build analysis prompt with timezone-formatted timestamps."""
        sorted_messages = sorted(messages, key=lambda m: m.timestamp)
        
        message_lines = []
        for msg in sorted_messages:
            # Format timestamp with timezone
            from utils.timezone_helper import format_datetime
            timestamp_str = format_datetime(msg.timestamp, self.timezone)
            
            # ... rest of formatting logic ...
            message_lines.append(
                f"[{timestamp_str}] @{msg.username}: {msg.text}{reactions_str}{reply_str}"
            )
        
        # ... rest of method ...
```

### 5. Bot Main (`bot/main.py`)

**Changes Required:**
- Pass timezone configuration to service constructors during dependency injection

**Modified Dependency Injection:**
```python
async def main():
    config = Config.from_env()
    
    # ... existing setup ...
    
    # Initialize OpenAI client with timezone
    openai_client = OpenAIClient(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        model=config.openai_model,
        max_tokens=config.max_tokens,
        timezone=config.timezone  # NEW PARAMETER
    )
    
    # Initialize admin service with timezone
    admin_service = AdminService(
        message_repository=message_repository,
        config_repository=config_repository,
        cache_repository=cache_repository,
        timezone=config.timezone  # NEW PARAMETER
    )
    
    # ... rest of initialization ...
```

## Data Models

**No Changes Required**: All database models remain unchanged. Timestamps continue to be stored as UTC datetime objects in SQLite.

## Error Handling

### Invalid Timezone Configuration

**Scenario**: User provides invalid timezone in `TIMEZONE` environment variable

**Handling**:
1. Log warning message: `"Invalid timezone '{value}', defaulting to UTC"`
2. Set `config.timezone = None`
3. Continue execution with UTC timestamps
4. No error thrown - graceful degradation

### Timezone Conversion Errors

**Scenario**: Runtime error during timezone conversion (edge case)

**Handling**:
1. Log error with context
2. Fall back to UTC formatting
3. Return formatted timestamp without timezone conversion
4. Continue execution - don't block user operations

**Implementation in `timezone_helper.py`:**
```python
def format_datetime(
    dt: datetime,
    timezone_str: Optional[str],
    format_str: str = "%Y-%m-%d %H:%M:%S"
) -> str:
    try:
        converted_dt = convert_to_timezone(dt, timezone_str)
        return converted_dt.strftime(format_str)
    except Exception as e:
        logger.error(f"Timezone conversion failed: {e}, using UTC")
        # Fallback to UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt.strftime(format_str)
```

## Testing Strategy

### Unit Tests

**Test File**: `tests/unit/test_timezone_helper.py`

**Test Cases**:
1. `test_convert_to_timezone_with_valid_timezone()` - Verify conversion to Europe/Moscow
2. `test_convert_to_timezone_with_none_timezone()` - Verify UTC default
3. `test_convert_to_timezone_with_naive_datetime()` - Verify handling of naive datetimes
4. `test_format_datetime_with_timezone()` - Verify formatted output
5. `test_format_datetime_with_dst_transition()` - Verify DST handling

**Test File**: `tests/unit/test_admin_service_timezone.py`

**Test Cases**:
1. `test_get_stats_formats_timestamps_with_timezone()` - Verify stats output
2. `test_get_stats_without_timezone_uses_utc()` - Verify UTC fallback

**Test File**: `tests/unit/test_openai_client_timezone.py`

**Test Cases**:
1. `test_build_prompt_formats_timestamps_with_timezone()` - Verify prompt formatting
2. `test_build_prompt_without_timezone_uses_utc()` - Verify UTC fallback

### Integration Tests

**Test File**: `tests/integration/test_timezone_end_to_end.py`

**Test Cases**:
1. `test_stats_command_with_timezone_configured()` - Full flow from command to output
2. `test_analysis_command_with_timezone_configured()` - Full flow including OpenAI prompt

### Manual Testing

**Test Scenarios**:
1. Set `TIMEZONE=Europe/Moscow` in `.env`, run `/stats` command, verify timestamps
2. Set `TIMEZONE=America/New_York` in `.env`, run `/anal` command, verify OpenAI receives correct timestamps
3. Set `TIMEZONE=Invalid/Timezone` in `.env`, verify warning logged and UTC used
4. Omit `TIMEZONE` from `.env`, verify UTC timestamps used
5. Test during DST transition period (if possible)

## Dependencies

### New Dependencies

Add to `requirements.txt`:
```
pytz==2024.1
```

**Rationale**: `pytz` is the standard Python library for timezone handling with comprehensive IANA timezone database support and DST handling.

### Existing Dependencies

No changes to existing dependencies.

## Configuration

### Environment Variables

**New Variable**:
```bash
# Timezone for timestamp display (optional)
# Use IANA timezone identifiers (e.g., "Europe/Moscow", "America/New_York")
# If not set or invalid, defaults to UTC
TIMEZONE=Europe/Moscow
```

**Update `.env.example`**:
Add the new `TIMEZONE` variable with documentation.

## Implementation Notes

### Timezone Identifier Format

Use IANA timezone database identifiers (e.g., "Europe/Moscow", "America/New_York", "Asia/Tokyo"). These are more reliable than abbreviations like "MSK" or "EST" because they handle DST transitions correctly.

### Performance Considerations

- Timezone conversion is lightweight (microseconds per operation)
- No database queries added
- No impact on message collection performance
- Minimal overhead in statistics and analysis operations

### Backward Compatibility

- Existing deployments without `TIMEZONE` configured continue to work with UTC timestamps
- No database migration required
- No breaking changes to existing functionality

### Logging

Add timezone information to relevant log messages:
- Configuration loading: Log configured timezone or "UTC (default)"
- Timezone conversion errors: Log error details and fallback behavior

## Future Enhancements

### Potential Improvements (Out of Scope)

1. **Per-User Timezone Preferences**: Allow different users to configure their own timezone
2. **Timezone Display in Messages**: Show timezone abbreviation in formatted timestamps (e.g., "2024-01-15 14:30:00 MSK")
3. **Automatic Timezone Detection**: Detect timezone from Telegram user settings
4. **Multiple Timezone Display**: Show timestamps in multiple timezones simultaneously

These enhancements are not included in the current design to maintain simplicity and focus on the core requirement.
