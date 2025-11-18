# Design Document: Markdown Parsing Fix

## Overview

This design addresses the critical bug where Telegram analysis messages fail due to malformed Markdown formatting. The OpenAI API returns analysis text with unescaped special characters (asterisks, underscores, backticks, square brackets) that break Telegram's Markdown parser. The solution implements robust text sanitization with fallback mechanisms to ensure 100% message delivery success.

## Architecture

### Current Flow (Broken)
```
OpenAI API → Raw Analysis Text → MessageFormatter.format_analysis_result() 
→ Add Header/Footer with Markdown → Send to Telegram with parse_mode="Markdown" 
→ ❌ FAILS: "Can't find end of entity"
```

### Proposed Flow (Fixed)
```
OpenAI API → Raw Analysis Text → MessageFormatter.format_analysis_result()
→ Sanitize Markdown Special Characters → Add Header/Footer with Safe Markdown
→ Validate Message Length → Send to Telegram with parse_mode="Markdown"
→ ✅ SUCCESS (or fallback to HTML/plain text if needed)
```

## Components and Interfaces

### 1. Enhanced MessageFormatter Class

**Location:** `utils/message_formatter.py`

**New Methods:**

```python
class MessageFormatter:
    
    @staticmethod
    def escape_markdown_v2(text: str) -> str:
        """
        Escape special characters for Telegram MarkdownV2.
        
        Characters to escape: _ * [ ] ( ) ~ ` > # + - = | { } . !
        
        Args:
            text: Raw text to escape
            
        Returns:
            Escaped text safe for MarkdownV2
        """
        pass
    
    @staticmethod
    def escape_markdown_v1(text: str) -> str:
        """
        Escape special characters for Telegram Markdown (legacy).
        
        Characters to escape: _ * [ ] ( ) `
        
        Args:
            text: Raw text to escape
            
        Returns:
            Escaped text safe for Markdown
        """
        pass
    
    @staticmethod
    def convert_to_html(text: str) -> str:
        """
        Convert text to HTML format and escape special characters.
        
        Escapes: < > &
        Converts markdown-style formatting to HTML tags if present.
        
        Args:
            text: Raw text to convert
            
        Returns:
            HTML-formatted text
        """
        pass
    
    @staticmethod
    def split_long_message(text: str, max_length: int = 4096) -> List[str]:
        """
        Split message into chunks that fit Telegram's limit.
        
        Splits at paragraph boundaries when possible to maintain readability.
        
        Args:
            text: Message text to split
            max_length: Maximum length per message (default 4096)
            
        Returns:
            List of message chunks
        """
        pass
    
    @staticmethod
    def format_analysis_result(
        analysis: str, 
        period_hours: int, 
        from_cache: bool = False,
        parse_mode: str = "Markdown"
    ) -> Union[str, List[str]]:
        """
        Format analysis result with robust error handling.
        
        Implements fallback chain:
        1. Try Markdown with escaping
        2. Try HTML with escaping
        3. Fall back to plain text
        
        Args:
            analysis: Raw analysis from OpenAI
            period_hours: Analysis period
            from_cache: Whether from cache
            parse_mode: Preferred parse mode ("Markdown", "HTML", or None)
            
        Returns:
            Formatted message(s) - single string or list if split needed
        """
        pass
```

### 2. Modified Admin Router

**Location:** `bot/routers/admin_router.py`

**Changes to `cmd_analyze` function:**

```python
async def cmd_analyze(message: Message, analysis_service: AnalysisService, config: Config):
    # ... existing code ...
    
    # Format result with error handling
    formatted_result = MessageFormatter.format_analysis_result(
        analysis=analysis_result,
        period_hours=period_hours,
        from_cache=from_cache,
        parse_mode="Markdown"  # Can be configured
    )
    
    # Handle single message or multiple chunks
    if isinstance(formatted_result, str):
        messages_to_send = [formatted_result]
    else:
        messages_to_send = formatted_result
    
    # Send message(s) with retry logic
    for idx, msg_text in enumerate(messages_to_send):
        try:
            await message.bot.send_message(
                chat_id=target_chat_id,
                text=msg_text,
                parse_mode="Markdown"
            )
        except TelegramBadRequest as e:
            if "can't parse entities" in str(e).lower():
                # Fallback to HTML
                logger.warning(f"Markdown failed, trying HTML: {e}")
                try:
                    html_text = MessageFormatter.convert_to_html(msg_text)
                    await message.bot.send_message(
                        chat_id=target_chat_id,
                        text=html_text,
                        parse_mode="HTML"
                    )
                except TelegramBadRequest:
                    # Final fallback to plain text
                    logger.error("HTML failed, using plain text")
                    plain_text = MessageFormatter.strip_formatting(msg_text)
                    await message.bot.send_message(
                        chat_id=target_chat_id,
                        text=plain_text,
                        parse_mode=None
                    )
            else:
                raise
```

## Data Models

No new data models required. All changes are in formatting logic.

## Error Handling

### Three-Tier Fallback Strategy

1. **Primary: Markdown with Escaping**
   - Escape all special characters in analysis content
   - Preserve intentional formatting in headers/footers
   - Log success

2. **Secondary: HTML Formatting**
   - Convert to HTML format
   - Escape HTML special characters
   - Use HTML tags for formatting
   - Log fallback event

3. **Tertiary: Plain Text**
   - Strip all formatting
   - Send raw text with basic structure
   - Log failure and send admin notification

### Specific Error Cases

| Error | Detection | Response |
|-------|-----------|----------|
| "Can't parse entities" | TelegramBadRequest exception | Try next fallback tier |
| Message too long | Length check before send | Split into chunks |
| Escaping failure | Exception in escape function | Use plain text immediately |
| All formats fail | All tiers exhausted | Send error message to admin |

## Testing Strategy

### Unit Tests

**File:** `tests/unit/test_message_formatter.py`

```python
class TestMarkdownEscaping:
    def test_escape_asterisks()
    def test_escape_underscores()
    def test_escape_square_brackets()
    def test_escape_backticks()
    def test_preserve_intentional_formatting()
    def test_mixed_special_characters()
    
class TestHTMLConversion:
    def test_escape_html_entities()
    def test_convert_markdown_to_html()
    def test_preserve_structure()
    
class TestMessageSplitting:
    def test_split_at_paragraph()
    def test_split_long_line()
    def test_respect_max_length()
    def test_no_split_needed()
    
class TestAnalysisFormatting:
    def test_format_with_markdown()
    def test_format_with_html()
    def test_format_plain_text()
    def test_handle_cache_flag()
    def test_handle_long_analysis()
```

### Integration Tests

**File:** `tests/integration/test_analysis_flow.py`

```python
class TestAnalysisMessageDelivery:
    async def test_successful_markdown_delivery()
    async def test_fallback_to_html()
    async def test_fallback_to_plain_text()
    async def test_split_long_message()
    async def test_real_openai_response_formatting()
```

### Manual Testing Scenarios

1. **Trigger the original error:**
   - Run `/analyze` command
   - Verify message sends successfully (no "Can't parse entities" error)

2. **Test with problematic characters:**
   - Create messages with: `*bold*`, `_italic_`, `[links]`, `` `code` ``
   - Run analysis
   - Verify proper escaping

3. **Test long messages:**
   - Analyze large message set (>4096 chars)
   - Verify proper splitting
   - Verify all chunks delivered

4. **Test fallback chain:**
   - Artificially inject malformed Markdown
   - Verify HTML fallback works
   - Verify plain text fallback works

## Implementation Notes

### Markdown Escaping Rules

**Telegram Markdown (legacy):**
- Escape: `_`, `*`, `[`, `]`, `(`, `)`, `` ` ``
- Method: Prefix with backslash `\`

**Telegram MarkdownV2 (recommended):**
- Escape: `_`, `*`, `[`, `]`, `(`, `)`, `~`, `` ` ``, `>`, `#`, `+`, `-`, `=`, `|`, `{`, `}`, `.`, `!`
- Method: Prefix with backslash `\`

**Decision:** Start with Markdown V1 for backward compatibility, add V2 support later if needed.

### Message Splitting Strategy

1. Try to split at double newline (paragraph boundary)
2. If paragraph > max_length, split at single newline
3. If line > max_length, split at last space before limit
4. If no spaces, hard split at character limit

### Configuration Options

Add to `config/settings.py`:

```python
class Config:
    # ... existing fields ...
    
    # Message formatting
    default_parse_mode: str = "Markdown"  # "Markdown", "HTML", or None
    enable_markdown_escaping: bool = True
    max_message_length: int = 4096
    split_at_paragraphs: bool = True
```

## Performance Considerations

- Escaping operations are O(n) where n = text length
- Minimal performance impact (< 1ms for typical messages)
- No additional API calls required
- No database changes needed

## Security Considerations

- Escaping prevents injection of malicious Markdown/HTML
- No user input directly controls parse mode
- Fallback to plain text prevents any formatting exploits
- Logging includes sanitized content (no sensitive data)

## Rollback Plan

If issues arise:
1. Set `enable_markdown_escaping = False` in config
2. Revert to plain text mode: `default_parse_mode = None`
3. Deploy previous version of `message_formatter.py`

No database migrations needed, so rollback is instant.
