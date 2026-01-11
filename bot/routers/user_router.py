"""Router for handling user-initiated analysis commands."""

import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType

from services.analysis_service import AnalysisService
from utils.telegram_sender import send_analysis_with_fallback, safe_reply
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
        
        Analyzes messages from the configured analysis period (default 8 hours).
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
                
                # Send result with fallback mechanism (reply to original message)
                await send_analysis_with_fallback(
                    send_func=lambda text, pm: safe_reply(message, text, pm),
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
                    warning_msg = MessageFormatter.format_debounce_warning("анализировал", remaining_seconds)
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
    
    
    return router
