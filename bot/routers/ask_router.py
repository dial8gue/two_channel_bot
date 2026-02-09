"""Router for handling inline questions to the bot."""

import asyncio
import logging
import re
from aiogram import Router, Bot, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType
from aiogram.dispatcher.event.bases import SkipHandler

from services.analysis_service import AnalysisService
from openai_client.client import OpenAIClient, OpenAIClientError
from utils.message_formatter import MessageFormatter
from utils.telegram_sender import safe_reply, typing_loop
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


async def _extract_image_description(message: Message, openai_client: OpenAIClient) -> str | None:
    """
    Extract and describe image from message or its reply.
    
    Checks for photo/sticker in the message itself first, then in the replied message.
    Downloads the largest available photo (or sticker thumbnail) and sends it to the vision model.
    
    Args:
        message: Telegram message (may contain photo, sticker, or reply to photo/sticker)
        openai_client: OpenAI client with vision support
        
    Returns:
        Image description string or None if no image found
    """
    # Determine which message has the photo, sticker, animation, or video
    photo_message = None
    sticker_message = None
    animation_message = None
    video_message = None
    
    if message.photo:
        photo_message = message
    elif message.sticker:
        sticker_message = message
    elif message.animation:
        animation_message = message
    elif message.video:
        video_message = message
    elif message.reply_to_message:
        if message.reply_to_message.photo:
            photo_message = message.reply_to_message
        elif message.reply_to_message.sticker:
            sticker_message = message.reply_to_message
        elif message.reply_to_message.animation:
            animation_message = message.reply_to_message
        elif message.reply_to_message.video:
            video_message = message.reply_to_message
    
    if not photo_message and not sticker_message and not animation_message and not video_message:
        return None
    
    try:
        from io import BytesIO
        
        if photo_message:
            # Get the largest photo (last in the list)
            photo = photo_message.photo[-1]
            
            logger.info(
                "Downloading image for vision",
                extra={
                    "file_id": photo.file_id,
                    "width": photo.width,
                    "height": photo.height,
                    "file_size": photo.file_size
                }
            )
            
            buf = BytesIO()
            await message.bot.download(photo, destination=buf)
            image_data = buf.getvalue()
        elif sticker_message:
            # Sticker — use thumbnail
            sticker = sticker_message.sticker
            if not sticker.thumbnail:
                # No thumbnail available, return emoji fallback
                emoji = sticker.emoji or ""
                return f"Стикер {emoji}"
            
            logger.info(
                "Downloading sticker thumbnail for vision",
                extra={
                    "file_id": sticker.thumbnail.file_id,
                    "sticker_emoji": sticker.emoji,
                    "sticker_set": sticker.set_name
                }
            )
            
            buf = BytesIO()
            await message.bot.download(sticker.thumbnail, destination=buf)
            image_data = buf.getvalue()
        elif animation_message:
            # Animation (GIF) — use thumbnail
            animation = animation_message.animation
            if not animation.thumbnail:
                return "[GIF]"
            
            logger.info(
                "Downloading animation thumbnail for vision",
                extra={
                    "file_id": animation.thumbnail.file_id,
                    "file_name": animation.file_name
                }
            )
            
            buf = BytesIO()
            await message.bot.download(animation.thumbnail, destination=buf)
            image_data = buf.getvalue()
        elif video_message:
            # Video — use thumbnail
            video = video_message.video
            if not video.thumbnail:
                return "[Видео]"
            
            logger.info(
                "Downloading video thumbnail for vision",
                extra={
                    "file_id": video.thumbnail.file_id,
                    "file_name": video.file_name,
                    "duration": video.duration
                }
            )
            
            buf = BytesIO()
            await message.bot.download(video.thumbnail, destination=buf)
            image_data = buf.getvalue()
        
        # Send to vision model for description
        description = await openai_client.describe_image(image_data)
        
        logger.info(
            "Image described successfully",
            extra={"description_length": len(description)}
        )
        
        return description
        
    except OpenAIClientError as e:
        logger.warning(f"Failed to describe image: {e}")
        return None
    except Exception as e:
        logger.error(f"Error extracting image: {e}", exc_info=True)
        return None


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
    
    # Get username of the person asking
    asking_user = message.from_user.username or message.from_user.first_name or None
    
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
    
    # Start typing indicator
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(typing_loop(message.chat.id, message.bot, stop_typing))
    
    try:
        # Try to extract and describe image if vision is enabled
        image_description = None
        openai_client = analysis_service.openai_client
        
        if openai_client.vision_enabled:
            image_description = await _extract_image_description(message, openai_client)
        
        # Call service with debounce protection
        answer = await analysis_service.answer_question_with_debounce(
            question=question,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            reply_context=reply_context,
            reply_timestamp=reply_timestamp,
            bypass_debounce=is_admin,
            asking_user=asking_user,
            image_description=image_description
        )
        
        # Stop typing indicator
        stop_typing.set()
        typing_task.cancel()
        
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
        # Stop typing indicator
        stop_typing.set()
        typing_task.cancel()
        
        # Handle debounce
        error_msg = str(e)
        try:
            remaining_seconds = float(error_msg)
            warning_msg = MessageFormatter.format_debounce_warning("задавал вопрос", remaining_seconds)
            await message.answer(warning_msg, parse_mode="Markdown")
        except Exception:
            await message.answer(f"⚠️ {error_msg}")
        
        logger.debug(
            "Question blocked by debounce",
            extra={
                "user_id": message.from_user.id,
                "chat_id": message.chat.id
            }
        )
    except Exception:
        # Stop typing indicator on any error
        stop_typing.set()
        typing_task.cancel()
        raise


async def _handle_private_question(
    message: Message,
    question: str,
    openai_client: OpenAIClient
) -> None:
    """
    Common logic for answering questions in admin's private chat (without group context).
    Supports image recognition via vision when photo is attached.
    
    Args:
        message: User message
        question: Question text
        openai_client: OpenAI client
    """
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(typing_loop(message.chat.id, message.bot, stop_typing))
    
    try:
        # Try to extract and describe image if vision is enabled
        image_description = None
        if openai_client.vision_enabled:
            image_description = await _extract_image_description(message, openai_client)
        
        # Build full question with image context
        if image_description:
            full_question = f"{question}\n\n[Изображение: {image_description}]"
        else:
            full_question = question
        
        answer = await openai_client.answer_question_simple(full_question)
        
        stop_typing.set()
        typing_task.cancel()
        
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
            "Private question answered",
            extra={
                "user_id": message.from_user.id,
                "answer_length": len(answer)
            }
        )
        
    except Exception:
        stop_typing.set()
        typing_task.cancel()
        raise


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
            Send photo with caption /ask <question> - question with image context
            
        Args:
            message: Command message
            analysis_service: Analysis service
            config: Bot configuration
        """
        try:
            # Check if user is admin
            is_admin = message.from_user.id == config.admin_id
            
            # Extract question from message (text or caption for photos)
            command_text = message.text or message.caption or ""
            # Remove /ask command from beginning
            question = command_text.split(maxsplit=1)[1] if len(command_text.split()) > 1 else ""
            
            # If no question text but there's a photo, sticker, or GIF, use default prompt
            if not question.strip() and (message.photo or message.sticker or message.animation):
                question = "Что на этом изображении?"
            
            if not question.strip():
                await message.answer(
                    "❓ Укажи вопрос после команды.\n"
                    "Использование: `/ask твой вопрос`",
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
        F.reply_to_message,
        lambda message: message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP],
        lambda message: message.text or (message.photo and message.caption) or message.sticker or message.animation
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
            Reply to bot message with photo + caption
            Reply to bot message with sticker
            
        Args:
            message: Reply message
            bot: Bot instance
            analysis_service: Analysis service
            config: Bot configuration
        """
        try:
            text = message.text or message.caption or ""
            
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
            
            # If photo, sticker, or GIF without text, use default question
            if not question and (message.photo or message.sticker or message.animation):
                question = "Что на этом изображении?"
            
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
        lambda message: message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP],
        lambda message: message.text or (message.photo and message.caption) or message.sticker or message.animation
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
            Send photo with caption @botname question - question with image context
            Send sticker as reply to @botname - question with sticker context
            
        Args:
            message: Message with mention
            bot: Bot instance
            analysis_service: Analysis service
            config: Bot configuration
        """
        try:
            text = message.text or message.caption or ""
            
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
            
            if not question and (message.photo or message.sticker or message.animation):
                question = "Что на этом изображении?"
            
            if not question:
                await message.answer(
                    "❓ Укажи вопрос после упоминания.\n"
                    f"Использование: `@{bot_username} твой вопрос`",
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
            command_text = message.text or ""
            question = command_text.split(maxsplit=1)[1] if len(command_text.split()) > 1 else ""
            
            if not question.strip():
                await message.answer(
                    "❓ Укажи вопрос после команды.\n"
                    "Использование: `/ask твой вопрос`",
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
            
            await _handle_private_question(message, question, openai_client)
                
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

    @router.message(
        lambda message: message.chat.type == ChatType.PRIVATE,
        lambda message: message.from_user and message.from_user.id == config.admin_id,
        lambda message: (message.text and not message.text.startswith('/')) or message.photo or message.sticker or message.animation
    )
    async def handle_private_text(
        message: Message,
        openai_client: OpenAIClient,
        config: Config
    ):
        """
        Handle plain text or photo messages in admin's private chat as questions.
        
        Args:
            message: Text or photo message from admin
            openai_client: OpenAI client
            config: Bot configuration
        """
        try:
            question = (message.text or message.caption or "").strip()
            
            # If photo/sticker/GIF without text, use default prompt
            if not question and (message.photo or message.sticker or message.animation):
                question = "Что на этом изображении?"
            
            if not question:
                return
            
            logger.info(
                "Received message in private chat",
                extra={
                    "user_id": message.from_user.id,
                    "question_length": len(question),
                    "has_photo": bool(message.photo)
                }
            )
            
            await _handle_private_question(message, question, openai_client)
                
        except Exception as e:
            logger.error(
                f"Error handling private text: {e}",
                extra={"user_id": message.from_user.id if message.from_user else None},
                exc_info=True
            )
            try:
                await message.answer("❌ Произошла ошибка при обработке вопроса.")
            except Exception:
                pass

    return router
