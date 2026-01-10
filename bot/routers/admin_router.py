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
from utils.telegram_sender import send_analysis_with_fallback, send_horoscope_with_fallback, safe_reply
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
    
    
    @router.message(Command("horoscope"), admin_filter)
    async def cmd_horoscope_admin(
        message: Message,
        analysis_service: AnalysisService,
        message_service: MessageService,
        config: Config
    ):
        """
        Handle /horoscope command for admin to create horoscopes for users.
        
        Usage:
            /horoscope - Show chat and user selection
            /horoscope @username - Create horoscope for specific user in current chat (if in group)
            
        Args:
            message: Command message from admin
            analysis_service: Service for message analysis
            message_service: Service for message operations
            config: Bot configuration
        """
        try:
            logger.info(
                "Admin horoscope command received",
                extra={
                    "admin_id": message.from_user.id,
                    "chat_id": message.chat.id,
                    "chat_type": message.chat.type
                }
            )
            
            # Parse optional username parameter
            target_username = None
            if message.text and len(message.text.split()) > 1:
                target_username = message.text.split()[1].lstrip('@')
            
            # Determine behavior based on chat type and parameters
            if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                # Command from group
                if not target_username:
                    # No username specified - create horoscope for admin
                    target_user_id = message.from_user.id
                    actual_username = message.from_user.username or message.from_user.first_name or "Admin"
                    
                    logger.info(
                        f"Creating horoscope for admin in group (no username specified)",
                        extra={
                            "admin_id": message.from_user.id,
                            "chat_id": message.chat.id,
                            "target_username": actual_username
                        }
                    )
                else:
                    # Username specified - find that user
                    # Get messages from last 12 hours to find the user
                    from datetime import datetime, timedelta
                    start_time = datetime.now() - timedelta(hours=12)
                    messages = await message_service.message_repository.get_by_period(
                        start_time=start_time,
                        chat_id=message.chat.id
                    )
                    
                    # Find user by username
                    target_user_id = None
                    actual_username = None
                    for msg in messages:
                        if msg.username.lower() == target_username.lower():
                            target_user_id = msg.user_id
                            actual_username = msg.username
                            break
                    
                    if not target_user_id:
                        await message.answer(
                            f"❌ Пользователь @{target_username} не найден в сообщениях за последние 12 часов."
                        )
                        return
                
                # Create horoscope for the determined user
                processing_msg = await message.answer("🔮 Звезды изучают сообщения...")
                
                try:
                    # Create horoscope
                    horoscope_result, from_cache = await analysis_service.create_horoscope_with_debounce(
                        user_id=target_user_id,
                        username=actual_username,
                        chat_id=message.chat.id,
                        hours=12,
                        bypass_debounce=True  # Admin bypasses debounce
                    )
                    
                    await processing_msg.delete()
                    
                    # Send result with fallback mechanism (реплаем на исходное сообщение)
                    await send_horoscope_with_fallback(
                        send_func=lambda text, pm: safe_reply(message, text, pm),
                        horoscope_result=horoscope_result,
                        period_hours=12,
                        from_cache=from_cache,
                        config=config,
                        username=actual_username
                    )
                    
                except Exception as e:
                    logger.error(f"Horoscope creation failed: {e}", exc_info=True)
                    await processing_msg.edit_text("❌ Ошибка при создании гороскопа.")
                    
            else:
                # Command from private chat - show chat and user selection
                logger.debug("Admin horoscope command from private chat, showing selection")
                
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
                    callback_data = f"horoscope_chat:{chat_id}"
                    
                    keyboard_buttons.append([
                        InlineKeyboardButton(text=button_text, callback_data=callback_data)
                    ])
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
                
                await message.answer(
                    "🔮 Выберите чат для создания гороскопа:",
                    reply_markup=keyboard
                )
                
        except Exception as e:
            logger.error(
                f"Error in admin horoscope command: {e}",
                extra={"admin_id": message.from_user.id if message.from_user else None},
                exc_info=True
            )
            await message.answer("❌ Произошла ошибка при выполнении команды.")
    
    
    @router.callback_query(lambda c: c.data and c.data.startswith("horoscope_chat:"))
    async def callback_horoscope_chat_selection(
        callback: CallbackQuery,
        analysis_service: AnalysisService,
        message_service: MessageService,
        config: Config
    ):
        """
        Handle callback from chat selection for horoscope.
        
        Callback data format: horoscope_chat:<chat_id>
        
        Args:
            callback: Callback query from inline button
            analysis_service: Service for message analysis
            message_service: Service for message operations
            config: Bot configuration
        """
        try:
            # Parse callback data
            _, chat_id_str = callback.data.split(":")
            chat_id = int(chat_id_str)
            
            # Answer callback to remove loading state
            await callback.answer()
            
            logger.info(
                "Horoscope chat selection callback received",
                extra={
                    "admin_id": callback.from_user.id,
                    "selected_chat_id": chat_id
                }
            )
            
            # Get users from the selected chat (last 12 hours)
            from datetime import datetime, timedelta
            start_time = datetime.now() - timedelta(hours=12)
            messages = await message_service.message_repository.get_by_period(
                start_time=start_time,
                chat_id=chat_id
            )
            
            if not messages:
                await callback.message.edit_text("❌ Нет сообщений в выбранном чате за последние 12 часов.")
                return
            
            # Get unique users with message counts
            user_stats = {}
            for msg in messages:
                if msg.user_id not in user_stats:
                    user_stats[msg.user_id] = {
                        'username': msg.username,
                        'message_count': 0
                    }
                user_stats[msg.user_id]['message_count'] += 1
            
            # Sort users by message count (most active first)
            sorted_users = sorted(
                user_stats.items(),
                key=lambda x: x[1]['message_count'],
                reverse=True
            )
            
            # Create inline keyboard with user options (limit to 10 most active)
            keyboard_buttons = []
            for user_id, user_data in sorted_users[:10]:
                username = user_data['username']
                msg_count = user_data['message_count']
                
                button_text = f"@{username} ({msg_count} сообщ.)"
                callback_data = f"horoscope_user:{chat_id}:{user_id}:{username}"
                
                keyboard_buttons.append([
                    InlineKeyboardButton(text=button_text, callback_data=callback_data)
                ])
            
            # Add back button
            keyboard_buttons.append([
                InlineKeyboardButton(text="⬅️ Назад к выбору чата", callback_data="horoscope_back")
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            # Try to get chat info for display
            try:
                chat_info = await callback.bot.get_chat(chat_id)
                chat_title = chat_info.title or f"Chat {chat_id}"
            except Exception:
                chat_title = f"Chat {chat_id}"
            
            await callback.message.edit_text(
                f"🔮 Выберите пользователя в чате *{chat_title}*:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(
                f"Error in horoscope chat selection callback: {e}",
                extra={"admin_id": callback.from_user.id if callback.from_user else None},
                exc_info=True
            )
            try:
                await callback.answer("❌ Произошла ошибка", show_alert=True)
            except Exception:
                pass
    
    
    @router.callback_query(lambda c: c.data and c.data.startswith("horoscope_user:"))
    async def callback_horoscope_user_selection(
        callback: CallbackQuery,
        analysis_service: AnalysisService,
        config: Config
    ):
        """
        Handle callback from user selection for horoscope.
        
        Callback data format: horoscope_user:<chat_id>:<user_id>:<username>
        
        Args:
            callback: Callback query from inline button
            analysis_service: Service for message analysis
            config: Bot configuration
        """
        try:
            # Parse callback data
            _, chat_id_str, user_id_str, username = callback.data.split(":", 3)
            chat_id = int(chat_id_str)
            user_id = int(user_id_str)
            
            # Answer callback to remove loading state
            await callback.answer()
            
            # Edit message to show processing
            await callback.message.edit_text("🔮 Звезды изучают сообщения пользователя...")
            
            logger.info(
                "Horoscope user selection callback received",
                extra={
                    "admin_id": callback.from_user.id,
                    "target_user_id": user_id,
                    "target_username": username,
                    "chat_id": chat_id
                }
            )
            
            try:
                # Create horoscope
                horoscope_result, from_cache = await analysis_service.create_horoscope_with_debounce(
                    user_id=user_id,
                    username=username,
                    chat_id=chat_id,
                    hours=12,
                    bypass_debounce=True  # Admin bypasses debounce
                )
                
                # Send result to admin's private chat with fallback mechanism
                await send_horoscope_with_fallback(
                    send_func=lambda text, pm: callback.bot.send_message(
                        chat_id=callback.from_user.id,
                        text=text,
                        parse_mode=pm
                    ),
                    horoscope_result=horoscope_result,
                    period_hours=12,
                    from_cache=from_cache,
                    config=config,
                    username=username
                )
                
                # Delete the selection message
                await callback.message.delete()
                
                logger.info(
                    "Admin horoscope completed and sent",
                    extra={
                        "admin_id": callback.from_user.id,
                        "target_user_id": user_id,
                        "target_username": username,
                        "from_cache": from_cache
                    }
                )
                
            except Exception as e:
                logger.error(f"Horoscope creation failed: {e}", exc_info=True)
                await callback.message.edit_text("❌ Ошибка при создании гороскопа.")
                
        except Exception as e:
            logger.error(
                f"Error in horoscope user selection callback: {e}",
                extra={"admin_id": callback.from_user.id if callback.from_user else None},
                exc_info=True
            )
            try:
                await callback.answer("❌ Произошла ошибка", show_alert=True)
            except Exception:
                pass
    
    
    @router.callback_query(lambda c: c.data == "horoscope_back")
    async def callback_horoscope_back(
        callback: CallbackQuery,
        message_service: MessageService
    ):
        """
        Handle back button for horoscope chat selection.
        
        Args:
            callback: Callback query from back button
            message_service: Service for message operations
        """
        try:
            # Answer callback
            await callback.answer()
            
            # Get available chats again
            available_chats = await message_service.get_available_chats()
            
            if not available_chats:
                await callback.message.edit_text("❌ Нет доступных чатов с сообщениями.")
                return
            
            # Create inline keyboard with chat options
            keyboard_buttons = []
            
            for chat in available_chats:
                chat_id = chat["chat_id"]
                msg_count = chat["message_count"]
                
                # Try to get chat info
                try:
                    chat_info = await callback.bot.get_chat(chat_id)
                    chat_title = chat_info.title or f"Chat {chat_id}"
                except Exception:
                    chat_title = f"Chat {chat_id}"
                
                button_text = f"{chat_title} ({msg_count} сообщ.)"
                callback_data = f"horoscope_chat:{chat_id}"
                
                keyboard_buttons.append([
                    InlineKeyboardButton(text=button_text, callback_data=callback_data)
                ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await callback.message.edit_text(
                "🔮 Выберите чат для создания гороскопа:",
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"Error in horoscope back callback: {e}", exc_info=True)
            try:
                await callback.answer("❌ Произошла ошибка", show_alert=True)
            except Exception:
                pass
    
    
    return router
