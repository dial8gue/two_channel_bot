"""Роутер для обработки инлайн-вопросов к боту."""

import logging
import re
from aiogram import Router, Bot, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType

from services.analysis_service import AnalysisService
from openai_client.client import OpenAIClient
from utils.message_formatter import MessageFormatter
from config.settings import Config


logger = logging.getLogger(__name__)

# Глобальная переменная для хранения username бота
_bot_username: str = ""


async def _get_bot_username(bot: Bot) -> str:
    """Получить и закэшировать username бота."""
    global _bot_username
    if not _bot_username:
        bot_info = await bot.get_me()
        _bot_username = bot_info.username or ""
    return _bot_username


def _check_bot_mention(text: str, bot_username: str) -> tuple[bool, str]:
    """
    Проверить, начинается ли сообщение с упоминания бота.
    
    Returns:
        Tuple (есть_упоминание, вопрос_после_упоминания)
    """
    if not bot_username or not text:
        return False, ""
    
    mention_pattern = rf'^@{re.escape(bot_username)}\s+'
    match = re.match(mention_pattern, text, re.IGNORECASE)
    
    if match:
        question = text[match.end():].strip()
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
    Общая логика обработки вопроса.
    
    Args:
        message: Сообщение пользователя
        question: Текст вопроса
        analysis_service: Сервис анализа
        config: Конфигурация бота
        is_admin: Является ли пользователь админом
    """
    # Получаем контекст из цитируемого сообщения (если есть)
    reply_context = None
    if message.reply_to_message:
        reply_msg = message.reply_to_message
        reply_username = reply_msg.from_user.username or reply_msg.from_user.first_name or "Unknown"
        reply_text = reply_msg.text or reply_msg.caption or ""
        if reply_text:
            reply_context = f"@{reply_username}: {reply_text}"
            logger.debug(
                "Найден контекст цитаты",
                extra={
                    "reply_user": reply_username,
                    "reply_text_length": len(reply_text)
                }
            )
    
    # Показываем сообщение о обработке
    processing_msg = await message.answer("🤔 Думаю над ответом...")
    
    try:
        # Вызываем сервис с debounce защитой
        answer = await analysis_service.answer_question_with_debounce(
            question=question,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            reply_context=reply_context,
            bypass_debounce=is_admin
        )
        
        # Удаляем сообщение о обработке
        await processing_msg.delete()
        
        # Отправляем ответ
        await message.answer(answer, parse_mode="Markdown")
        
        logger.info(
            "Вопрос обработан успешно",
            extra={
                "user_id": message.from_user.id,
                "chat_id": message.chat.id,
                "answer_length": len(answer)
            }
        )
        
    except ValueError as e:
        # Обработка debounce
        error_msg = str(e)
        try:
            remaining_seconds = float(error_msg)
            warning_msg = MessageFormatter.format_debounce_warning("вопрос", remaining_seconds)
            await processing_msg.edit_text(warning_msg, parse_mode="Markdown")
        except Exception:
            await processing_msg.edit_text(f"⚠️ {error_msg}")
        
        logger.debug(
            "Вопрос заблокирован debounce",
            extra={
                "user_id": message.from_user.id,
                "chat_id": message.chat.id
            }
        )


def create_ask_router(config: Config) -> Router:
    """
    Создать и настроить роутер для команды /ask и упоминаний бота.
    
    Args:
        config: Конфигурация бота
        
    Returns:
        Настроенный экземпляр роутера
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
        Обработка команды /ask для ответа на вопросы.
        
        Использование:
            /ask <вопрос> - задать вопрос боту
            Ответ на сообщение с /ask <вопрос> - вопрос с контекстом цитаты
            
        Args:
            message: Сообщение с командой
            analysis_service: Сервис анализа
            config: Конфигурация бота
        """
        try:
            # Проверяем, является ли пользователь админом
            is_admin = message.from_user.id == config.admin_id
            
            # Извлекаем вопрос из сообщения
            command_text = message.text or ""
            # Убираем команду /ask из начала
            question = command_text.split(maxsplit=1)[1] if len(command_text.split()) > 1 else ""
            
            if not question.strip():
                await message.answer(
                    "❓ Укажите вопрос после команды.\n"
                    "Использование: `/ask ваш вопрос`",
                    parse_mode="Markdown"
                )
                return
            
            logger.info(
                "Получена команда /ask",
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
                f"Ошибка в команде /ask: {e}",
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
        lambda message: message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]
    )
    async def handle_mention(
        message: Message,
        bot: Bot,
        analysis_service: AnalysisService,
        config: Config
    ):
        """
        Обработка упоминания бота через @username.
        
        Использование:
            @botname вопрос - задать вопрос боту
            Ответ на сообщение с @botname вопрос - вопрос с контекстом цитаты
            
        Args:
            message: Сообщение с упоминанием
            bot: Экземпляр бота
            analysis_service: Сервис анализа
            config: Конфигурация бота
        """
        try:
            # Получаем username бота
            bot_username = await _get_bot_username(bot)
            
            if not bot_username:
                return
            
            text = message.text or ""
            
            # Проверяем упоминание бота
            has_mention, question = _check_bot_mention(text, bot_username)
            
            if not has_mention:
                # Не наше сообщение - пропускаем (не блокируем другие хендлеры)
                return
            
            if not question:
                await message.answer(
                    "❓ Укажите вопрос после упоминания.\n"
                    f"Использование: `@{bot_username} ваш вопрос`",
                    parse_mode="Markdown"
                )
                return
            
            # Проверяем, является ли пользователь админом
            is_admin = message.from_user.id == config.admin_id
            
            logger.info(
                "Получено упоминание бота",
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
                f"Ошибка при обработке упоминания: {e}",
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
        Обработка команды /ask в личном чате админа (без контекста).
        
        Args:
            message: Сообщение с командой
            openai_client: Клиент OpenAI
            config: Конфигурация бота
        """
        try:
            # Извлекаем вопрос из сообщения
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
                "Получена команда /ask в личном чате",
                extra={
                    "user_id": message.from_user.id,
                    "question_length": len(question)
                }
            )
            
            # Показываем сообщение о обработке
            processing_msg = await message.answer("🤔 Думаю над ответом...")
            
            try:
                # Вызываем OpenAI напрямую без контекста
                answer = await openai_client.answer_question_simple(question)
                
                # Удаляем сообщение о обработке
                await processing_msg.delete()
                
                # Отправляем ответ
                await message.answer(answer, parse_mode="Markdown")
                
                logger.info(
                    "Команда /ask в личном чате выполнена",
                    extra={
                        "user_id": message.from_user.id,
                        "answer_length": len(answer)
                    }
                )
                
            except Exception as e:
                logger.error(f"Ошибка при генерации ответа: {e}", exc_info=True)
                await processing_msg.edit_text("❌ Ошибка при генерации ответа.")
                
        except Exception as e:
            logger.error(
                f"Ошибка в команде /ask (личный чат): {e}",
                extra={"user_id": message.from_user.id if message.from_user else None},
                exc_info=True
            )
            try:
                await message.answer("❌ Произошла ошибка при обработке вопроса.")
            except Exception:
                pass
    
    return router
