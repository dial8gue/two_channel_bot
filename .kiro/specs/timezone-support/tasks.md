# Implementation Plan

- [x] 1. Add timezone dependency and utility module





  - Add `pytz==2024.1` to requirements.txt
  - Create `utils/timezone_helper.py` with timezone conversion functions (`convert_to_timezone`, `format_datetime`)
  - Implement error handling with UTC fallback for invalid timezones
  - _Requirements: 1.3, 1.4, 2.3, 3.2, 4.1, 4.2, 4.3_

- [x] 1.1 Write unit tests for timezone helper


  - Create `tests/unit/test_timezone_helper.py`
  - Test timezone conversion with valid timezone, None timezone, naive datetime
  - Test datetime formatting with timezone and DST transitions
  - _Requirements: 4.1, 4.2_

- [x] 2. Update configuration module for timezone support





  - Add `timezone: Optional[str]` field to `Config` dataclass in `config/settings.py`
  - Implement `_get_validated_timezone_env()` static method with pytz validation
  - Load `TIMEZONE` environment variable in `from_env()` method with validation
  - Log warning if invalid timezone provided and default to None (UTC)
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 2.1 Write unit tests for config timezone validation


  - Test valid timezone loading
  - Test invalid timezone fallback to UTC with warning
  - Test missing timezone defaults to None
  - _Requirements: 3.2, 3.3_

- [x] 3. Update admin service for timezone-aware statistics





  - Add `timezone: Optional[str]` parameter to `AdminService.__init__()`
  - Store timezone as instance variable
  - Update `get_stats()` method to use `format_datetime()` for oldest_message and newest_message timestamps
  - Import and use `utils.timezone_helper.format_datetime` for formatting
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 3.4_

- [x] 3.1 Write unit tests for admin service timezone formatting


  - Test `get_stats()` formats timestamps with configured timezone
  - Test `get_stats()` uses UTC when timezone is None
  - Mock message repository to return test messages with known timestamps
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 4. Update OpenAI client for timezone-aware prompts





  - Add `timezone: Optional[str]` parameter to `OpenAIClient.__init__()`
  - Store timezone as instance variable
  - Update `_build_prompt()` method to use `format_datetime()` for message timestamps
  - Import and use `utils.timezone_helper.format_datetime` for formatting
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.4, 4.4_

- [x] 4.1 Write unit tests for OpenAI client timezone formatting


  - Test `_build_prompt()` formats message timestamps with configured timezone
  - Test `_build_prompt()` uses UTC when timezone is None
  - Create test messages with known timestamps and verify prompt output
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 5. Wire timezone configuration through dependency injection





  - Update `bot/main.py` to pass `config.timezone` to `OpenAIClient` constructor
  - Update `bot/main.py` to pass `config.timezone` to `AdminService` constructor
  - Ensure timezone is propagated from config to all services that need it
  - _Requirements: 3.4, 4.4_

- [x] 6. Update environment configuration documentation





  - Add `TIMEZONE` variable to `.env.example` with documentation
  - Include examples of valid IANA timezone identifiers (Europe/Moscow, America/New_York)
  - Document that invalid or missing timezone defaults to UTC
  - _Requirements: 3.1, 3.2_

- [x] 7. Add integration tests for end-to-end timezone functionality





  - Create `tests/integration/test_timezone_end_to_end.py`
  - Test stats command with timezone configured returns formatted timestamps
  - Test analysis command with timezone configured sends formatted timestamps to OpenAI
  - _Requirements: 1.1, 1.2, 2.1, 2.2_
