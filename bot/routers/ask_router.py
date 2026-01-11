"""Router for handling inline questions to the bot."""

import logging
import re
from aiogram import Router, Bot, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType
from aiogram.dispatcher.event.bases import SkipHandler

from services.analysis_service import AnalysisService
from openai_client.client import OpenAIClient
from utils.message_formatter import MessageFormatter
from utils.telegram_sender import safe_reply
from config.settings import Config


logger = logging.getLogger(__name__)

# Global variable to store bot username
_bot_username: str = ""


async def _get_bot_username(bot: Bot) -> str:
    """Get and cache bot username."""
    global _bot_username
    if not _bot_username:
        bot_info = await bot.get_me()
        _bot_username = bot_info.username or ""
    return _bot_username


def _check_bot_mention(text: str, bot_username: str) -> tuple[bool, str]:
    """
    Check if message contains bot mention.
    
    Returns:
        Tuple (has_mention, text_without_mention)
    """
    if not bot_username or not text:
        return False, ""
    
    # Search for mention anywhere in text
    mention_pattern = rf'@{re.escape(bot_username)}\b'
    match = re.search(mention_pattern, text, re.IGNORECASE)
    
    if match:
        # Remove mention from text
        question = (text[:match.start()] + text[match.end():]).strip()
        return True, question
    
    return False, ""


async def _handle_question(
    message: Message,
    question: str,
    analysis_service: AnalysisService,
    config: Config,
    is_admin: bool
) -> None:
    """
    Common question handling logic.
    
    Args:
        message: User message
        question: Question text
        analysis_service: Analysis service
        config: Bot configuration
        is_admin: Whether user is admin
    """
    from datetime import datetime, timezone
    
    # Get context from quoted message (if any)
    reply_context = None
    reply_timestamp = None
    
    if message.reply_to_message:
        reply_msg = message.reply_to_message
        reply_username = reply_msg.from_user.username or reply_msg.from_user.first_name or "Unknown"
        reply_text = reply_msg.text or reply_msg.caption or ""
        if reply_text:
            reply_context = f"@{reply_username}: {reply_text}"
            # Get timestamp of quoted message
            if reply_msg.date:
                reply_timestamp = reply_msg.date.replace(tzinfo=timezone.utc)
            logger.debug(
                "Found reply context",
                extra={
                    "reply_user": reply_username,
                    "reply_text_length": len(reply_text),
                    "reply_timestamp": reply_timestamp.isoformat() if reply_timestamp else None
                }
            )
    
    # Show processing message
    processing_msg = await message.answer("🤔 Думаю над ответом...")
    
    try:
        # Call service with debounce protection
        answer = await analysis_service.answer_question_with_debounce(
            question=question,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            reply_context=reply_context,
            reply_timestamp=reply_timestamp,
            bypass_debounce=is_admin
        )
        
        # Delete processing message
        await processing_msg.delete()
        
        # Send reply with fallback on parsing error
        try:
            await safe_reply(message, answer, parse_mode="Markdown")
        except Exception as parse_error:
            logger.warning(f"Markdown parsing error, trying HTML: {parse_error}")
            try:
                html_answer = MessageFormatter.convert_to_html(answer)
                await safe_reply(message, html_answer, parse_mode="HTML")
            except Exception as html_error:
                logger.warning(f"HTML parsing error, sending plain text: {html_error}")
                plain_answer = MessageFormatter.strip_formatting(answer)
                await safe_reply(message, plain_answer)
        
        logger.info(
            "Question processed successfully",
            extra={
                "user_id": message.from_user.id,
                "chat_id": message.chat.id,
                "answer_length": len(answer)
            }
        )
        
    except ValueError as e:
        # Handle debounce
        error_msg = str(e)
        try:
            remaining_seconds = float(error_msg)
            warning_msg = MessageFormatter.format_debounce_warning("задавал вопрос", remaining_seconds)
            await processing_msg.edit_text(warning_msg, parse_mode="Markdown")
        except Exception:
            await processing_msg.edit_text(f"⚠️ {error_msg}")
        
        logger.debug(
            "Question blocked by debounce",
            extra={
                "user_id": message.from_user.id,
                "chat_id": message.chat.id
            }
        )


def create_ask_router(config: Config) -> Router:
    """
    Create and configure router for /ask command and bot mentions.
    
    Args:
        config: Bot configuration
        
    Returns:
        Configured router instance
    """
    router = Router(name="ask_router")
    
    @router.message(
        Command("ask"),
        lambda message: message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]
    )
    async def cmd_ask(
        message: Message,
        analysis_service: AnalysisService,
        config: Config
    ):
        """
        Handle /ask command for answering questions.
        
        Usage:
            /ask <question> - ask bot a question
            Reply to message with /ask <question> - question with reply context
            
        Args:
            message: Command message
            analysis_service: Analysis service
            config: Bot configuration
        """
        try:
            # Check if user is admin
            is_admin = message.from_user.id == config.admin_id
            
            # Extract question from message
            command_text = message.text or ""
            # Remove /ask command from beginning
            question = command_text.split(maxsplit=1)[1] if len(command_text.split()) > 1 else ""
            
            if not question.strip():
                await message.answer(
                    "❓ Укажите вопрос после команды.\n"
                    "Использование: `/ask ваш вопрос`",
                    parse_mode="Markdown"
                )
                return
            
            logger.info(
                "Received /ask command",
                extra={
                    "user_id": message.from_user.id,
                    "chat_id": message.chat.id,
                    "is_admin": is_admin,
                    "question_length": len(question)
                }
            )
            
            await _handle_question(message, question, analysis_service, config, is_admin)
                
        except Exception as e:
            logger.error(
                f"Error in /ask command: {e}",
                extra={
                    "user_id": message.from_user.id if message.from_user else None,
                    "chat_id": message.chat.id if message.chat else None
                },
                exc_info=True
            )
            try:
                await message.answer("❌ Произошла ошибка при обработке вопроса.")
            except Exception:
                pass
    
    @router.message(
        F.text,
        F.reply_to_message,
        lambda message: message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]
    )
    async def handle_reply_to_bot(
        message: Message,
        bot: Bot,
        analysis_service: AnalysisService,
        config: Config
    ):
        """
        Handle reply to bot message.
        
        Usage:
            Reply to bot message with question text
            
        Args:
            message: Reply message
            bot: Bot instance
            analysis_service: Analysis service
            config: Bot configuration
        """
        try:
            text = message.text or ""
            
            # Ignore commands (starting with /)
            if text.startswith('/'):
                raise SkipHandler()
            
            # Check that this is reply to bot message
            reply_msg = message.reply_to_message
            bot_info = await bot.get_me()
            
            if not reply_msg.from_user or reply_msg.from_user.id != bot_info.id:
                # This is not reply to bot message - skip
                raise SkipHandler()
            
            # Check if there's bot mention (to avoid duplication with handle_mention)
            bot_username = await _get_bot_username(bot)
            if bot_username:
                has_mention, _ = _check_bot_mention(text, bot_username)
                if has_mention:
                    # Has mention - let handle_mention process it
                    raise SkipHandler()
            
            question = text.strip()
            
            if not question:
                raise SkipHandler()
            
            # Check if user is admin
            is_admin = message.from_user.id == config.admin_id
            
            logger.info(
                "Received reply to bot message",
                extra={
                    "user_id": message.from_user.id,
                    "chat_id": message.chat.id,
                    "is_admin": is_admin,
                    "question_length": len(question)
                }
            )
            
            await _handle_question(message, question, analysis_service, config, is_admin)
        
        except SkipHandler:
            raise
                
        except Exception as e:
            logger.error(
                f"Error handling reply to bot message: {e}",
                extra={
                    "user_id": message.from_user.id if message.from_user else None,
                    "chat_id": message.chat.id if message.chat else None
                },
                exc_info=True
            )
    
    @router.message(
        F.text,
        lambda message: message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]
    )
    async def handle_mention(
        message: Message,
        bot: Bot,
        analysis_service: AnalysisService,
        config: Config
    ):
        """
        Handle bot mention via @username.
        
        Usage:
            @botname question - ask bot a question
            Reply to message with @botname question - question with reply context
            
        Args:
            message: Message with mention
            bot: Bot instance
            analysis_service: Analysis service
            config: Bot configuration
        """
        try:
            text = message.text or ""
            
            # Ignore commands (starting with /)
            if text.startswith('/'):
                raise SkipHandler()
            
            # Get bot username
            bot_username = await _get_bot_username(bot)
            
            if not bot_username:
                raise SkipHandler()
            
            # Check bot mention
            has_mention, question = _check_bot_mention(text, bot_username)
            
            if not has_mention:
                # Not our message - skip to other handlers
                raise SkipHandler()
            
            if not question:
                await message.answer(
                    "❓ Укажите вопрос после упоминания.\n"
                    f"Использование: `@{bot_username} ваш вопрос`",
                    parse_mode="Markdown"
                )
                return
            
            # Check if user is admin
            is_admin = message.from_user.id == config.admin_id
            
            logger.info(
                "Received bot mention",
                extra={
                    "user_id": message.from_user.id,
                    "chat_id": message.chat.id,
                    "is_admin": is_admin,
                    "question_length": len(question)
                }
            )
            
            await _handle_question(message, question, analysis_service, config, is_admin)
        
        except SkipHandler:
            # Normal behavior - message not for us, skip without logging
            raise
                
        except Exception as e:
            logger.error(
                f"Error handling mention: {e}",
                extra={
                    "user_id": message.from_user.id if message.from_user else None,
                    "chat_id": message.chat.id if message.chat else None
                },
                exc_info=True
            )
    
    @router.message(
        Command("ask"),
        lambda message: message.chat.type == ChatType.PRIVATE,
        lambda message: message.from_user.id == config.admin_id
    )
    async def cmd_ask_private(
        message: Message,
        openai_client: OpenAIClient,
        config: Config
    ):
        """
        Handle /ask command in admin's private chat (without context).
        
        Args:
            message: Command message
            openai_client: OpenAI client
            config: Bot configuration
        """
        try:
            # Extract question from message
            command_text = message.text or ""
            question = command_text.split(maxsplit=1)[1] if len(command_text.split()) > 1 else ""
            
            if not question.strip():
                await message.answer(
                    "❓ Укажите вопрос после команды.\n"
                    "Использование: `/ask ваш вопрос`",
                    parse_mode="Markdown"
                )
                return
            
            logger.info(
                "Received /ask command in private chat",
                extra={
                    "user_id": message.from_user.id,
                    "question_length": len(question)
                }
            )
            
            # Show processing message
            processing_msg = await message.answer("🤔 Думаю над ответом...")
            
            try:
                # Call OpenAI directly without context
                answer = await openai_client.answer_question_simple(question)
                
                # Delete processing message
                await processing_msg.delete()
                
                # Send reply with fallback on parsing error
                try:
                    await safe_reply(message, answer, parse_mode="Markdown")
                except Exception as parse_error:
                    logger.warning(f"Markdown parsing error, trying HTML: {parse_error}")
                    try:
                        html_answer = MessageFormatter.convert_to_html(answer)
                        await safe_reply(message, html_answer, parse_mode="HTML")
                    except Exception as html_error:
                        logger.warning(f"HTML parsing error, sending plain text: {html_error}")
                        plain_answer = MessageFormatter.strip_formatting(answer)
                        await safe_reply(message, plain_answer)
                
                logger.info(
                    "/ask command in private chat completed",
                    extra={
                        "user_id": message.from_user.id,
                        "answer_length": len(answer)
                    }
                )
                
            except Exception as e:
                logger.error(f"Error generating answer: {e}", exc_info=True)
                await processing_msg.edit_text("❌ Ошибка при генерации ответа.")
                
        except Exception as e:
            logger.error(
                f"Error in /ask command (private chat): {e}",
                extra={"user_id": message.from_user.id if message.from_user else None},
                exc_info=True
            )
            try:
                await message.answer("❌ Произошла ошибка при обработке вопроса.")
            except Exception:
                pass
    
    return router
