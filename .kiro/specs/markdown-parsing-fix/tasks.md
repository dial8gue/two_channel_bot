# Implementation Plan

- [x] 1. Implement core text escaping functions in MessageFormatter





  - Add `escape_markdown_v1()` method to escape Markdown special characters: `_`, `*`, `[`, `]`, `(`, `)`, `` ` ``
  - Add `escape_markdown_v2()` method for future MarkdownV2 support with extended character set
  - Add `convert_to_html()` method to convert text to HTML format and escape `<`, `>`, `&`
  - Add `strip_formatting()` helper method to remove all formatting for plain text fallback
  - _Requirements: 1.1, 1.2, 2.2, 2.3_

- [x] 2. Implement message splitting functionality





  - Add `split_long_message()` method that splits messages at paragraph boundaries (double newline)
  - Implement fallback splitting at single newlines if paragraphs exceed limit
  - Implement fallback splitting at last space before limit if lines exceed limit
  - Handle edge case of no spaces with hard character limit split
  - Ensure each chunk respects 4096 character Telegram limit
  - _Requirements: 1.3_

- [x] 3. Refactor format_analysis_result() with robust error handling





  - Modify method signature to accept `parse_mode` parameter (default "Markdown")
  - Apply appropriate escaping function based on parse_mode before adding headers/footers
  - Preserve intentional Markdown formatting in header and footer sections
  - Check message length and call `split_long_message()` if needed
  - Return either single string or list of strings for multi-part messages
  - Wrap escaping logic in try-except with fallback to plain text on error
  - _Requirements: 1.1, 1.4, 2.1, 3.1_

- [x] 4. Update admin router with fallback chain logic



  - Modify `cmd_analyze()` to handle both single string and list return from formatter
  - Implement three-tier fallback: Markdown → HTML → Plain text
  - Add try-except around `send_message()` to catch `TelegramBadRequest` exceptions
  - On "can't parse entities" error, retry with HTML format using `convert_to_html()`
  - On HTML failure, retry with plain text using `strip_formatting()` and `parse_mode=None`
  - Add logging for each fallback tier with appropriate log levels
  - _Requirements: 2.1, 3.2, 3.3_





- [ ] 5. Add configuration options for message formatting

  - Add `default_parse_mode` field to Config class (default "Markdown")
  - Add `enable_markdown_escaping` boolean flag to Config (default True)
  - Add `max_message_length` field to Config (default 4096)
  - Update admin router to use config values instead of hardcoded settings
  - _Requirements: 2.1_

- [x] 6. Write unit tests for text escaping functions




  - Test `escape_markdown_v1()` with various special characters
  - Test `escape_markdown_v2()` with extended character set
  - Test `convert_to_html()` with HTML entities and markdown conversion
  - Test `strip_formatting()` removes all formatting correctly
  - Test edge cases: empty strings, only special characters, mixed content
  - _Requirements: 1.1, 1.2, 2.2, 2.3_
-

- [x] 7. Write unit tests for message splitting



  - Test splitting at paragraph boundaries
  - Test splitting at line boundaries when paragraphs too long
  - Test splitting at spaces when lines too long
  - Test hard split when no spaces available
  - Test messages that don't need splitting
  - Test exact boundary conditions (4095, 4096, 4097 characters)
  - _Requirements: 1.3_

- [x] 8. Write unit tests for format_analysis_result()





  - Test formatting with Markdown parse mode
  - Test formatting with HTML parse mode
  - Test formatting with plain text (None parse mode)
  - Test cache flag appears correctly in footer
  - Test long analysis triggers message splitting
  - Test error handling falls back to plain text
  - _Requirements: 1.4, 2.1, 3.1_

- [ ] 9. Write integration tests for end-to-end analysis flow
  - Test successful message delivery with Markdown
  - Test fallback to HTML when Markdown fails
  - Test fallback to plain text when HTML fails
  - Test multi-part message delivery for long analysis
  - Mock Telegram API responses for different error scenarios
  - _Requirements: 3.2, 3.3, 3.4_
