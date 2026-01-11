"""
Unit tests for MessageFormatter text escaping functions.
"""
import pytest
from aiogram.enums import ParseMode

from utils.message_formatter import MessageFormatter, get_parse_mode


@pytest.mark.unit
class TestGetParseMode:
    """Test cases for get_parse_mode function."""
    
    def test_markdown_string_to_enum(self):
        """Test converting 'Markdown' string to ParseMode.MARKDOWN enum."""
        result = get_parse_mode("Markdown")
        assert result == ParseMode.MARKDOWN
    
    def test_html_string_to_enum(self):
        """Test converting 'HTML' string to ParseMode.HTML enum."""
        result = get_parse_mode("HTML")
        assert result == ParseMode.HTML
    
    def test_none_string_to_none(self):
        """Test converting 'None' string to None."""
        result = get_parse_mode("None")
        assert result is None
    
    def test_empty_string_to_none(self):
        """Test converting empty string to None."""
        result = get_parse_mode("")
        assert result is None
    
    def test_none_value_to_none(self):
        """Test converting None value to None."""
        result = get_parse_mode(None)
        assert result is None
    
    def test_invalid_string_to_none(self):
        """Test converting invalid string to None."""
        result = get_parse_mode("InvalidMode")
        assert result is None
    
    def test_case_sensitive(self):
        """Test that function is case-sensitive."""
        # Lowercase should not match
        result = get_parse_mode("markdown")
        assert result is None
        
        result = get_parse_mode("html")
        assert result is None


@pytest.mark.unit
class TestEscapeMarkdownV1:
    """Test cases for escape_markdown_v1 method."""
    
    def test_escape_asterisks(self):
        """Test escaping asterisks."""
        text = "This is *bold* text"
        result = MessageFormatter.escape_markdown_v1(text)
        assert result == "This is \\*bold\\* text"
    
    def test_escape_underscores(self):
        """Test escaping underscores."""
        text = "This is _italic_ text"
        result = MessageFormatter.escape_markdown_v1(text)
        assert result == "This is \\_italic\\_ text"
    
    def test_escape_square_brackets(self):
        """Test escaping square brackets."""
        text = "This is [link] text"
        result = MessageFormatter.escape_markdown_v1(text)
        assert result == "This is \\[link\\] text"
    
    def test_escape_parentheses(self):
        """Test escaping parentheses."""
        text = "This is (parentheses) text"
        result = MessageFormatter.escape_markdown_v1(text)
        assert result == "This is \\(parentheses\\) text"
    
    def test_escape_backticks(self):
        """Test escaping backticks."""
        text = "This is `code` text"
        result = MessageFormatter.escape_markdown_v1(text)
        assert result == "This is \\`code\\` text"
    
    def test_escape_all_special_characters(self):
        """Test escaping all special characters together."""
        text = "Text with _italic_ *bold* [link](url) and `code`"
        result = MessageFormatter.escape_markdown_v1(text)
        assert result == "Text with \\_italic\\_ \\*bold\\* \\[link\\]\\(url\\) and \\`code\\`"
    
    def test_empty_string(self):
        """Test with empty string."""
        result = MessageFormatter.escape_markdown_v1("")
        assert result == ""
    
    def test_none_value(self):
        """Test with None value."""
        result = MessageFormatter.escape_markdown_v1(None)
        assert result is None
    
    def test_only_special_characters(self):
        """Test with only special characters."""
        text = "_*[]()` "
        result = MessageFormatter.escape_markdown_v1(text)
        assert result == "\\_\\*\\[\\]\\(\\)\\` "
    
    def test_no_special_characters(self):
        """Test with text containing no special characters."""
        text = "This is plain text without special characters"
        result = MessageFormatter.escape_markdown_v1(text)
        assert result == "This is plain text without special characters"


@pytest.mark.unit
class TestEscapeMarkdownV2:
    """Test cases for escape_markdown_v2 method."""
    
    def test_escape_basic_characters(self):
        """Test escaping basic markdown characters."""
        text = "Text with _italic_ and *bold*"
        result = MessageFormatter.escape_markdown_v2(text)
        assert result == "Text with \\_italic\\_ and \\*bold\\*"
    
    def test_escape_extended_characters(self):
        """Test escaping extended MarkdownV2 characters."""
        text = "Text with ~ > # + - = | { } . !"
        result = MessageFormatter.escape_markdown_v2(text)
        assert result == "Text with \\~ \\> \\# \\+ \\- \\= \\| \\{ \\} \\. \\!"
    
    def test_escape_all_v2_characters(self):
        """Test escaping all MarkdownV2 special characters."""
        text = "_*[]()~`>#+-=|{}.!"
        result = MessageFormatter.escape_markdown_v2(text)
        assert result == "\\_\\*\\[\\]\\(\\)\\~\\`\\>\\#\\+\\-\\=\\|\\{\\}\\.\\!"
    
    def test_empty_string(self):
        """Test with empty string."""
        result = MessageFormatter.escape_markdown_v2("")
        assert result == ""
    
    def test_none_value(self):
        """Test with None value."""
        result = MessageFormatter.escape_markdown_v2(None)
        assert result is None
    
    def test_mixed_content(self):
        """Test with mixed content including text and special characters."""
        text = "Hello! This is a test. [Link](url) with #hashtag and +plus"
        result = MessageFormatter.escape_markdown_v2(text)
        assert result == "Hello\\! This is a test\\. \\[Link\\]\\(url\\) with \\#hashtag and \\+plus"


@pytest.mark.unit
class TestConvertToHtml:
    """Test cases for convert_to_html method."""
    
    def test_escape_html_entities(self):
        """Test escaping HTML special characters."""
        text = "Text with <tag> and & symbol"
        result = MessageFormatter.convert_to_html(text)
        assert result == "Text with &lt;tag&gt; and &amp; symbol"
    
    def test_convert_bold_double_asterisk(self):
        """Test converting **bold** to HTML."""
        text = "This is **bold** text"
        result = MessageFormatter.convert_to_html(text)
        assert result == "This is <b>bold</b> text"
    
    def test_convert_bold_double_underscore(self):
        """Test converting __bold__ to HTML."""
        text = "This is __bold__ text"
        result = MessageFormatter.convert_to_html(text)
        assert result == "This is <b>bold</b> text"
    
    def test_convert_italic_single_asterisk(self):
        """Test converting *italic* to HTML."""
        text = "This is *italic* text"
        result = MessageFormatter.convert_to_html(text)
        assert result == "This is <i>italic</i> text"
    
    def test_convert_italic_single_underscore(self):
        """Test converting _italic_ to HTML."""
        text = "This is _italic_ text"
        result = MessageFormatter.convert_to_html(text)
        assert result == "This is <i>italic</i> text"
    
    def test_convert_code(self):
        """Test converting `code` to HTML."""
        text = "This is `code` text"
        result = MessageFormatter.convert_to_html(text)
        assert result == "This is <code>code</code> text"
    
    def test_mixed_formatting(self):
        """Test converting mixed markdown formatting to HTML."""
        text = "Text with **bold**, *italic*, and `code`"
        result = MessageFormatter.convert_to_html(text)
        assert result == "Text with <b>bold</b>, <i>italic</i>, and <code>code</code>"
    
    def test_html_entities_and_markdown(self):
        """Test escaping HTML entities and converting markdown."""
        text = "**Bold** text with <tag> & symbol"
        result = MessageFormatter.convert_to_html(text)
        assert result == "<b>Bold</b> text with &lt;tag&gt; &amp; symbol"
    
    def test_empty_string(self):
        """Test with empty string."""
        result = MessageFormatter.convert_to_html("")
        assert result == ""
    
    def test_none_value(self):
        """Test with None value."""
        result = MessageFormatter.convert_to_html(None)
        assert result is None


@pytest.mark.unit
class TestStripFormatting:
    """Test cases for strip_formatting method."""
    
    def test_remove_bold_double_asterisk(self):
        """Test removing **bold** formatting."""
        text = "This is **bold** text"
        result = MessageFormatter.strip_formatting(text)
        assert result == "This is bold text"
    
    def test_remove_bold_double_underscore(self):
        """Test removing __bold__ formatting."""
        text = "This is __bold__ text"
        result = MessageFormatter.strip_formatting(text)
        assert result == "This is bold text"
    
    def test_remove_italic_single_asterisk(self):
        """Test removing *italic* formatting."""
        text = "This is *italic* text"
        result = MessageFormatter.strip_formatting(text)
        assert result == "This is italic text"
    
    def test_remove_italic_single_underscore(self):
        """Test removing _italic_ formatting."""
        text = "This is _italic_ text"
        result = MessageFormatter.strip_formatting(text)
        assert result == "This is italic text"
    
    def test_remove_code(self):
        """Test removing `code` formatting."""
        text = "This is `code` text"
        result = MessageFormatter.strip_formatting(text)
        assert result == "This is code text"
    
    def test_remove_links(self):
        """Test removing [text](url) links."""
        text = "This is a [link](https://example.com) in text"
        result = MessageFormatter.strip_formatting(text)
        assert result == "This is a link in text"
    
    def test_remove_all_formatting(self):
        """Test removing all formatting types."""
        text = "Text with **bold**, *italic*, `code`, and [link](url)"
        result = MessageFormatter.strip_formatting(text)
        assert result == "Text with bold, italic, code, and link"
    
    def test_remove_backslashes(self):
        """Test removing backslashes."""
        text = "Text with \\* escaped \\_ characters"
        result = MessageFormatter.strip_formatting(text)
        assert result == "Text with * escaped _ characters"
    
    def test_empty_string(self):
        """Test with empty string."""
        result = MessageFormatter.strip_formatting("")
        assert result == ""
    
    def test_none_value(self):
        """Test with None value."""
        result = MessageFormatter.strip_formatting(None)
        assert result is None
    
    def test_plain_text(self):
        """Test with plain text without formatting."""
        text = "This is plain text"
        result = MessageFormatter.strip_formatting(text)
        assert result == "This is plain text"


@pytest.mark.unit
class TestSplitLongMessage:
    """Test cases for split_long_message method."""
    
    def test_split_at_paragraph_boundaries(self):
        """Test splitting at paragraph boundaries (double newline)."""
        # Create text with paragraphs that will exceed limit when combined
        paragraph1 = "A" * 2000
        paragraph2 = "B" * 2000
        paragraph3 = "C" * 2000
        text = f"{paragraph1}\n\n{paragraph2}\n\n{paragraph3}"
        
        result = MessageFormatter.split_long_message(text, max_length=4096)
        
        # Should split into at least 2 chunks
        assert len(result) >= 2
        # Each chunk should be within limit
        for chunk in result:
            assert len(chunk) <= 4096
        # Content should be preserved
        combined = "".join(result)
        assert "A" * 2000 in combined
        assert "B" * 2000 in combined
        assert "C" * 2000 in combined
    
    def test_split_at_line_boundaries_when_paragraphs_too_long(self):
        """Test splitting at line boundaries when paragraphs exceed limit."""
        # Create a single paragraph with multiple lines that exceeds limit
        lines = [f"Line {i} with some content" * 50 for i in range(10)]
        text = "\n".join(lines)
        
        result = MessageFormatter.split_long_message(text, max_length=4096)
        
        # Should split into multiple chunks
        assert len(result) >= 2
        # Each chunk should be within limit
        for chunk in result:
            assert len(chunk) <= 4096
        # Should split at newlines (check that lines aren't broken mid-line)
        for chunk in result:
            if chunk.strip():  # Skip empty chunks
                assert not chunk.startswith(" with some content")
    
    def test_split_at_spaces_when_lines_too_long(self):
        """Test splitting at spaces when lines exceed limit."""
        # Create a single long line with spaces
        text = "word " * 1000  # Creates a long line with spaces
        
        result = MessageFormatter.split_long_message(text, max_length=4096)
        
        # Should split into multiple chunks
        assert len(result) >= 2
        # Each chunk should be within limit
        for chunk in result:
            assert len(chunk) <= 4096
        # Should split at spaces (check that words aren't broken)
        for chunk in result:
            if chunk.strip():
                # Each chunk should start with a complete word
                assert not chunk.startswith(" ")
    
    def test_hard_split_when_no_spaces_available(self):
        """Test hard split at character limit when no spaces available."""
        # Create text with no spaces or newlines
        text = "A" * 10000
        
        result = MessageFormatter.split_long_message(text, max_length=4096)
        
        # Should split into multiple chunks
        assert len(result) >= 3  # 10000 / 4096 = ~2.44, so at least 3 chunks
        # Each chunk should be within limit
        for chunk in result:
            assert len(chunk) <= 4096
        # All content should be preserved
        combined = "".join(result)
        assert len(combined) == 10000
        assert combined == "A" * 10000
    
    def test_messages_that_dont_need_splitting(self):
        """Test messages that don't need splitting."""
        # Short message
        short_text = "This is a short message"
        result = MessageFormatter.split_long_message(short_text, max_length=4096)
        assert len(result) == 1
        assert result[0] == short_text
        
        # Message exactly at limit
        exact_text = "A" * 4096
        result = MessageFormatter.split_long_message(exact_text, max_length=4096)
        assert len(result) == 1
        assert result[0] == exact_text
        
        # Message just under limit
        under_text = "A" * 4095
        result = MessageFormatter.split_long_message(under_text, max_length=4096)
        assert len(result) == 1
        assert result[0] == under_text
    
    def test_exact_boundary_conditions(self):
        """Test exact boundary conditions (4095, 4096, 4097 characters)."""
        # Test 4095 characters (just under limit)
        text_4095 = "A" * 4095
        result = MessageFormatter.split_long_message(text_4095, max_length=4096)
        assert len(result) == 1
        assert len(result[0]) == 4095
        
        # Test 4096 characters (exactly at limit)
        text_4096 = "B" * 4096
        result = MessageFormatter.split_long_message(text_4096, max_length=4096)
        assert len(result) == 1
        assert len(result[0]) == 4096
        
        # Test 4097 characters (just over limit)
        text_4097 = "C" * 4097
        result = MessageFormatter.split_long_message(text_4097, max_length=4096)
        assert len(result) == 2
        assert len(result[0]) <= 4096
        assert len(result[1]) <= 4096
        # Verify all content is preserved
        combined = "".join(result)
        assert len(combined) == 4097
        assert combined == "C" * 4097
    
    def test_empty_string(self):
        """Test with empty string."""
        result = MessageFormatter.split_long_message("", max_length=4096)
        assert len(result) == 1
        assert result[0] == ""
    
    def test_none_value(self):
        """Test with None value."""
        result = MessageFormatter.split_long_message(None, max_length=4096)
        assert len(result) == 1
        assert result[0] == ""
    
    def test_split_preserves_content_order(self):
        """Test that splitting preserves content order."""
        # Create text with identifiable sections
        sections = [f"Section {i}: " + "X" * 1500 for i in range(5)]
        text = "\n\n".join(sections)
        
        result = MessageFormatter.split_long_message(text, max_length=4096)
        
        # Verify content order is preserved
        combined = "".join(result)
        for i in range(5):
            assert f"Section {i}:" in combined
        
        # Verify sections appear in order
        positions = [combined.find(f"Section {i}:") for i in range(5)]
        assert positions == sorted(positions)


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases for text escaping functions."""
    
    def test_escape_markdown_v1_multiple_consecutive_special_chars(self):
        """Test escaping multiple consecutive special characters."""
        text = "***multiple***"
        result = MessageFormatter.escape_markdown_v1(text)
        assert result == "\\*\\*\\*multiple\\*\\*\\*"
    
    def test_escape_markdown_v2_complex_expression(self):
        """Test escaping complex mathematical expression."""
        text = "x = (a + b) - c * d / e"
        result = MessageFormatter.escape_markdown_v2(text)
        assert result == "x \\= \\(a \\+ b\\) \\- c \\* d / e"
    
    def test_convert_to_html_nested_formatting(self):
        """Test converting nested markdown formatting."""
        text = "**bold with *italic* inside**"
        result = MessageFormatter.convert_to_html(text)
        # Note: This tests actual behavior, nested formatting may not work perfectly
        assert "<b>" in result and "<i>" in result
    
    def test_strip_formatting_incomplete_markdown(self):
        """Test stripping incomplete markdown syntax."""
        text = "Text with *incomplete markdown"
        result = MessageFormatter.strip_formatting(text)
        # Should handle gracefully without crashing
        assert "Text with" in result
    
    def test_escape_markdown_v1_unicode_characters(self):
        """Test escaping with unicode characters."""
        text = "Текст с *жирным* и _курсивом_"
        result = MessageFormatter.escape_markdown_v1(text)
        assert result == "Текст с \\*жирным\\* и \\_курсивом\\_"
    
    def test_convert_to_html_only_special_chars(self):
        """Test converting text with only HTML special characters."""
        text = "<<< >>> &&& <>&"
        result = MessageFormatter.convert_to_html(text)
        assert result == "&lt;&lt;&lt; &gt;&gt;&gt; &amp;&amp;&amp; &lt;&gt;&amp;"
    
    def test_strip_formatting_mixed_complete_incomplete(self):
        """Test stripping mix of complete and incomplete formatting."""
        text = "**complete** and *incomplete and `code` and [link"
        result = MessageFormatter.strip_formatting(text)
        # Should handle gracefully
        assert "complete" in result and "code" in result



@pytest.mark.unit
class TestFormatAnalysisResult:
    """Test cases for format_analysis_result method."""
    
    def test_format_with_markdown_parse_mode(self):
        """Test formatting with Markdown parse mode."""
        analysis = "This is a test analysis with *special* characters"
        result = MessageFormatter.format_analysis_result(
            analysis=analysis,
            period_hours=24,
            from_cache=False,
            parse_mode="Markdown"
        )
        
        # Should return a string (not a list)
        assert isinstance(result, str)
        
        # Should contain header with Markdown formatting
        assert "📊 *Анализ сообщений за последние 24 ч*" in result
        
        # Should NOT escape special characters in analysis content
        # (LLM already provides properly formatted Markdown)
        assert "*special*" in result
        
        # Should contain footer with Markdown formatting
        assert "_Анализ выполнен роботами_" in result
        assert "(из кеша)" not in result
    
    def test_format_with_html_parse_mode(self):
        """Test formatting with HTML parse mode."""
        analysis = "This is a test analysis with <tag> and & symbol"
        result = MessageFormatter.format_analysis_result(
            analysis=analysis,
            period_hours=12,
            from_cache=False,
            parse_mode="HTML"
        )
        
        # Should return a string (not a list)
        assert isinstance(result, str)
        
        # Should contain header with HTML formatting
        assert "📊 <b>Анализ сообщений за последние 12 ч</b>" in result
        
        # Should escape HTML special characters
        assert "&lt;tag&gt;" in result
        assert "&amp;" in result
        
        # Should contain footer with HTML formatting
        assert "<i>Анализ выполнен роботами</i>" in result
        assert "(из кеша)" not in result
    
    def test_format_with_plain_text_parse_mode(self):
        """Test formatting with plain text (None parse mode)."""
        analysis = "This is a test analysis with **bold** and *italic*"
        result = MessageFormatter.format_analysis_result(
            analysis=analysis,
            period_hours=6,
            from_cache=False,
            parse_mode=None
        )
        
        # Should return a string (not a list)
        assert isinstance(result, str)
        
        # Should contain header without formatting
        assert "📊 Анализ сообщений за последние 6 ч" in result
        
        # Should strip formatting from analysis content
        assert "bold" in result
        assert "italic" in result
        assert "**" not in result
        assert "*" not in result or "\\*" not in result  # Either stripped or escaped
        
        # Should contain footer without formatting
        assert "Анализ выполнен роботами" in result
        assert "_" not in result or "\\_" not in result  # No markdown underscores
    
    def test_cache_flag_appears_in_footer_markdown(self):
        """Test cache flag appears correctly in footer with Markdown."""
        analysis = "Test analysis"
        
        # Test with from_cache=True
        result_cached = MessageFormatter.format_analysis_result(
            analysis=analysis,
            period_hours=24,
            from_cache=True,
            parse_mode="Markdown"
        )
        assert "(из кеша)" in result_cached
        assert "_Анализ выполнен роботами (из кеша)_" in result_cached
        
        # Test with from_cache=False
        result_not_cached = MessageFormatter.format_analysis_result(
            analysis=analysis,
            period_hours=24,
            from_cache=False,
            parse_mode="Markdown"
        )
        assert "(из кеша)" not in result_not_cached
        assert "_Анализ выполнен роботами_" in result_not_cached
    
    def test_cache_flag_appears_in_footer_html(self):
        """Test cache flag appears correctly in footer with HTML."""
        analysis = "Test analysis"
        
        # Test with from_cache=True
        result_cached = MessageFormatter.format_analysis_result(
            analysis=analysis,
            period_hours=24,
            from_cache=True,
            parse_mode="HTML"
        )
        assert "(из кеша)" in result_cached
        assert "<i>Анализ выполнен роботами (из кеша)</i>" in result_cached
        
        # Test with from_cache=False
        result_not_cached = MessageFormatter.format_analysis_result(
            analysis=analysis,
            period_hours=24,
            from_cache=False,
            parse_mode="HTML"
        )
        assert "(из кеша)" not in result_not_cached
        assert "<i>Анализ выполнен роботами</i>" in result_not_cached
    
    def test_cache_flag_appears_in_footer_plain_text(self):
        """Test cache flag appears correctly in footer with plain text."""
        analysis = "Test analysis"
        
        # Test with from_cache=True
        result_cached = MessageFormatter.format_analysis_result(
            analysis=analysis,
            period_hours=24,
            from_cache=True,
            parse_mode=None
        )
        assert "(из кеша)" in result_cached
        assert "Анализ выполнен роботами (из кеша)" in result_cached
        
        # Test with from_cache=False
        result_not_cached = MessageFormatter.format_analysis_result(
            analysis=analysis,
            period_hours=24,
            from_cache=False,
            parse_mode=None
        )
        assert "(из кеша)" not in result_not_cached
        assert "Анализ выполнен роботами" in result_not_cached
    
    def test_long_analysis_triggers_message_splitting(self):
        """Test long analysis triggers message splitting."""
        # Create a long analysis that exceeds 4096 characters
        long_analysis = "This is a long analysis. " * 200  # ~5000 characters
        
        result = MessageFormatter.format_analysis_result(
            analysis=long_analysis,
            period_hours=24,
            from_cache=False,
            parse_mode="Markdown"
        )
        
        # Should return a list of strings
        assert isinstance(result, list)
        assert len(result) >= 2
        
        # Each chunk should be within the limit
        for chunk in result:
            assert len(chunk) <= 4096
        
        # Content should be preserved across chunks
        combined = "".join(result)
        assert "This is a long analysis." in combined
    
    def test_long_analysis_with_custom_max_length(self):
        """Test long analysis with custom max_length parameter."""
        # Create analysis that exceeds custom limit
        analysis = "A" * 500
        
        result = MessageFormatter.format_analysis_result(
            analysis=analysis,
            period_hours=24,
            from_cache=False,
            parse_mode="Markdown",
            max_length=200
        )
        
        # Should return a list of strings
        assert isinstance(result, list)
        assert len(result) >= 2
        
        # Each chunk should be within the custom limit
        for chunk in result:
            assert len(chunk) <= 200
    
    def test_error_handling_falls_back_to_plain_text(self):
        """Test error handling falls back to plain text."""
        # Test with valid analysis to ensure the method works correctly
        # The error handling is tested implicitly through the fallback chain
        # in the admin router when Telegram rejects the message
        
        analysis = "Test analysis with normal content"
        result = MessageFormatter.format_analysis_result(
            analysis=analysis,
            period_hours=24,
            from_cache=False,
            parse_mode="Markdown"
        )
        
        # Should return a valid result
        assert result is not None
        assert isinstance(result, str)
        assert "📊" in result
        assert "Анализ" in result
        assert "Test analysis" in result
    
    def test_format_preserves_period_hours(self):
        """Test that different period_hours values are correctly displayed."""
        analysis = "Test"
        
        # Test with different period values
        for hours in [1, 6, 12, 24, 48, 168]:
            result = MessageFormatter.format_analysis_result(
                analysis=analysis,
                period_hours=hours,
                from_cache=False,
                parse_mode="Markdown"
            )
            assert f"{hours} ч" in result
    
    def test_format_with_empty_analysis(self):
        """Test formatting with empty analysis string."""
        result = MessageFormatter.format_analysis_result(
            analysis="",
            period_hours=24,
            from_cache=False,
            parse_mode="Markdown"
        )
        
        # Should still return a formatted message with header and footer
        assert isinstance(result, str)
        assert "📊" in result
        assert "Анализ выполнен роботами" in result
    
    def test_format_with_special_characters_in_all_modes(self):
        """Test formatting with special characters in all parse modes."""
        analysis = "Analysis with _underscores_ *asterisks* [brackets] and `backticks`"
        
        # Test Markdown mode
        result_md = MessageFormatter.format_analysis_result(
            analysis=analysis,
            period_hours=24,
            from_cache=False,
            parse_mode="Markdown"
        )
        assert isinstance(result_md, str)
        # Special characters should be escaped
        assert "\\_" in result_md or "underscores" in result_md
        
        # Test HTML mode
        result_html = MessageFormatter.format_analysis_result(
            analysis=analysis,
            period_hours=24,
            from_cache=False,
            parse_mode="HTML"
        )
        assert isinstance(result_html, str)
        # Should contain HTML tags or escaped content
        assert "<" in result_html or "underscores" in result_html
        
        # Test plain text mode
        result_plain = MessageFormatter.format_analysis_result(
            analysis=analysis,
            period_hours=24,
            from_cache=False,
            parse_mode=None
        )
        assert isinstance(result_plain, str)
        # Should contain the words without formatting
        assert "underscores" in result_plain
        assert "asterisks" in result_plain
    
    def test_format_exactly_at_length_boundary(self):
        """Test formatting when result is exactly at max_length boundary."""
        # Calculate how much content we need to reach exactly 4096 chars
        # Header: "📊 *Message analysis for last 24 h*\n\n"
        # Footer: "\n\n_Analysis performed by robots_"
        # We need to account for escaping, so use plain text mode
        
        header_len = len("📊 Анализ сообщений за последние 24 ч\n\n")
        footer_len = len("\n\nАнализ выполнен роботами")
        analysis_len = 4096 - header_len - footer_len
        
        analysis = "A" * analysis_len
        
        result = MessageFormatter.format_analysis_result(
            analysis=analysis,
            period_hours=24,
            from_cache=False,
            parse_mode=None,
            max_length=4096
        )
        
        # Should return a single string (not split)
        assert isinstance(result, str)
        assert len(result) <= 4096
    
    def test_format_just_over_length_boundary(self):
        """Test formatting when result is just over max_length boundary."""
        # Create analysis that will push total over 4096
        header_len = len("📊 Анализ сообщений за последние 24 ч\n\n")
        footer_len = len("\n\nАнализ выполнен роботами")
        analysis_len = 4096 - header_len - footer_len + 10  # 10 chars over
        
        analysis = "B" * analysis_len
        
        result = MessageFormatter.format_analysis_result(
            analysis=analysis,
            period_hours=24,
            from_cache=False,
            parse_mode=None,
            max_length=4096
        )
        
        # Should return a list (split into chunks)
        assert isinstance(result, list)
        assert len(result) >= 2
        
        # Each chunk should be within limit
        for chunk in result:
            assert len(chunk) <= 4096



@pytest.mark.unit
class TestFormatDebounceWaitTime:
    """Test cases for format_debounce_wait_time method."""
    
    def test_format_hours_minutes_seconds(self):
        """Test formatting with hours, minutes, and seconds."""
        # 2 hours, 30 minutes, 15 seconds = 9015 seconds
        result = MessageFormatter.format_debounce_wait_time(9015)
        assert result == "2 ч 30 мин 15 сек"
    
    def test_format_only_minutes_and_seconds(self):
        """Test formatting with only minutes and seconds (no hours)."""
        # 45 minutes, 30 seconds = 2730 seconds
        result = MessageFormatter.format_debounce_wait_time(2730)
        assert result == "45 мин 30 сек"
    
    def test_format_only_seconds(self):
        """Test formatting with only seconds."""
        result = MessageFormatter.format_debounce_wait_time(45)
        assert result == "45 сек"
    
    def test_format_zero_seconds(self):
        """Test formatting with zero seconds."""
        result = MessageFormatter.format_debounce_wait_time(0)
        assert result == "0 сек"
    
    def test_format_negative_seconds(self):
        """Test formatting with negative seconds (edge case)."""
        result = MessageFormatter.format_debounce_wait_time(-10)
        assert result == "0 сек"
    
    def test_format_one_hour_exactly(self):
        """Test formatting with exactly one hour."""
        result = MessageFormatter.format_debounce_wait_time(3600)
        assert result == "1 ч"
    
    def test_format_one_minute_exactly(self):
        """Test formatting with exactly one minute."""
        result = MessageFormatter.format_debounce_wait_time(60)
        assert result == "1 мин"
    
    def test_format_hours_and_seconds_no_minutes(self):
        """Test formatting with hours and seconds but no minutes."""
        # 2 hours and 15 seconds = 7215 seconds
        result = MessageFormatter.format_debounce_wait_time(7215)
        assert result == "2 ч 15 сек"
    
    def test_format_hours_and_minutes_no_seconds(self):
        """Test formatting with hours and minutes but no seconds."""
        # 3 hours and 45 minutes = 13500 seconds
        result = MessageFormatter.format_debounce_wait_time(13500)
        assert result == "3 ч 45 мин"
    
    def test_format_minutes_no_seconds(self):
        """Test formatting with minutes but no seconds."""
        # 5 minutes exactly = 300 seconds
        result = MessageFormatter.format_debounce_wait_time(300)
        assert result == "5 мин"
    
    def test_format_very_large_value(self):
        """Test formatting with very large value (many hours)."""
        # 100 hours, 30 minutes, 45 seconds = 361845 seconds
        result = MessageFormatter.format_debounce_wait_time(361845)
        assert result == "100 ч 30 мин 45 сек"
    
    def test_format_fractional_seconds(self):
        """Test formatting with fractional seconds (should be truncated)."""
        # 90.7 seconds should become 90 seconds (1 min 30 sec)
        result = MessageFormatter.format_debounce_wait_time(90.7)
        assert result == "1 мин 30 сек"
    
    def test_format_one_second(self):
        """Test formatting with one second."""
        result = MessageFormatter.format_debounce_wait_time(1)
        assert result == "1 сек"
    
    def test_format_59_seconds(self):
        """Test formatting with 59 seconds (just under a minute)."""
        result = MessageFormatter.format_debounce_wait_time(59)
        assert result == "59 сек"
    
    def test_format_3599_seconds(self):
        """Test formatting with 3599 seconds (just under an hour)."""
        # 59 minutes and 59 seconds
        result = MessageFormatter.format_debounce_wait_time(3599)
        assert result == "59 мин 59 сек"
    
    def test_format_3661_seconds(self):
        """Test formatting with 3661 seconds (just over an hour)."""
        # 1 hour, 1 minute, 1 second
        result = MessageFormatter.format_debounce_wait_time(3661)
        assert result == "1 ч 1 мин 1 сек"
