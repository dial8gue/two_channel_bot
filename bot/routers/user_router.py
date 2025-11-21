"""Router for handling user-initiated analysis commands."""

import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType

from services.analysis_service import AnalysisService
from utils.message_formatter import MessageFormatter, get_parse_mode
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
                
                # Format and send result
                formatted_result = MessageFormatter.format_analysis_result(
                    analysis=result,
                    period_hours=config.anal_period_hours,
                    from_cache=from_cache,
                    parse_mode=config.default_parse_mode,
                    max_length=config.max_message_length
                )
                
                # Delete processing message
                await processing_msg.delete()
                
                # Convert parse mode string to enum
                parse_mode_enum = get_parse_mode(config.default_parse_mode)
                
                # Send result (handle both string and list)
                if isinstance(formatted_result, str):
                    await message.answer(formatted_result, parse_mode=parse_mode_enum)
                else:
                    for msg_text in formatted_result:
                        await message.answer(msg_text, parse_mode=parse_mode_enum)
                
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
                
                # Format and send result
                formatted_result = MessageFormatter.format_analysis_result(
                    analysis=result,
                    period_hours=config.deep_anal_period_hours,
                    from_cache=from_cache,
                    parse_mode=config.default_parse_mode,
                    max_length=config.max_message_length
                )
                
                # Delete processing message
                await processing_msg.delete()
                
                # Convert parse mode string to enum
                parse_mode_enum = get_parse_mode(config.default_parse_mode)
                
                # Send result (handle both string and list)
                if isinstance(formatted_result, str):
                    await message.answer(formatted_result, parse_mode=parse_mode_enum)
                else:
                    for msg_text in formatted_result:
                        await message.answer(msg_text, parse_mode=parse_mode_enum)
                
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
    
    
    return router
