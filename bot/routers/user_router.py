"""Router for handling user-initiated analysis commands."""

import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType

from services.analysis_service import AnalysisService
from utils.telegram_sender import send_analysis_with_fallback
from utils.message_formatter import MessageFormatter
from config.settings import Config


logger = logging.getLogger(__name__)


def create_user_router(config: Config) -> Router:
    """
    Create and configure the user router with analysis command handlers.
    
    Args:
        config: Bot configuration
        
    Returns:
        Configured router instance
    """
    # Create router for user commands
    router = Router(name="user_router")
    
    
    @router.message(
        Command("anal"),
        lambda message: message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]
    )
    async def cmd_anal(
        message: Message,
        analysis_service: AnalysisService,
        config: Config
    ):
        """
        Handle /anal command for short-term analysis.
        
        Analyzes messages from the configured short analysis period (default 6 hours).
        Regular users are subject to debounce protection, admins bypass it.
        
        Args:
            message: Command message from user
            analysis_service: Service for message analysis
            config: Bot configuration
        """
        try:
            # Check if user is admin
            is_admin = message.from_user.id == config.admin_id
            
            logger.info(
                "/anal command received",
                extra={
                    "user_id": message.from_user.id,
                    "chat_id": message.chat.id,
                    "is_admin": is_admin
                }
            )
            
            # Show processing message
            processing_msg = await message.answer("⏳ Анализирую сообщения...")
            
            try:
                # Call analysis service with debounce protection
                result, from_cache = await analysis_service.analyze_messages_with_debounce(
                    hours=config.anal_period_hours,
                    chat_id=message.chat.id,
                    user_id=message.from_user.id,
                    operation_type="anal",
                    bypass_debounce=is_admin
                )
                
                # Delete processing message
                await processing_msg.delete()
                
                # Send result with fallback mechanism
                await send_analysis_with_fallback(
                    send_func=lambda text, pm: message.answer(text, parse_mode=pm),
                    analysis_result=result,
                    period_hours=config.anal_period_hours,
                    from_cache=from_cache,
                    config=config
                )
                
                logger.info(
                    "/anal command completed",
                    extra={
                        "user_id": message.from_user.id,
                        "chat_id": message.chat.id,
                        "from_cache": from_cache
                    }
                )
                
            except ValueError as e:
                # Handle debounce rejection
                error_msg = str(e)
                # Extract remaining seconds from error message
                # Expected format: just a number (seconds as string)
                try:
                    remaining_seconds = float(error_msg)
                    warning_msg = MessageFormatter.format_debounce_warning("анализ", remaining_seconds)
                    await processing_msg.edit_text(warning_msg, parse_mode="Markdown")
                except Exception:
                    # Fallback if parsing fails
                    await processing_msg.edit_text(f"⚠️ {error_msg}")
                
                logger.debug(
                    "/anal command debounced",
                    extra={
                        "user_id": message.from_user.id,
                        "chat_id": message.chat.id
                    }
                )
                
        except Exception as e:
            logger.error(
                f"Error in /anal command: {e}",
                extra={
                    "user_id": message.from_user.id if message.from_user else None,
                    "chat_id": message.chat.id if message.chat else None
                },
                exc_info=True
            )
            try:
                await message.answer("❌ Произошла ошибка при выполнении команды.")
            except Exception:
                pass
    
    
    @router.message(
        Command("deep_anal"),
        lambda message: message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]
    )
    async def cmd_deep_anal(
        message: Message,
        analysis_service: AnalysisService,
        config: Config
    ):
        """
        Handle /deep_anal command for extended analysis.
        
        Analyzes messages from the configured deep analysis period (default 12 hours).
        Regular users are subject to debounce protection, admins bypass it.
        
        Args:
            message: Command message from user
            analysis_service: Service for message analysis
            config: Bot configuration
        """
        try:
            # Check if user is admin
            is_admin = message.from_user.id == config.admin_id
            
            logger.info(
                "/deep_anal command received",
                extra={
                    "user_id": message.from_user.id,
                    "chat_id": message.chat.id,
                    "is_admin": is_admin
                }
            )
            
            # Show processing message
            processing_msg = await message.answer("⏳ Анализирую сообщения...")
            
            try:
                # Call analysis service with debounce protection
                result, from_cache = await analysis_service.analyze_messages_with_debounce(
                    hours=config.deep_anal_period_hours,
                    chat_id=message.chat.id,
                    user_id=message.from_user.id,
                    operation_type="deep_anal",
                    bypass_debounce=is_admin
                )
                
                # Delete processing message
                await processing_msg.delete()
                
                # Send result with fallback mechanism
                await send_analysis_with_fallback(
                    send_func=lambda text, pm: message.answer(text, parse_mode=pm),
                    analysis_result=result,
                    period_hours=config.deep_anal_period_hours,
                    from_cache=from_cache,
                    config=config
                )
                
                logger.info(
                    "/deep_anal command completed",
                    extra={
                        "user_id": message.from_user.id,
                        "chat_id": message.chat.id,
                        "from_cache": from_cache
                    }
                )
                
            except ValueError as e:
                # Handle debounce rejection
                error_msg = str(e)
                
                # Extract remaining seconds from error message
                # Expected format: just a number (seconds as string)
                try:
                    remaining_seconds = float(error_msg)
                    warning_msg = MessageFormatter.format_debounce_warning("глубокий анализ", remaining_seconds)
                    await processing_msg.edit_text(warning_msg, parse_mode="Markdown")
                except Exception:
                    # Fallback if parsing fails
                    await processing_msg.edit_text(f"⚠️ {error_msg}")
                
                logger.debug(
                    "/deep_anal command debounced",
                    extra={
                        "user_id": message.from_user.id,
                        "chat_id": message.chat.id
                    }
                )
                
        except Exception as e:
            logger.error(
                f"Error in /deep_anal command: {e}",
                extra={
                    "user_id": message.from_user.id if message.from_user else None,
                    "chat_id": message.chat.id if message.chat else None
                },
                exc_info=True
            )
            try:
                await message.answer("❌ Произошла ошибка при выполнении команды.")
            except Exception:
                pass
    
    
    @router.message(
        Command("horoscope"),
        lambda message: message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]
    )
    async def cmd_horoscope(
        message: Message,
        analysis_service: AnalysisService,
        config: Config
    ):
        """
        Handle /horoscope command for creating user's horoscope.
        
        Creates an ironic horoscope based on user's messages from the last 12 hours.
        Regular users are subject to debounce protection, admins bypass it.
        
        Args:
            message: Command message from user
            analysis_service: Service for message analysis
            config: Bot configuration
        """
        try:
            # Check if user is admin
            is_admin = message.from_user.id == config.admin_id
            
            # Get user info
            user_id = message.from_user.id
            username = message.from_user.username or message.from_user.first_name or "Unknown"
            
            logger.info(
                "/horoscope command received",
                extra={
                    "user_id": user_id,
                    "username": username,
                    "chat_id": message.chat.id,
                    "is_admin": is_admin
                }
            )
            
            # Show processing message
            processing_msg = await message.answer("🔮 Звезды изучают ваши сообщения...")
            
            try:
                # Call horoscope service with debounce protection
                result, from_cache = await analysis_service.create_horoscope_with_debounce(
                    user_id=user_id,
                    username=username,
                    chat_id=message.chat.id,
                    hours=12,  # Fixed 12 hours for horoscope
                    bypass_debounce=is_admin
                )
                
                # Delete processing message
                await processing_msg.delete()
                
                # Send result with fallback mechanism
                await send_analysis_with_fallback(
                    send_func=lambda text, pm: message.answer(text, parse_mode=pm),
                    analysis_result=result,
                    period_hours=12,
                    from_cache=from_cache,
                    config=config
                )
                
                logger.info(
                    "/horoscope command completed",
                    extra={
                        "user_id": user_id,
                        "username": username,
                        "chat_id": message.chat.id,
                        "from_cache": from_cache
                    }
                )
                
            except ValueError as e:
                # Handle debounce rejection
                error_msg = str(e)
                
                # Extract remaining seconds from error message
                try:
                    remaining_seconds = float(error_msg)
                    warning_msg = MessageFormatter.format_debounce_warning("гороскоп", remaining_seconds)
                    await processing_msg.edit_text(warning_msg, parse_mode="Markdown")
                except Exception:
                    # Fallback if parsing fails
                    await processing_msg.edit_text(f"⚠️ {error_msg}")
                
                logger.debug(
                    "/horoscope command debounced",
                    extra={
                        "user_id": user_id,
                        "username": username,
                        "chat_id": message.chat.id
                    }
                )
                
        except Exception as e:
            logger.error(
                f"Error in /horoscope command: {e}",
                extra={
                    "user_id": message.from_user.id if message.from_user else None,
                    "chat_id": message.chat.id if message.chat else None
                },
                exc_info=True
            )
            try:
                await message.answer("❌ Произошла ошибка при создании гороскопа.")
            except Exception:
                pass
    
    
    return router
