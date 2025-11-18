"""Router for handling administrative commands."""

import logging
from typing import Optional

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode

from bot.filters.admin_filter import IsAdminFilter
from services.analysis_service import AnalysisService
from services.admin_service import AdminService
from utils.message_formatter import MessageFormatter
from config.settings import Config


logger = logging.getLogger(__name__)


def _get_parse_mode(mode_str: str) -> ParseMode | None:
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


def create_admin_router(config: Config) -> Router:
    """
    Create and configure the admin router with all command handlers.
    
    Args:
        config: Bot configuration
        
    Returns:
        Configured router instance
    """
    # Create router for admin commands
    router = Router(name="admin_router")
    
    # Create admin filter instance
    admin_filter = IsAdminFilter(config)
    
    
    @router.message(Command("analyze"), admin_filter)
    async def cmd_analyze(
        message: Message,
        analysis_service: AnalysisService,
        config: Config
    ):
        """
        Handle /analyze command to analyze messages.
        
        Usage:
            /analyze - Analyze messages from default period
            /analyze 12 - Analyze messages from last 12 hours
            
        Args:
            message: Command message from admin
            analysis_service: Service for message analysis
            config: Bot configuration
        """
        try:
            # Parse optional hours parameter
            hours: Optional[int] = None
            if message.text and len(message.text.split()) > 1:
                try:
                    hours = int(message.text.split()[1])
                    if hours <= 0:
                        await message.answer("❌ Период должен быть положительным числом.")
                        return
                except ValueError:
                    await message.answer("❌ Неверный формат. Используйте: /analyze [часы]")
                    return
            
            # Send processing message
            processing_msg = await message.answer("⏳ Анализирую сообщения...")
            
            logger.info(
                "Analysis command received",
                extra={
                    "admin_id": message.from_user.id,
                    "hours": hours,
                    "chat_id": message.chat.id
                }
            )
            
            # Perform analysis
            try:
                analysis_result, from_cache = await analysis_service.analyze_messages(
                    hours=hours,
                    chat_id=None  # Analyze all chats
                )
                
                # Format result
                period_hours = hours or config.analysis_period_hours
                formatted_result = MessageFormatter.format_analysis_result(
                    analysis=analysis_result,
                    period_hours=period_hours,
                    from_cache=from_cache,
                    parse_mode=config.default_parse_mode,
                    max_length=config.max_message_length
                )
                
                # Determine where to send the result
                if config.debug_mode:
                    # Debug mode: send to admin in private chat
                    target_chat_id = message.from_user.id
                    logger.info("Sending analysis to admin (debug mode)")
                else:
                    # Normal mode: send to the group chat
                    # We need to get the group chat ID - for now, send to admin
                    # In production, this should be configured or detected
                    target_chat_id = message.from_user.id
                    logger.info("Sending analysis to admin (no group chat configured)")
                
                # Delete processing message
                await processing_msg.delete()
                
                # Handle both single string and list return from formatter
                if isinstance(formatted_result, str):
                    messages_to_send = [formatted_result]
                else:
                    messages_to_send = formatted_result
                
                # Send message(s) with three-tier fallback: Markdown → HTML → Plain text
                for idx, msg_text in enumerate(messages_to_send):
                    try:
                        # Tier 1: Try configured parse mode
                        parse_mode_enum = _get_parse_mode(config.default_parse_mode)
                        await message.bot.send_message(
                            chat_id=target_chat_id,
                            text=msg_text,
                            parse_mode=parse_mode_enum
                        )
                        logger.debug(f"Message {idx + 1}/{len(messages_to_send)} sent successfully with {config.default_parse_mode}")
                        
                    except TelegramBadRequest as e:
                        if "can't parse entities" in str(e).lower():
                            # Tier 2: Fallback to HTML
                            logger.warning(
                                f"Markdown parsing failed for message {idx + 1}/{len(messages_to_send)}, trying HTML: {e}",
                                extra={"error": str(e), "message_length": len(msg_text)}
                            )
                            try:
                                # Re-format the original analysis with HTML
                                html_result = MessageFormatter.format_analysis_result(
                                    analysis=analysis_result,
                                    period_hours=period_hours,
                                    from_cache=from_cache,
                                    parse_mode="HTML",
                                    max_length=config.max_message_length
                                )
                                
                                # Handle single string or list
                                if isinstance(html_result, str):
                                    html_messages = [html_result]
                                else:
                                    html_messages = html_result
                                
                                # Send the corresponding chunk
                                html_text = html_messages[idx] if idx < len(html_messages) else html_messages[0]
                                
                                await message.bot.send_message(
                                    chat_id=target_chat_id,
                                    text=html_text,
                                    parse_mode=ParseMode.HTML
                                )
                                logger.info(f"Message {idx + 1}/{len(messages_to_send)} sent successfully with HTML fallback")
                                
                            except TelegramBadRequest as html_error:
                                # Tier 3: Final fallback to plain text
                                logger.error(
                                    f"HTML parsing also failed for message {idx + 1}/{len(messages_to_send)}, using plain text: {html_error}",
                                    extra={"error": str(html_error), "message_length": len(msg_text)}
                                )
                                
                                # Re-format the original analysis with plain text
                                plain_result = MessageFormatter.format_analysis_result(
                                    analysis=analysis_result,
                                    period_hours=period_hours,
                                    from_cache=from_cache,
                                    parse_mode=None,
                                    max_length=config.max_message_length
                                )
                                
                                # Handle single string or list
                                if isinstance(plain_result, str):
                                    plain_messages = [plain_result]
                                else:
                                    plain_messages = plain_result
                                
                                # Send the corresponding chunk
                                plain_text = plain_messages[idx] if idx < len(plain_messages) else plain_messages[0]
                                
                                await message.bot.send_message(
                                    chat_id=target_chat_id,
                                    text=plain_text,
                                    parse_mode=None
                                )
                                logger.info(f"Message {idx + 1}/{len(messages_to_send)} sent successfully with plain text fallback")
                        else:
                            # Re-raise if it's a different error
                            raise
                
                logger.info(
                    "Analysis completed and sent",
                    extra={
                        "admin_id": message.from_user.id,
                        "period_hours": period_hours,
                        "from_cache": from_cache,
                        "target_chat_id": target_chat_id,
                        "message_count": len(messages_to_send)
                    }
                )
                
            except ValueError as e:
                # Debounce or validation error
                await processing_msg.delete()
                await message.answer(f"⚠️ {str(e)}")
                
            except Exception as e:
                logger.error(f"Analysis failed: {e}", exc_info=True)
                await processing_msg.delete()
                await message.answer(
                    "❌ Ошибка при анализе сообщений. Проверьте логи для деталей."
                )
                
        except Exception as e:
            logger.error(
                f"Error in analyze command: {e}",
                extra={"admin_id": message.from_user.id if message.from_user else None},
                exc_info=True
            )
            await message.answer("❌ Произошла ошибка при выполнении команды.")
    
    
    @router.message(Command("clear_db"), admin_filter)
    async def cmd_clear_db(message: Message, admin_service: AdminService):
        """
        Handle /clear_db command to clear all messages from database.
        
        Args:
            message: Command message from admin
            admin_service: Service for admin operations
        """
        try:
            logger.info(
                "Clear database command received",
                extra={"admin_id": message.from_user.id}
            )
            
            # Perform database clear
            await admin_service.clear_database()
            
            await message.answer("✅ База данных очищена.")
            
            logger.info(
                "Database cleared successfully",
                extra={"admin_id": message.from_user.id}
            )
            
        except Exception as e:
            logger.error(
                f"Error clearing database: {e}",
                extra={"admin_id": message.from_user.id if message.from_user else None},
                exc_info=True
            )
            await message.answer("❌ Ошибка при очистке базы данных.")
    
    
    @router.message(Command("set_storage"), admin_filter)
    async def cmd_set_storage(message: Message, admin_service: AdminService):
        """
        Handle /set_storage command to set storage period.
        
        Usage: /set_storage <hours>
        
        Args:
            message: Command message from admin
            admin_service: Service for admin operations
        """
        try:
            # Parse hours parameter
            if not message.text or len(message.text.split()) < 2:
                await message.answer(
                    "❌ Укажите период хранения в часах.\n"
                    "Использование: /set_storage <часы>"
                )
                return
            
            try:
                hours = int(message.text.split()[1])
            except ValueError:
                await message.answer("❌ Период должен быть числом.")
                return
            
            logger.info(
                "Set storage period command received",
                extra={"admin_id": message.from_user.id, "hours": hours}
            )
            
            # Set storage period
            await admin_service.set_storage_period(hours)
            
            await message.answer(f"✅ Период хранения установлен: {hours} часов.")
            
            logger.info(
                "Storage period updated",
                extra={"admin_id": message.from_user.id, "hours": hours}
            )
            
        except ValueError as e:
            await message.answer(f"❌ {str(e)}")
        except Exception as e:
            logger.error(
                f"Error setting storage period: {e}",
                extra={"admin_id": message.from_user.id if message.from_user else None},
                exc_info=True
            )
            await message.answer("❌ Ошибка при установке периода хранения.")
    
    
    @router.message(Command("set_analysis"), admin_filter)
    async def cmd_set_analysis(message: Message, admin_service: AdminService):
        """
        Handle /set_analysis command to set analysis period.
        
        Usage: /set_analysis <hours>
        
        Args:
            message: Command message from admin
            admin_service: Service for admin operations
        """
        try:
            # Parse hours parameter
            if not message.text or len(message.text.split()) < 2:
                await message.answer(
                    "❌ Укажите период анализа в часах.\n"
                    "Использование: /set_analysis <часы>"
                )
                return
            
            try:
                hours = int(message.text.split()[1])
            except ValueError:
                await message.answer("❌ Период должен быть числом.")
                return
            
            logger.info(
                "Set analysis period command received",
                extra={"admin_id": message.from_user.id, "hours": hours}
            )
            
            # Set analysis period
            await admin_service.set_analysis_period(hours)
            
            await message.answer(f"✅ Период анализа установлен: {hours} часов.")
            
            logger.info(
                "Analysis period updated",
                extra={"admin_id": message.from_user.id, "hours": hours}
            )
            
        except ValueError as e:
            await message.answer(f"❌ {str(e)}")
        except Exception as e:
            logger.error(
                f"Error setting analysis period: {e}",
                extra={"admin_id": message.from_user.id if message.from_user else None},
                exc_info=True
            )
            await message.answer("❌ Ошибка при установке периода анализа.")
    
    
    @router.message(Command("stop_collection"), admin_filter)
    async def cmd_stop_collection(message: Message, admin_service: AdminService):
        """
        Handle /stop_collection command to stop message collection.
        
        Args:
            message: Command message from admin
            admin_service: Service for admin operations
        """
        try:
            logger.info(
                "Stop collection command received",
                extra={"admin_id": message.from_user.id}
            )
            
            # Disable collection
            await admin_service.toggle_collection(enabled=False)
            
            await message.answer("✅ Сбор сообщений остановлен.")
            
            logger.info(
                "Message collection stopped",
                extra={"admin_id": message.from_user.id}
            )
            
        except Exception as e:
            logger.error(
                f"Error stopping collection: {e}",
                extra={"admin_id": message.from_user.id if message.from_user else None},
                exc_info=True
            )
            await message.answer("❌ Ошибка при остановке сбора сообщений.")
    
    
    @router.message(Command("start_collection"), admin_filter)
    async def cmd_start_collection(message: Message, admin_service: AdminService):
        """
        Handle /start_collection command to start message collection.
        
        Args:
            message: Command message from admin
            admin_service: Service for admin operations
        """
        try:
            logger.info(
                "Start collection command received",
                extra={"admin_id": message.from_user.id}
            )
            
            # Enable collection
            await admin_service.toggle_collection(enabled=True)
            
            await message.answer("✅ Сбор сообщений запущен.")
            
            logger.info(
                "Message collection started",
                extra={"admin_id": message.from_user.id}
            )
            
        except Exception as e:
            logger.error(
                f"Error starting collection: {e}",
                extra={"admin_id": message.from_user.id if message.from_user else None},
                exc_info=True
            )
            await message.answer("❌ Ошибка при запуске сбора сообщений.")
    
    
    @router.message(Command("stats"), admin_filter)
    async def cmd_stats(message: Message, admin_service: AdminService):
        """
        Handle /stats command to get database statistics.
        
        Args:
            message: Command message from admin
            admin_service: Service for admin operations
        """
        try:
            logger.info(
                "Stats command received",
                extra={"admin_id": message.from_user.id}
            )
            
            # Get statistics
            stats = await admin_service.get_stats()
            
            # Format statistics
            formatted_stats = MessageFormatter.format_stats(stats)
            
            await message.answer(formatted_stats, parse_mode=ParseMode.MARKDOWN)
            
            logger.info(
                "Statistics sent",
                extra={
                    "admin_id": message.from_user.id,
                    "total_messages": stats.get('total_messages', 0)
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error getting statistics: {e}",
                extra={"admin_id": message.from_user.id if message.from_user else None},
                exc_info=True
            )
            await message.answer("❌ Ошибка при получении статистики.")
    
    
    return router
