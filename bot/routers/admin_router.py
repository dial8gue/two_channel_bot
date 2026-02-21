"""Router for handling administrative commands."""

import asyncio
import logging
from typing import Optional

from aiogram import Router, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode, ChatType

from bot.filters.admin_filter import IsAdminFilter
from services.analysis_service import AnalysisService
from services.admin_service import AdminService
from services.message_service import MessageService
from openai_client.client import OpenAIClient
from utils.message_formatter import MessageFormatter
from utils.telegram_sender import send_analysis_with_fallback, safe_reply, typing_loop
from config.settings import Config


logger = logging.getLogger(__name__)


async def _perform_analysis_and_send(
    bot: Bot,
    target_chat_id: int,
    analysis_service: AnalysisService,
    config: Config,
    hours: Optional[int],
    chat_id_to_analyze: Optional[int],
    admin_id: int,
    typing_chat_id: int,
    bypass_cache: bool = False
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
        typing_chat_id: Chat ID to show typing indicator
        bypass_cache: If True, skip cache for private admin commands
    """
    # Start typing indicator
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(typing_loop(typing_chat_id, bot, stop_typing))
    
    try:
        # Perform analysis with debounce bypass for admin
        operation_chat_id = chat_id_to_analyze if chat_id_to_analyze is not None else 0
        
        analysis_result, from_cache = await analysis_service.analyze_messages_with_debounce(
            hours=hours or config.analysis_period_hours,
            chat_id=operation_chat_id,
            user_id=admin_id,
            operation_type="admin_analyze",
            bypass_debounce=True,
            bypass_cache=bypass_cache
        )
        
        # Stop typing indicator
        stop_typing.set()
        typing_task.cancel()
        
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
    except Exception:
        stop_typing.set()
        typing_task.cancel()
        raise


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
                    await message.answer("❌ Неверный формат. Используй: /analyze [часы]")
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
                        admin_id=message.from_user.id,
                        typing_chat_id=message.chat.id
                    )
                    await processing_msg.delete()
                    
                except ValueError as e:
                    await processing_msg.delete()
                    await message.answer(f"⚠️ {str(e)}")
                    
                except Exception as e:
                    logger.error(f"Analysis failed: {e}", exc_info=True)
                    await processing_msg.delete()
                    await message.answer("❌ Ошибка при анализе сообщений. Проверь логи для деталей.")
                    
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
                    "Выбери чат для анализа:",
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
            
            # Delete the selection message - typing indicator is enough
            await callback.message.delete()
            
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
                    admin_id=callback.from_user.id,
                    typing_chat_id=callback.message.chat.id,
                    bypass_cache=True  # Private chat - no cache
                )
                
            except ValueError as e:
                await callback.bot.send_message(callback.from_user.id, f"⚠️ {str(e)}")
                
            except Exception as e:
                logger.error(f"Analysis failed: {e}", exc_info=True)
                await callback.bot.send_message(callback.from_user.id, "❌ Ошибка при анализе сообщений. Проверь логи для деталей.")
                
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
                    "❌ Укажи период хранения в часах.\n"
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
                    "❌ Укажи период анализа в часах.\n"
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
    
    
    @router.message(Command("set_model"), admin_filter)
    async def cmd_set_model(
        message: Message,
        admin_service: AdminService,
        openai_client: OpenAIClient
    ):
        """
        Handle /set_model command to change OpenAI model.
        
        Usage: /set_model <model_name>
        
        Args:
            message: Command message from admin
            admin_service: Service for admin operations
            openai_client: OpenAI client instance
        """
        try:
            # Parse model parameter
            if not message.text or len(message.text.split()) < 2:
                current_model = openai_client.get_model()
                await message.answer(
                    f"Текущая модель: `{current_model}`\n\n"
                    "Использование: /set\\_model <название\\_модели>\n\n"
                    "Примеры:\n"
                    "• `gpt-4o-mini` — быстрая и дешёвая\n"
                    "• `gpt-4o` — умнее, дороже\n"
                    "• `gpt-4-turbo` — мощная",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            model = message.text.split(maxsplit=1)[1].strip()
            
            logger.info(
                "Set model command received",
                extra={"admin_id": message.from_user.id, "model": model}
            )
            
            # Save to database
            await admin_service.set_openai_model(model)
            
            # Update client immediately
            openai_client.set_model(model)
            
            await message.answer(f"✅ Модель изменена на: `{model}`", parse_mode=ParseMode.MARKDOWN)
            
            logger.info(
                "OpenAI model updated",
                extra={"admin_id": message.from_user.id, "model": model}
            )
            
        except ValueError as e:
            await message.answer(f"❌ {str(e)}")
        except Exception as e:
            logger.error(
                f"Error setting model: {e}",
                extra={"admin_id": message.from_user.id if message.from_user else None},
                exc_info=True
            )
            await message.answer("❌ Ошибка при изменении модели.")
    
    @router.message(Command("toggle_vision"), admin_filter)
    async def cmd_toggle_vision(
        message: Message,
        admin_service: AdminService,
        openai_client: OpenAIClient
    ):
        """
        Handle /toggle_vision command to enable/disable image recognition.
        
        Args:
            message: Command message from admin
            admin_service: Service for admin operations
            openai_client: OpenAI client instance
        """
        try:
            # Get current state and toggle
            current = await admin_service.is_vision_enabled()
            new_state = not current
            
            await admin_service.toggle_vision(new_state)
            openai_client.vision_enabled = new_state
            
            status = "включено ✅" if new_state else "выключено ❌"
            await message.answer(f"🖼 Распознавание изображений: {status}")
            
            logger.info(
                "Vision toggled",
                extra={"admin_id": message.from_user.id, "vision_enabled": new_state}
            )
            
        except Exception as e:
            logger.error(
                f"Error toggling vision: {e}",
                extra={"admin_id": message.from_user.id if message.from_user else None},
                exc_info=True
            )
            await message.answer("❌ Ошибка при переключении распознавания изображений.")
    
    
    @router.message(Command("manage_groups"), admin_filter)
    async def cmd_manage_groups(message: Message, admin_service: AdminService):
        """
        Handle /manage_groups command to show group management interface.
        
        Args:
            message: Command message from admin
            admin_service: Service for admin operations
        """
        try:
            logger.info(
                "Manage groups command received",
                extra={"admin_id": message.from_user.id}
            )
            
            # Get all groups
            groups = await admin_service.get_all_groups()
            
            if not groups:
                await message.answer("📋 Нет зарегистрированных групп.")
                return
            
            # Create inline keyboard with group options
            keyboard_buttons = []
            
            for group in groups:
                # Status emoji
                status_emoji = "✅" if group.is_enabled else "⛔️"
                
                # Group title button (just for display)
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"{status_emoji} {group.title}",
                        callback_data=f"group_info:{group.chat_id}"
                    )
                ])
                
                # Action buttons for this group
                action_buttons = []
                
                if group.is_enabled:
                    action_buttons.append(
                        InlineKeyboardButton(
                            text="🔴 Отключить",
                            callback_data=f"group_disable:{group.chat_id}"
                        )
                    )
                else:
                    action_buttons.append(
                        InlineKeyboardButton(
                            text="🟢 Включить",
                            callback_data=f"group_enable:{group.chat_id}"
                        )
                    )
                
                action_buttons.append(
                    InlineKeyboardButton(
                        text="🚪 Покинуть",
                        callback_data=f"group_leave:{group.chat_id}"
                    )
                )
                
                keyboard_buttons.append(action_buttons)
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await message.answer(
                "🔧 Управление группами:\n\n"
                "Выбери действие для группы:",
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(
                f"Error in manage_groups command: {e}",
                extra={"admin_id": message.from_user.id if message.from_user else None},
                exc_info=True
            )
            await message.answer("❌ Ошибка при получении списка групп.")
    
    
    @router.callback_query(lambda c: c.data and c.data.startswith("group_"))
    async def callback_group_action(
        callback: CallbackQuery,
        admin_service: AdminService
    ):
        """
        Handle callback from group management buttons.
        
        Callback data formats:
        - group_info:<chat_id> - Show group info
        - group_disable:<chat_id> - Disable bot in group
        - group_enable:<chat_id> - Enable bot in group
        - group_leave:<chat_id> - Leave group
        
        Args:
            callback: Callback query from inline button
            admin_service: Service for admin operations
        """
        try:
            action, chat_id_str = callback.data.split(":", 1)
            chat_id = int(chat_id_str)
            
            if action == "group_info":
                # Just acknowledge, no action needed
                await callback.answer()
                return
            
            elif action == "group_disable":
                # Disable bot in group
                await admin_service.toggle_group(chat_id, enabled=False)
                await callback.answer("✅ Бот отключен в группе", show_alert=True)
                
                logger.info(
                    f"Bot disabled in group {chat_id}",
                    extra={"admin_id": callback.from_user.id}
                )
                
            elif action == "group_enable":
                # Enable bot in group
                await admin_service.toggle_group(chat_id, enabled=True)
                await callback.answer("✅ Бот включен в группе", show_alert=True)
                
                logger.info(
                    f"Bot enabled in group {chat_id}",
                    extra={"admin_id": callback.from_user.id}
                )
                
            elif action == "group_leave":
                # Leave group
                try:
                    # Send goodbye message to the group before leaving
                    try:
                        await callback.bot.send_message(chat_id, "Я ливаю отсюда!")
                        # Give some time for the message to be delivered
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.warning(f"Failed to send goodbye message to group {chat_id}: {e}")
                    
                    # Now leave the group
                    await callback.bot.leave_chat(chat_id)
                    await admin_service.remove_group(chat_id)
                    await callback.answer("✅ Бот покинул группу", show_alert=True)
                    
                    logger.info(
                        f"Bot left group {chat_id}",
                        extra={"admin_id": callback.from_user.id}
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to leave group {chat_id}: {e}", exc_info=True)
                    await callback.answer("❌ Не удалось покинуть группу", show_alert=True)
                    return
            
            # Refresh the group list
            groups = await admin_service.get_all_groups()
            
            if not groups:
                await callback.message.edit_text("📋 Нет зарегистрированных групп.")
                return
            
            # Recreate keyboard
            keyboard_buttons = []
            
            for group in groups:
                status_emoji = "✅" if group.is_enabled else "⛔️"
                
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"{status_emoji} {group.title}",
                        callback_data=f"group_info:{group.chat_id}"
                    )
                ])
                
                action_buttons = []
                
                if group.is_enabled:
                    action_buttons.append(
                        InlineKeyboardButton(
                            text="🔴 Отключить",
                            callback_data=f"group_disable:{group.chat_id}"
                        )
                    )
                else:
                    action_buttons.append(
                        InlineKeyboardButton(
                            text="🟢 Включить",
                            callback_data=f"group_enable:{group.chat_id}"
                        )
                    )
                
                action_buttons.append(
                    InlineKeyboardButton(
                        text="🚪 Покинуть",
                        callback_data=f"group_leave:{group.chat_id}"
                    )
                )
                
                keyboard_buttons.append(action_buttons)
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await callback.message.edit_reply_markup(reply_markup=keyboard)
            
        except Exception as e:
            logger.error(
                f"Error in group action callback: {e}",
                extra={"admin_id": callback.from_user.id if callback.from_user else None},
                exc_info=True
            )
            try:
                await callback.answer("❌ Произошла ошибка", show_alert=True)
            except Exception:
                pass
    
    
    return router
