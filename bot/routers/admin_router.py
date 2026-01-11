"""Router for handling administrative commands."""

import logging
from typing import Optional

from aiogram import Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode, ChatType

from bot.filters.admin_filter import IsAdminFilter
from services.analysis_service import AnalysisService
from services.admin_service import AdminService
from services.message_service import MessageService
from utils.message_formatter import MessageFormatter
from utils.telegram_sender import send_analysis_with_fallback, safe_reply
from config.settings import Config


logger = logging.getLogger(__name__)


async def _perform_analysis_and_send(
    bot,
    target_chat_id: int,
    analysis_service: AnalysisService,
    config: Config,
    hours: Optional[int],
    chat_id_to_analyze: Optional[int],
    admin_id: int
):
    """
    Helper function to perform analysis and send results with fallback formatting.
    
    Args:
        bot: Bot instance
        target_chat_id: Where to send the result
        analysis_service: Service for analysis
        config: Bot configuration
        hours: Hours to analyze
        chat_id_to_analyze: Chat ID to analyze (None for all)
        admin_id: Admin user ID for logging
    """
    # Perform analysis with debounce bypass for admin
    # Use chat_id_to_analyze or 0 for operation key (0 means "all chats")
    operation_chat_id = chat_id_to_analyze if chat_id_to_analyze is not None else 0
    
    analysis_result, from_cache = await analysis_service.analyze_messages_with_debounce(
        hours=hours or config.analysis_period_hours,
        chat_id=operation_chat_id,
        user_id=admin_id,
        operation_type="admin_analyze",
        bypass_debounce=True  # Admin bypasses debounce
    )
    
    # Send result with fallback mechanism
    period_hours = hours or config.analysis_period_hours
    await send_analysis_with_fallback(
        send_func=lambda text, pm: bot.send_message(chat_id=target_chat_id, text=text, parse_mode=pm),
        analysis_result=analysis_result,
        period_hours=period_hours,
        from_cache=from_cache,
        config=config
    )
    
    logger.info(
        "Analysis completed and sent",
        extra={
            "admin_id": admin_id,
            "period_hours": period_hours,
            "from_cache": from_cache,
            "target_chat_id": target_chat_id,
            "chat_id_analyzed": chat_id_to_analyze
        }
    )


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
        message_service: MessageService,
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
            message_service: Service for message operations
            config: Bot configuration
        """
        try:
            # Parse optional hours parameter
            hours: Optional[int] = None
            if message.text and len(message.text.split()) > 1:
                try:
                    hours = int(message.text.split()[1])
                    if hours <= 0 or hours > 24:
                        await message.answer("❌ Период должен быть положительным числом от 1 до 24.")
                        return
                except ValueError:
                    await message.answer("❌ Неверный формат. Используйте: /analyze [часы]")
                    return
            
            logger.info(
                "Analysis command received",
                extra={
                    "admin_id": message.from_user.id,
                    "hours": hours,
                    "chat_id": message.chat.id,
                    "chat_type": message.chat.type
                }
            )
            
            # Determine which chat to analyze based on where command was sent
            if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                # Command from group - analyze this group directly
                chat_id_to_analyze = message.chat.id
                logger.debug(f"Analyzing group chat: {chat_id_to_analyze}")
                
                processing_msg = await message.answer("⏳ Анализирую сообщения...")
                
                try:
                    await _perform_analysis_and_send(
                        bot=message.bot,
                        target_chat_id=message.from_user.id if config.debug_mode else message.chat.id,
                        analysis_service=analysis_service,
                        config=config,
                        hours=hours,
                        chat_id_to_analyze=chat_id_to_analyze,
                        admin_id=message.from_user.id
                    )
                    await processing_msg.delete()
                    
                except ValueError as e:
                    await processing_msg.delete()
                    await message.answer(f"⚠️ {str(e)}")
                    
                except Exception as e:
                    logger.error(f"Analysis failed: {e}", exc_info=True)
                    await processing_msg.delete()
                    await message.answer("❌ Ошибка при анализе сообщений. Проверьте логи для деталей.")
                    
            else:
                # Command from private chat - show chat selection
                logger.debug("Command from private chat, showing chat selection")
                
                available_chats = await message_service.get_available_chats()
                
                if not available_chats:
                    await message.answer("❌ Нет доступных чатов с сообщениями.")
                    return
                
                # Create inline keyboard with chat options
                keyboard_buttons = []
                
                for chat in available_chats:
                    chat_id = chat["chat_id"]
                    msg_count = chat["message_count"]
                    
                    # Try to get chat info
                    try:
                        chat_info = await message.bot.get_chat(chat_id)
                        chat_title = chat_info.title or f"Chat {chat_id}"
                    except Exception:
                        chat_title = f"Chat {chat_id}"
                    
                    button_text = f"{chat_title} ({msg_count} сообщ.)"
                    callback_data = f"analyze:{chat_id}:{hours or config.analysis_period_hours}"
                    
                    keyboard_buttons.append([
                        InlineKeyboardButton(text=button_text, callback_data=callback_data)
                    ])
                
                # Add "All chats" option
                total_messages = sum(chat["message_count"] for chat in available_chats)
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"📊 Все чаты ({total_messages} сообщ.)",
                        callback_data=f"analyze:all:{hours or config.analysis_period_hours}"
                    )
                ])
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
                
                await message.answer(
                    "Выберите чат для анализа:",
                    reply_markup=keyboard
                )
                
        except Exception as e:
            logger.error(
                f"Error in analyze command: {e}",
                extra={"admin_id": message.from_user.id if message.from_user else None},
                exc_info=True
            )
            await message.answer("❌ Произошла ошибка при выполнении команды.")
    
    
    @router.callback_query(lambda c: c.data and c.data.startswith("analyze:"))
    async def callback_analyze_chat(
        callback: CallbackQuery,
        analysis_service: AnalysisService,
        config: Config
    ):
        """
        Handle callback from chat selection for analysis.
        
        Callback data format: analyze:<chat_id|all>:<hours>
        
        Args:
            callback: Callback query from inline button
            analysis_service: Service for message analysis
            config: Bot configuration
        """
        try:
            # Parse callback data
            _, chat_id_str, hours_str = callback.data.split(":")
            hours = int(hours_str)
            
            # Determine chat_id to analyze
            chat_id_to_analyze = None if chat_id_str == "all" else int(chat_id_str)
            
            # Answer callback to remove loading state
            await callback.answer()
            
            # Edit message to show processing
            await callback.message.edit_text("⏳ Анализирую сообщения...")
            
            logger.info(
                "Analysis callback received",
                extra={
                    "admin_id": callback.from_user.id,
                    "chat_id_to_analyze": chat_id_to_analyze,
                    "hours": hours
                }
            )
            
            try:
                await _perform_analysis_and_send(
                    bot=callback.bot,
                    target_chat_id=callback.from_user.id,
                    analysis_service=analysis_service,
                    config=config,
                    hours=hours,
                    chat_id_to_analyze=chat_id_to_analyze,
                    admin_id=callback.from_user.id
                )
                await callback.message.delete()
                
            except ValueError as e:
                await callback.message.edit_text(f"⚠️ {str(e)}")
                
            except Exception as e:
                logger.error(f"Analysis failed: {e}", exc_info=True)
                await callback.message.edit_text("❌ Ошибка при анализе сообщений. Проверьте логи для деталей.")
                
        except Exception as e:
            logger.error(
                f"Error in analyze callback: {e}",
                extra={"admin_id": callback.from_user.id if callback.from_user else None},
                exc_info=True
            )
            try:
                await callback.answer("❌ Произошла ошибка", show_alert=True)
            except Exception:
                pass

    
    
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
