"""
Utility for sending Telegram messages with fallback formatting.
"""
import logging
from typing import Union, Callable, Awaitable
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

from utils.message_formatter import MessageFormatter, get_parse_mode
from config.settings import Config


logger = logging.getLogger(__name__)


async def safe_reply(message: Message, text: str, parse_mode = None) -> Message:
    """
    Отправить ответ реплаем, с fallback на обычный answer если сообщение удалено.
    
    Args:
        message: Исходное сообщение
        text: Текст ответа
        parse_mode: Режим парсинга (ParseMode enum или None)
        
    Returns:
        Отправленное сообщение
    """
    try:
        logger.debug(f"Sending reply to message {message.message_id}")
        return await message.reply(text, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        # Message deleted or unavailable - send normally
        if "message to reply not found" in str(e).lower() or "replied message not found" in str(e).lower():
            logger.debug(f"Original message deleted, sending without reply")
            return await message.answer(text, parse_mode=parse_mode)
        raise


async def send_analysis_with_fallback(
    send_func: Callable[[str, Union[ParseMode, None]], Awaitable[None]],
    analysis_result: str,
    period_hours: int,
    from_cache: bool,
    config: Config
):
    """
    Send analysis result with three-tier fallback: Markdown → HTML → Plain text.
    
    This function handles formatting and sending messages with automatic fallback
    when Telegram cannot parse the formatting. It tries:
    1. Configured parse mode (usually Markdown)
    2. HTML if Markdown fails
    3. Plain text if HTML also fails
    
    Args:
        send_func: Async function to send message, signature: (text, parse_mode) -> None
        analysis_result: Raw analysis text from service
        period_hours: Analysis period in hours
        from_cache: Whether result is from cache
        config: Bot configuration
        
    Example:
        # For message.answer():
        await send_analysis_with_fallback(
            send_func=lambda text, pm: message.answer(text, parse_mode=pm),
            analysis_result=result,
            period_hours=6,
            from_cache=False,
            config=config
        )
        
        # For bot.send_message():
        await send_analysis_with_fallback(
            send_func=lambda text, pm: bot.send_message(chat_id=123, text=text, parse_mode=pm),
            analysis_result=result,
            period_hours=12,
            from_cache=True,
            config=config
        )
    """
    # Format result with configured parse mode
    formatted_result = MessageFormatter.format_analysis_result(
        analysis=analysis_result,
        period_hours=period_hours,
        from_cache=from_cache,
        parse_mode=config.default_parse_mode,
        max_length=config.max_message_length
    )
    
    # Handle both single string and list return from formatter
    if isinstance(formatted_result, str):
        messages_to_send = [formatted_result]
    else:
        messages_to_send = formatted_result
    
    # Send message(s) with three-tier fallback
    for idx, msg_text in enumerate(messages_to_send):
        try:
            # Tier 1: Try configured parse mode
            parse_mode_enum = get_parse_mode(config.default_parse_mode)
            await send_func(msg_text, parse_mode_enum)
            logger.debug(f"Message {idx + 1}/{len(messages_to_send)} sent successfully")
            
        except TelegramBadRequest as e:
            if "can't parse entities" in str(e).lower():
                # Tier 2: Fallback to HTML
                logger.warning(f"Markdown parsing failed, trying HTML: {e}")
                try:
                    html_result = MessageFormatter.format_analysis_result(
                        analysis=analysis_result,
                        period_hours=period_hours,
                        from_cache=from_cache,
                        parse_mode="HTML",
                        max_length=config.max_message_length
                    )
                    
                    if isinstance(html_result, str):
                        html_messages = [html_result]
                    else:
                        html_messages = html_result
                    
                    html_text = html_messages[idx] if idx < len(html_messages) else html_messages[0]
                    
                    await send_func(html_text, ParseMode.HTML)
                    logger.info("Message sent with HTML fallback")
                    
                except TelegramBadRequest as html_error:
                    # Tier 3: Final fallback to plain text
                    logger.error(f"HTML parsing also failed, using plain text: {html_error}")
                    
                    plain_result = MessageFormatter.format_analysis_result(
                        analysis=analysis_result,
                        period_hours=period_hours,
                        from_cache=from_cache,
                        parse_mode=None,
                        max_length=config.max_message_length
                    )
                    
                    if isinstance(plain_result, str):
                        plain_messages = [plain_result]
                    else:
                        plain_messages = plain_result
                    
                    plain_text = plain_messages[idx] if idx < len(plain_messages) else plain_messages[0]
                    
                    await send_func(plain_text, None)
                    logger.info("Message sent with plain text fallback")
            else:
                raise
