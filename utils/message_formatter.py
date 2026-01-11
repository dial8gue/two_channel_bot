"""
Message formatter for Telegram bot responses.
"""
import logging
import re
from typing import Dict, Any, List, Union, Optional
from aiogram.enums import ParseMode


logger = logging.getLogger(__name__)


def get_parse_mode(mode_str: str) -> Optional[ParseMode]:
    """
    Convert string parse mode to ParseMode enum.
    
    Args:
        mode_str: String representation ("Markdown", "HTML", "None", or None)
        
    Returns:
        ParseMode enum value or None
    """
    if not mode_str or mode_str == "None":
        return None
    elif mode_str == "Markdown":
        return ParseMode.MARKDOWN
    elif mode_str == "HTML":
        return ParseMode.HTML
    else:
        return None


class MessageFormatter:
    """Formats messages for Telegram with Markdown support."""
    
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
        if not text:
            return text
        
        # Escape special characters by prefixing with backslash
        special_chars = ['_', '*', '[', ']', '(', ')', '`']
        escaped_text = text
        
        for char in special_chars:
            escaped_text = escaped_text.replace(char, f'\\{char}')
        
        return escaped_text
    
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
        if not text:
            return text
        
        # Escape special characters by prefixing with backslash
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        escaped_text = text
        
        for char in special_chars:
            escaped_text = escaped_text.replace(char, f'\\{char}')
        
        return escaped_text
    
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
        if not text:
            return text
        
        # First escape HTML special characters
        html_text = text.replace('&', '&amp;')
        html_text = html_text.replace('<', '&lt;')
        html_text = html_text.replace('>', '&gt;')
        
        # Convert markdown-style formatting to HTML tags
        # Bold: **text** or __text__ -> <b>text</b>
        html_text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html_text)
        html_text = re.sub(r'__(.+?)__', r'<b>\1</b>', html_text)
        
        # Italic: *text* or _text_ -> <i>text</i>
        html_text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', html_text)
        html_text = re.sub(r'_(.+?)_', r'<i>\1</i>', html_text)
        
        # Code: `text` -> <code>text</code>
        html_text = re.sub(r'`(.+?)`', r'<code>\1</code>', html_text)
        
        return html_text
    
    @staticmethod
    def strip_formatting(text: str) -> str:
        """
        Remove all formatting for plain text fallback.
        
        Args:
            text: Text with potential formatting
            
        Returns:
            Plain text without any formatting characters
        """
        if not text:
            return text
        
        # Remove markdown formatting characters
        # Bold: **text** or __text__ -> text
        plain_text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        plain_text = re.sub(r'__(.+?)__', r'\1', plain_text)
        
        # Italic: *text* or _text_ -> text
        plain_text = re.sub(r'\*(.+?)\*', r'\1', plain_text)
        plain_text = re.sub(r'_(.+?)_', r'\1', plain_text)
        
        # Code: `text` -> text
        plain_text = re.sub(r'`(.+?)`', r'\1', plain_text)
        
        # Links: [text](url) -> text
        plain_text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', plain_text)
        
        # Remove any remaining special characters that might cause issues
        plain_text = plain_text.replace('\\', '')
        
        return plain_text
    
    @staticmethod
    def split_long_message(text: str, max_length: int = 4096) -> list[str]:
        """
        Split message into chunks that fit Telegram's limit.
        
        Splits at paragraph boundaries when possible to maintain readability.
        Strategy:
        1. Try to split at double newline (paragraph boundary)
        2. If paragraph > max_length, split at single newline
        3. If line > max_length, split at last space before limit
        4. If no spaces, hard split at character limit
        
        Args:
            text: Message text to split
            max_length: Maximum length per message (default 4096)
            
        Returns:
            List of message chunks
        """
        if not text:
            return [""]
        
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        remaining = text
        
        while remaining:
            if len(remaining) <= max_length:
                chunks.append(remaining)
                break
            
            # Try to find a good split point within max_length
            chunk = remaining[:max_length]
            split_point = -1
            
            # Strategy 1: Try to split at paragraph boundary (double newline)
            last_paragraph = chunk.rfind('\n\n')
            if last_paragraph > 0:
                split_point = last_paragraph + 2  # Include the double newline
            
            # Strategy 2: If no paragraph boundary, try single newline
            elif '\n' in chunk:
                last_newline = chunk.rfind('\n')
                if last_newline > 0:
                    split_point = last_newline + 1  # Include the newline
            
            # Strategy 3: If no newline, try to split at last space
            elif ' ' in chunk:
                last_space = chunk.rfind(' ')
                if last_space > 0:
                    split_point = last_space + 1  # Include the space
            
            # Strategy 4: Hard split at character limit (no good split point found)
            else:
                split_point = max_length
            
            # Add the chunk and continue with remaining text
            chunks.append(remaining[:split_point].rstrip())
            remaining = remaining[split_point:].lstrip()
        
        logger.debug(f"Split message into {len(chunks)} chunks")
        return chunks
    
    @staticmethod
    def format_analysis_result(
        analysis: str, 
        period_hours: int, 
        from_cache: bool = False,
        parse_mode: str = "Markdown",
        max_length: int = 4096,
        analysis_type: str = "analysis",
        username: str = None
    ) -> Union[str, List[str]]:
        """
        Format analysis result with robust error handling.
        
        Implements fallback chain:
        1. Try requested parse_mode with escaping
        2. Fall back to plain text on error
        
        Args:
            analysis: Raw analysis text from OpenAI
            period_hours: Number of hours analyzed
            from_cache: Whether the result was retrieved from cache
            parse_mode: Preferred parse mode ("Markdown", "HTML", or None)
            max_length: Maximum message length (default 4096)
            analysis_type: Type of analysis ("analysis" or "horoscope")
            username: Username for horoscope header (only used for horoscope type)
            
        Returns:
            Formatted message(s) - single string or list if split needed
        """
        # Конфигурация форматирования по parse_mode
        FORMAT_CONFIG = {
            "Markdown": {"bold": ("*", "*"), "italic": ("_", "_")},
            "HTML": {"bold": ("<b>", "</b>"), "italic": ("<i>", "</i>")},
            None: {"bold": ("", ""), "italic": ("", "")},
        }
        
        def get_format(mode: str) -> dict:
            """Получить конфигурацию форматирования для режима."""
            return FORMAT_CONFIG.get(mode, FORMAT_CONFIG[None])
        
        def build_header(mode: str) -> str:
            """Построить заголовок сообщения."""
            fmt = get_format(mode)
            b_open, b_close = fmt["bold"]
            
            if analysis_type == "horoscope":
                if username:
                    # Экранирование username для HTML
                    safe_username = (
                        username.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                        if mode == "HTML" else username
                    )
                    return f"🔮 {b_open}Гороскоп для @{safe_username}{b_close}\n\n"
                return f"🔮 {b_open}Гороскоп по сообщениям за {period_hours} ч{b_close}\n\n"
            
            return f"📊 {b_open}Анализ сообщений за последние {period_hours} ч{b_close}\n\n"
        
        def build_footer(mode: str) -> str:
            """Построить футер сообщения (только для кешированных результатов)."""
            if not from_cache:
                return ""
            
            fmt = get_format(mode)
            i_open, i_close = fmt["italic"]
            
            return f"\n\n{i_open}(из кеша){i_close}"
        
        def format_content(text: str, mode: str) -> str:
            """Форматировать контент в зависимости от режима."""
            match mode:
                case "Markdown":
                    return text  # LLM уже возвращает Markdown
                case "HTML":
                    return MessageFormatter.convert_to_html(text)
                case _:
                    return MessageFormatter.strip_formatting(text)
        
        def finalize_result(result: str) -> Union[str, List[str]]:
            """Проверить длину и разбить при необходимости."""
            if len(result) > max_length:
                logger.info(f"Message exceeds {max_length} chars ({len(result)}), splitting into chunks")
                chunks = MessageFormatter.split_long_message(result, max_length=max_length)
                logger.debug(f"Formatted analysis result into {len(chunks)} chunks (from_cache={from_cache}, parse_mode={parse_mode})")
                return chunks
            
            logger.debug(f"Formatted analysis result ({len(result)} chars, from_cache={from_cache}, parse_mode={parse_mode})")
            return result
        
        try:
            header = build_header(parse_mode)
            formatted_analysis = format_content(analysis.strip(), parse_mode)
            footer = build_footer(parse_mode)
            
            return finalize_result(header + formatted_analysis + footer)
            
        except Exception as e:
            # Fallback на plain text при любой ошибке
            logger.error(f"Error formatting analysis result with parse_mode={parse_mode}: {e}")
            logger.info("Falling back to plain text formatting")
            
            try:
                header = build_header(None)
                plain_analysis = MessageFormatter.strip_formatting(analysis.strip())
                footer = build_footer(None)
                
                return finalize_result(header + plain_analysis + footer)
                
            except Exception as fallback_error:
                # Крайний fallback - минимальное безопасное сообщение
                logger.error(f"Error in fallback formatting: {fallback_error}")
                safe_length = max_length - 96
                
                if analysis_type == "horoscope":
                    prefix = f"🔮 Гороскоп для @{username}" if username else f"🔮 Гороскоп за {period_hours} ч"
                else:
                    prefix = f"📊 Анализ за {period_hours} ч"
                
                return f"{prefix}\n\n{analysis[:safe_length]}"
    
    @staticmethod
    def format_stats(stats: Dict[str, Any]) -> str:
        """
        Format database statistics for Telegram message.
        
        Args:
            stats: Dictionary containing statistics data
            
        Returns:
            Formatted statistics message with Markdown
        """
        # Конфигурация полей статистики: (ключ, emoji, шаблон, требует_значение)
        STATS_FIELDS = [
            ('total_messages', '📝', 'Всего сообщений: *{value}*', False),
            ('oldest_message', '📅', 'Самое старое сообщение: {value}', True),
            ('newest_message', '📅', 'Самое новое сообщение: {value}', True),
            ('cache_entries', '💾', 'Записей в кеше: *{value}*', False),
            ('storage_period_hours', '⏱', 'Период хранения: *{value} ч*', False),
        ]
        
        try:
            message_parts = ["📈 *Статистика базы данных*\n"]
            
            for key, emoji, template, requires_value in STATS_FIELDS:
                if key in stats and (not requires_value or stats[key]):
                    message_parts.append(f"{emoji} {template.format(value=stats[key])}")
            
            # Особый случай для collection_enabled (булево значение с кастомным форматом)
            if 'collection_enabled' in stats:
                status = "✅ Включен" if stats['collection_enabled'] else "❌ Выключен"
                message_parts.append(f"🔄 Сбор сообщений: {status}")
            
            logger.debug("Formatted statistics message")
            return "\n".join(message_parts)
            
        except Exception as e:
            logger.error(f"Error formatting stats: {e}")
            return "📈 Статистика\n\nОшибка форматирования данных"
    
    @staticmethod
    def format_error(error_message: str) -> str:
        """
        Format error message for Telegram.
        
        Args:
            error_message: Error message text
            
        Returns:
            Formatted error message
        """
        return f"❌ *Ошибка*\n\n{error_message}"
    
    @staticmethod
    def format_success(message: str) -> str:
        """
        Format success message for Telegram.
        
        Args:
            message: Success message text
            
        Returns:
            Formatted success message
        """
        return f"✅ {message}"
    
    @staticmethod
    def format_debounce_wait_time(seconds: float) -> str:
        """
        Format remaining debounce time in human-readable format.
        
        Converts seconds to hours, minutes, and seconds components,
        omitting zero components for cleaner output.
        
        Args:
            seconds: Remaining time in seconds
            
        Returns:
            Formatted string like "2 ч 30 мин 15 сек" or "45 мин 30 сек"
            
        Examples:
            - 9015 seconds → "2 ч 30 мин 15 сек"
            - 2730 seconds → "45 мин 30 сек"
            - 45 seconds → "45 сек"
            - 0 seconds → "0 сек"
        """
        # Handle edge cases
        if seconds <= 0:
            return "0 сек"
        
        # Convert to integer to avoid fractional components
        total_seconds = int(seconds)
        
        # Calculate components
        hours = total_seconds // 3600
        remaining_after_hours = total_seconds % 3600
        minutes = remaining_after_hours // 60
        secs = remaining_after_hours % 60
        
        # Build time string, omitting zero components
        parts = []
        
        if hours > 0:
            parts.append(f"{hours} ч")
        
        if minutes > 0:
            parts.append(f"{minutes} мин")
        
        # Always show seconds if it's the only component, or if there are other components
        if secs > 0 or len(parts) == 0:
            parts.append(f"{secs} сек")
        
        return " ".join(parts)
    
    @staticmethod
    def format_debounce_warning(operation: str, remaining_seconds: float) -> str:
        """
        Format debounce warning message.
        
        Args:
            operation: Name of the operation
            remaining_seconds: Seconds remaining in debounce period
            
        Returns:
            Formatted warning message
        """
        time_str = MessageFormatter.format_debounce_wait_time(remaining_seconds)
        
        return (
            f"⏳ *Слишком частый запрос*\n\n"
            f"Операция «{operation}» была выполнена недавно.\n"
            f"Подождите еще {time_str}."
        )
