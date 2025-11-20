# Requirements Document

## Introduction

This feature extends the Telegram Analytics Bot to allow regular group chat users (not just admins) to request message analysis using two new commands: `/anal` for short-term analysis and `/deep_anal` for extended analysis. The feature includes configurable time periods via environment variables, user-specific debounce protection (excluding admins), and improved debounce messaging that displays remaining wait time in hours, minutes, and seconds.

## Glossary

- **Bot**: The Telegram Analytics Bot system
- **User**: Any member of a Telegram group chat (excluding the admin)
- **Admin**: The bot administrator identified by ADMIN_ID in configuration
- **Analysis Command**: A command that triggers message analysis (`/anal` or `/deep_anal`)
- **Debounce**: Rate limiting mechanism that prevents commands from being executed too frequently in a chat
- **Debounce Period**: The minimum time interval that must pass between consecutive command executions in the same chat
- **Analysis Period**: The time window of messages to analyze (e.g., last 6 hours)
- **Group Chat**: A Telegram group or supergroup where the bot is active

## Requirements

### Requirement 1

**User Story:** As a group chat member, I want to analyze recent chat messages using `/anal`, so that I can quickly understand what was discussed in the last few hours.

#### Acceptance Criteria

1. WHEN a User sends the `/anal` command in a Group Chat, THE Bot SHALL analyze messages from the configured short analysis period
2. WHERE the short analysis period is not configured, THE Bot SHALL use 6 hours as the default value
3. THE Bot SHALL send the analysis result to the Group Chat where the command was issued
4. THE Bot SHALL format the analysis result using the same formatting logic as admin analysis commands
5. IF the User has executed an Analysis Command within the Debounce Period, THEN THE Bot SHALL reject the request with a debounce message

### Requirement 2

**User Story:** As a group chat member, I want to perform deeper analysis using `/deep_anal`, so that I can review discussions over a longer time period.

#### Acceptance Criteria

1. WHEN a User sends the `/deep_anal` command in a Group Chat, THE Bot SHALL analyze messages from the configured deep analysis period
2. WHERE the deep analysis period is not configured, THE Bot SHALL use 12 hours as the default value
3. THE Bot SHALL send the analysis result to the Group Chat where the command was issued
4. THE Bot SHALL format the analysis result using the same formatting logic as admin analysis commands
5. IF the User has executed an Analysis Command within the Debounce Period, THEN THE Bot SHALL reject the request with a debounce message

### Requirement 3

**User Story:** As a system administrator, I want to configure analysis periods via environment variables, so that I can customize the time windows without code changes.

#### Acceptance Criteria

1. THE Bot SHALL read the `ANAL_PERIOD_HOURS` environment variable for the `/anal` command period
2. THE Bot SHALL read the `DEEP_ANAL_PERIOD_HOURS` environment variable for the `/deep_anal` command period
3. WHERE `ANAL_PERIOD_HOURS` is not set, THE Bot SHALL use 6 as the default value
4. WHERE `DEEP_ANAL_PERIOD_HOURS` is not set, THE Bot SHALL use 12 as the default value
5. THE Bot SHALL validate that both period values are positive integers

### Requirement 4

**User Story:** As a regular user, I want to see how long I need to wait before using analysis commands again, so that I understand when I can make another request.

#### Acceptance Criteria

1. WHEN a User triggers debounce protection, THE Bot SHALL calculate the remaining wait time in seconds
2. THE Bot SHALL convert the remaining seconds into hours, minutes, and seconds components
3. THE Bot SHALL format the debounce message to display the wait time in the format "X ч Y мин Z сек"
4. WHERE the hours component is zero, THE Bot SHALL omit hours from the message
5. WHERE both hours and minutes are zero, THE Bot SHALL display only seconds

### Requirement 5

**User Story:** As the bot administrator, I want to bypass debounce restrictions, so that I can use analysis commands without waiting.

#### Acceptance Criteria

1. WHEN the Admin executes an Analysis Command, THE Bot SHALL skip debounce validation
2. THE Bot SHALL process the Admin's Analysis Command immediately regardless of previous command timing
3. THE Bot SHALL apply debounce protection only to Users who are not the Admin
4. THE Bot SHALL identify the Admin using the ADMIN_ID from configuration

### Requirement 6

**User Story:** As a group chat member, I want analysis commands to work only in group chats, so that the bot behavior is consistent with message collection.

#### Acceptance Criteria

1. THE Bot SHALL accept `/anal` and `/deep_anal` commands only from Group Chats
2. IF a User sends an Analysis Command in a private chat, THEN THE Bot SHALL ignore the command
3. THE Bot SHALL apply the same chat type filtering as used for message collection
4. THE Bot SHALL log when commands are received from non-group chat types

### Requirement 7

**User Story:** As a system administrator, I want a shared debounce mechanism for all users in a chat, so that analysis commands are rate-limited globally per chat.

#### Acceptance Criteria

1. THE Bot SHALL track debounce state per chat_id and operation_type combination
2. WHEN any User executes an Analysis Command in a Group Chat, THE Bot SHALL create a debounce record for that chat and command type
3. IF any User attempts to execute the same Analysis Command type in the same Group Chat within the Debounce Period, THEN THE Bot SHALL reject the request
4. THE Bot SHALL use a composite key of chat_id and operation_type for debounce tracking
5. THE Bot SHALL store debounce records in the database using the existing debounce table
6. THE Bot SHALL clean up expired debounce records automatically
