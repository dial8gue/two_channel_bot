# Requirements Document

## Introduction

This feature addresses a critical bug where Telegram analysis messages fail to send due to malformed Markdown formatting. The OpenAI API returns analysis text containing unescaped Markdown special characters, causing Telegram's message parser to fail with "Can't find end of the entity" errors. The system needs robust Markdown sanitization to ensure all analysis messages are delivered successfully.

## Glossary

- **Message Formatter**: The utility class responsible for formatting analysis results and other bot messages for Telegram
- **Markdown Entity**: Telegram formatting elements like bold (*text*), italic (_text_), code (`text`), and links [text](url)
- **Parse Mode**: Telegram's message parsing configuration that interprets formatting syntax (Markdown, HTML, or None)
- **Analysis Service**: The service that generates message analysis using OpenAI and formats results for delivery

## Requirements

### Requirement 1

**User Story:** As a bot administrator, I want analysis messages to always be delivered successfully, so that I can reliably receive insights about chat activity.

#### Acceptance Criteria

1. WHEN the Message Formatter receives analysis text from OpenAI, THE Message Formatter SHALL escape all Markdown special characters that are not part of intentional formatting
2. WHEN the Message Formatter processes text containing asterisks, underscores, backticks, or square brackets, THE Message Formatter SHALL ensure these characters do not create malformed Markdown entities
3. IF the formatted message exceeds Telegram's 4096 character limit, THEN THE Message Formatter SHALL split the message into multiple valid segments
4. THE Message Formatter SHALL preserve intentional formatting in headers and footers while sanitizing user-generated content

### Requirement 2

**User Story:** As a bot administrator, I want the option to use HTML formatting instead of Markdown, so that I have more reliable message parsing with fewer edge cases.

#### Acceptance Criteria

1. THE Message Formatter SHALL support both Markdown and HTML parse modes
2. WHEN using HTML parse mode, THE Message Formatter SHALL escape HTML special characters (<, >, &) in analysis content
3. THE Message Formatter SHALL use HTML tags for bold (<b>), italic (<i>), and code (<code>) formatting
4. THE Message Formatter SHALL maintain consistent visual output regardless of parse mode selection

### Requirement 3

**User Story:** As a developer, I want comprehensive error handling for message formatting failures, so that the bot gracefully handles edge cases without crashing.

#### Acceptance Criteria

1. WHEN Markdown sanitization encounters an error, THE Message Formatter SHALL fall back to plain text formatting
2. IF a formatted message still fails Telegram validation, THEN THE Message Formatter SHALL retry with progressively simpler formatting
3. THE Message Formatter SHALL log detailed information about formatting failures including message length and problematic content patterns
4. WHEN all formatting attempts fail, THE Message Formatter SHALL send a truncated plain text version with an error notice
