# Requirements Document

## Introduction

This feature adds timezone support to the Telegram Analytics Bot to display timestamps in a user-configured timezone instead of UTC. The system will format message timestamps and statistics according to the timezone specified in the environment configuration, improving usability for users in different geographical locations.

## Glossary

- **Bot**: The Telegram Analytics Bot system
- **Admin**: The authorized user who can execute bot commands (configured via ADMIN_ID)
- **Timezone**: A geographical region's standard time offset from UTC (e.g., "Europe/Moscow", "America/New_York")
- **Statistics Output**: The formatted text response containing message analysis results sent to the admin
- **OpenAI Prompt**: The text payload sent to OpenAI API containing message data for analysis
- **Message Timestamp**: The datetime value indicating when a message was sent
- **Environment Configuration**: Settings loaded from the .env file at bot startup

## Requirements

### Requirement 1

**User Story:** As an admin, I want to see message timestamps in my local timezone in statistics output, so that I can understand when messages were sent without manual timezone conversion

#### Acceptance Criteria

1. WHEN THE Bot generates statistics output, THE Bot SHALL format the oldest_message timestamp according to the configured timezone
2. WHEN THE Bot generates statistics output, THE Bot SHALL format the newest_message timestamp according to the configured timezone
3. WHERE no timezone is configured in Environment Configuration, THE Bot SHALL display timestamps in UTC without modification
4. THE Bot SHALL use the timezone value from the TIMEZONE environment variable for all timestamp formatting operations

### Requirement 2

**User Story:** As an admin, I want message timestamps sent to OpenAI to be in my local timezone, so that the AI analysis reflects the correct temporal context of conversations

#### Acceptance Criteria

1. WHEN THE Bot prepares message data for OpenAI Prompt, THE Bot SHALL convert each Message Timestamp to the configured timezone
2. WHEN THE Bot formats the message list for OpenAI Prompt, THE Bot SHALL include timezone-adjusted timestamps for each message
3. WHERE no timezone is configured in Environment Configuration, THE Bot SHALL send timestamps to OpenAI in UTC without modification
4. THE Bot SHALL maintain timestamp accuracy during timezone conversion with precision to the second

### Requirement 3

**User Story:** As a system administrator, I want to configure the timezone via environment variable, so that I can set it once during deployment without code changes

#### Acceptance Criteria

1. THE Bot SHALL read the timezone configuration from the TIMEZONE environment variable during startup
2. WHERE the TIMEZONE environment variable contains an invalid timezone identifier, THE Bot SHALL log a warning and default to UTC
3. THE Bot SHALL validate the timezone identifier against the IANA timezone database
4. THE Bot SHALL apply the configured timezone consistently across all timestamp formatting operations

### Requirement 4

**User Story:** As an admin, I want timezone conversion to handle daylight saving time automatically, so that timestamps are always accurate regardless of the season

#### Acceptance Criteria

1. WHEN THE Bot converts a Message Timestamp, THE Bot SHALL apply daylight saving time rules for the configured timezone
2. THE Bot SHALL use the pytz library or equivalent for timezone-aware datetime operations
3. THE Bot SHALL preserve the original UTC timestamp in the database without modification
4. THE Bot SHALL perform timezone conversion only during display and API communication operations
