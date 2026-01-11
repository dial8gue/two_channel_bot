"""
OpenAI client for analyzing Telegram messages.
"""
import logging
from datetime import datetime
from typing import List, Optional
from openai import AsyncOpenAI, RateLimitError, APIConnectionError
from openai import APIError as OpenAIAPIError
from database.models import MessageModel
from utils.timezone_helper import format_datetime


logger = logging.getLogger(__name__)


class OpenAIClientError(Exception):
    """Ошибка клиента OpenAI."""
    pass


class OpenAIClient:
    """Client for interacting with OpenAI API to analyze messages."""
    
    def __init__(self, api_key: str, base_url: str = None, model: str = "gpt-4o-mini", max_tokens: int = 4000, horoscope_max_tokens: int = 2000, inline_max_tokens: int = 500, timezone: Optional[str] = None):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key
            base_url: Optional base URL for API (defaults to OpenAI's endpoint)
            model: Model to use for analysis
            max_tokens: Maximum tokens for API requests (analysis)
            horoscope_max_tokens: Maximum tokens for horoscope requests
            inline_max_tokens: Maximum tokens for inline question answers
            timezone: Optional IANA timezone identifier for timestamp formatting
        """
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        
        self.client = AsyncOpenAI(**client_kwargs)
        self.model = model
        self.max_tokens = max_tokens
        self.horoscope_max_tokens = horoscope_max_tokens
        self.inline_max_tokens = inline_max_tokens
        self.timezone = timezone
        logger.info(
            "OpenAI client initialized",
            extra={
                "model": model,
                "max_tokens": max_tokens,
                "horoscope_max_tokens": horoscope_max_tokens,
                "inline_max_tokens": inline_max_tokens,
                "base_url": base_url or "default",
                "timezone": timezone or "UTC"
            }
        )
    
    async def analyze_messages(self, messages: List[MessageModel]) -> str:
        """
        Analyze messages using OpenAI API.
        
        Args:
            messages: List of messages to analyze
            
        Returns:
            Analysis result as formatted text
            
        Raises:
            APIError: If OpenAI API returns an error
            RateLimitError: If rate limit is exceeded
            APIConnectionError: If connection to API fails
        """
        if not messages:
            logger.warning("No messages provided for analysis")
            return "Нет сообщений для анализа."
        
        try:
            prompt = self._build_prompt(messages)
            
            logger.info(
                "Sending analysis request to OpenAI",
                extra={
                    "message_count": len(messages),
                    "prompt_length": len(prompt)
                }
            )
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": r"""Ты - аналитик групповых чатов с чувством юмора.

КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА ФОРМАТИРОВАНИЯ:

1. ЗАГОЛОВКИ РАЗДЕЛОВ: ОБЯЗАТЕЛЬНО выделяй жирным шрифтом используя *текст*
   Правильно: *1. Основные темы обсуждения* 🎭
   Неправильно: 1. Основные темы обсуждения 🎭

2. УПОМИНАНИЯ ПОЛЬЗОВАТЕЛЕЙ: ВСЕГДА ставь обратный слеш \ перед каждым подчеркиванием в username
   Правильно: @user\_name, @test\_user\_123, @my\_cool\_name
   Неправильно: @user_name, @test_user_123
   ВАЖНО: Это необходимо для корректного отображения в Telegram Markdown
   
3. СТРУКТУРА: Строго следуй указанному формату с 4 разделами

Ты ОБЯЗАН следовать этим правилам в каждом ответе."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=0.7
            )
            
            analysis = response.choices[0].message.content
            
            logger.info(
                "Analysis completed successfully",
                extra={
                    "tokens_used": response.usage.total_tokens,
                    "response_length": len(analysis) if analysis else 0
                }
            )
            
            return analysis or "Не удалось получить анализ."
            
        except RateLimitError as e:
            logger.error("OpenAI rate limit exceeded", exc_info=True)
            raise OpenAIClientError(
                "Превышен лимит запросов к OpenAI API. Попробуйте позже."
            ) from e
            
        except APIConnectionError as e:
            logger.error("Failed to connect to OpenAI API", exc_info=True)
            raise OpenAIClientError(
                "Не удалось подключиться к OpenAI API. Проверьте соединение."
            ) from e
            
        except OpenAIAPIError as e:
            logger.error("OpenAI API error", exc_info=True)
            raise OpenAIClientError(
                f"Ошибка OpenAI API: {str(e)}"
            ) from e
            
        except Exception as e:
            logger.error("Unexpected error during analysis", exc_info=True)
            raise OpenAIClientError(
                f"Неожиданная ошибка при анализе: {str(e)}"
            ) from e
    
    async def create_horoscope(self, messages: List[MessageModel], username: str) -> str:
        """
        Create an ironic horoscope based on user's messages.
        
        Args:
            messages: List of user's messages to analyze (can be empty)
            username: Username for personalization
            
        Returns:
            Horoscope result as formatted text
            
        Raises:
            APIError: If OpenAI API returns an error
            RateLimitError: If rate limit is exceeded
            APIConnectionError: If connection to API fails
        """
        # Гороскоп генерируется даже без сообщений - звезды всегда что-то скажут
        
        try:
            prompt = self._build_horoscope_prompt(messages, username)
            
            logger.info(
                "Sending horoscope request to OpenAI",
                extra={
                    "message_count": len(messages),
                    "username": username,
                    "prompt_length": len(prompt)
                }
            )
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": r"""Ты - ироничный астролог-мемолог, который составляет гороскопы на основе сообщений пользователей в чатах.

КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА ФОРМАТИРОВАНИЯ:

1. ЗАГОЛОВКИ РАЗДЕЛОВ: ОБЯЗАТЕЛЬНО выделяй жирным шрифтом используя *текст*
   Правильно: *🔮 Гороскоп для @user\_name* 
   Неправильно: 🔮 Гороскоп для @user_name

2. УПОМИНАНИЯ ПОЛЬЗОВАТЕЛЕЙ: ВСЕГДА ставь обратный слеш \ перед каждым подчеркиванием в username
   Правильно: @user\_name, @test\_user\_123, @my\_cool\_name
   Неправильно: @user_name, @test_user_123
   ВАЖНО: Это необходимо для корректного отображения в Telegram Markdown

3. СТРУКТУРА: Строго следуй указанному формату с разделами

Ты ОБЯЗАН следовать этим правилам в каждом ответе."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.horoscope_max_tokens,
                temperature=0.7
            )
            
            horoscope = response.choices[0].message.content
            
            logger.info(
                "Horoscope completed successfully",
                extra={
                    "tokens_used": response.usage.total_tokens,
                    "response_length": len(horoscope) if horoscope else 0,
                    "username": username
                }
            )
            
            return horoscope or "Звезды отказались комментировать ваши сообщения. 🌟"
            
        except RateLimitError as e:
            logger.error("OpenAI rate limit exceeded", exc_info=True)
            raise OpenAIClientError(
                "Превышен лимит запросов к OpenAI API. Попробуйте позже."
            ) from e
            
        except APIConnectionError as e:
            logger.error("Failed to connect to OpenAI API", exc_info=True)
            raise OpenAIClientError(
                "Не удалось подключиться к OpenAI API. Проверьте соединение."
            ) from e
            
        except OpenAIAPIError as e:
            logger.error("OpenAI API error", exc_info=True)
            raise OpenAIClientError(
                f"Ошибка OpenAI API: {str(e)}"
            ) from e
            
        except Exception as e:
            logger.error("Unexpected error during horoscope creation", exc_info=True)
            raise OpenAIClientError(
                f"Неожиданная ошибка при создании гороскопа: {str(e)}"
            ) from e
    
    def _build_prompt(self, messages: List[MessageModel]) -> str:
        """
        Build analysis prompt from messages.
        
        Args:
            messages: List of messages to include in prompt
            
        Returns:
            Formatted prompt string in Russian
        """
        # Sort messages by timestamp
        sorted_messages = sorted(messages, key=lambda m: m.timestamp)
        
        # Build message list
        message_lines = []
        for msg in sorted_messages:
            timestamp_str = format_datetime(msg.timestamp, self.timezone)
            reactions_str = ""
            
            if msg.reactions:
                reactions_list = [f"{emoji}: {count}" for emoji, count in msg.reactions.items()]
                reactions_str = f" [Реакции: {', '.join(reactions_list)}]"
            
            reply_str = ""
            # if msg.reply_to_message_id:
            #     reply_str = f" [Ответ на сообщение #{msg.reply_to_message_id}]"
            
            message_lines.append(
                f"[{timestamp_str}] @{msg.username}: {msg.text}{reactions_str}{reply_str}"
            )
        
        messages_text = "\n".join(message_lines)
        
        # Build complete prompt
        prompt = f"""Проанализируй следующие сообщения из группового чата и предоставь краткую сводку.

СООБЩЕНИЯ:
{messages_text}

ФОРМАТ ОТВЕТА (СТРОГО соблюдай каждую деталь):

*1. Основные темы обсуждения* 🎭
- Перечисли главные темы, о которых спорили наши герои (и насколько далеко они ушли от изначальной темы)
- Укажи, кто был главным "экспертом" в каждой области и насколько это обоснованно

*2. Самые "горячие" посты* 🔥
- Определи сообщения, которые разожгли самые жаркие баталии
- Укажи автора и суть его "гениального" вклада в дискуссию
- Оцени уровень драмы по шкале от "легкого недопонимания" до "ядерной войны"

*3. Короли реакций* 👑
- Определи пользователей, чьи сообщения собрали армию эмодзи
- Проанализируй, заслужили ли они эту славу или просто повезло
- Отметь самые популярные реакции и что они говорят о душевном состоянии чата

*4. Диагноз чата* 🏥
- Статистика: сколько сообщений, сколько участников
- Общий уровень токсичности и шансы на мирное разрешение конфликтов
- Прогноз: будут ли участники еще разговаривать друг с другом завтра

ПРАВИЛА ФОРМАТИРОВАНИЯ (ОБЯЗАТЕЛЬНЫ):
1. Каждый заголовок раздела (1., 2., 3., 4.) ОБЯЗАТЕЛЬНО выделяй *жирным* как показано выше
2. При упоминании пользователей ВСЕГДА экранируй подчеркивания обратным слешем
   Правильно: @user\_name, @john\_doe, @test\_user\_123
   Неправильно: @user_name, @john_doe, @test_user_123
   КРИТИЧНО: Каждое подчеркивание должно быть с обратным слешем перед ним

СТИЛЬ: Используй сарказм, зумерский язык, иронию и легкий цинизм. Будь кратким. Добавь эмодзи для драматического эффекта. Мы анализируем человеческую комедию, а не пишем научную работу.

НАЧНИ ОТВЕТ СРАЗУ С ПЕРВОГО ПУНКТА (*1. Основные темы обсуждения* 🎭). НЕ ДОБАВЛЯЙ ВСТУПЛЕНИЙ ИЛИ ЗАКЛЮЧЕНИЙ."""
        return prompt
    
    def _build_horoscope_prompt(self, messages: List[MessageModel], username: str) -> str:
        """
        Build horoscope prompt from user's messages.
        
        Args:
            messages: List of user's messages to analyze
            username: Username for personalization
            
        Returns:
            Formatted horoscope prompt string in Russian
        """
        # Sort messages by timestamp
        sorted_messages = sorted(messages, key=lambda m: m.timestamp)
        
        # Build message list
        message_lines = []
        for msg in sorted_messages:
            timestamp_str = format_datetime(msg.timestamp, self.timezone)
            reactions_str = ""
            
            if msg.reactions:
                reactions_list = [f"{emoji}: {count}" for emoji, count in msg.reactions.items()]
                reactions_str = f" [Реакции: {', '.join(reactions_list)}]"
            
            message_lines.append(
                f"[{timestamp_str}] {msg.text}{reactions_str}"
            )
        
        messages_text = "\n".join(message_lines) if message_lines else "Сообщений нет - пользователь молчал как партизан"
        
        # Escape username for Markdown
        escaped_username = username.replace('_', r'\_')
        
        # Определяем контекст для промпта
        has_messages = len(messages) > 0
        context_note = "" if has_messages else "\nВАЖНО: У пользователя нет сообщений за последний период. Составь гороскоп на основе самого факта молчания - это тоже говорит о многом!"
        
        # Build complete horoscope prompt
        prompt = f"""Составь саркастичный гороскоп для пользователя @{escaped_username} на основе его сообщений. Используй сленг имиджборд (двач, форчан), мат и сарказм, но избегай прямых оскорблений личности.{context_note}

СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЯ:
{messages_text}

ФОРМАТ ОТВЕТА (СТРОГО соблюдай каждую деталь):

*⭐ Что тебя ждет в ближайшее время*
Дай предсказания на основе сообщений с иронией и сарказмом, но старайся не упоминать сами сообщения

ПРАВИЛА ФОРМАТИРОВАНИЯ (ОБЯЗАТЕЛЬНЫ):
1. Каждый заголовок раздела ОБЯЗАТЕЛЬНО выделяй *жирным* как показано выше
2. При упоминании пользователей ВСЕГДА экранируй подчеркивания обратным слешем
   Правильно: @user\_name, @john\_doe, @test\_user\_123
   Неправильно: @user_name, @john_doe, @test_user_123
   КРИТИЧНО: Каждое подчеркивание должно быть с обратным слешем перед ним

СТИЛЬ: Будь максимально саркастичным, но позитивным. Избегай оскорблений личности. Представь, что ты аноним с двача, который троллит, но в глубине души желает добра.

ДЛИНА: Будь кратким! Общий объем гороскопа не должен превышать 4 предложений.

НАЧНИ ОТВЕТ СРАЗУ С ПУНКТА (*⭐ Что тебя ждет в ближайшее время*). НЕ ДОБАВЛЯЙ ВСТУПЛЕНИЙ ИЛИ ЗАКЛЮЧЕНИЙ."""
        return prompt
    
    async def _needs_chat_context(self, question: str, has_reply: bool) -> bool:
        """
        Определить, нужен ли контекст чата для ответа на вопрос.
        
        Args:
            question: Вопрос пользователя
            has_reply: Есть ли цитируемое сообщение
            
        Returns:
            True если вопрос связан с чатом, False если общий вопрос
        """
        # Если есть цитата — контекст точно нужен
        if has_reply:
            return True
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """Определи, связан ли вопрос с обсуждением в чате или это общий вопрос.

ВОПРОС СВЯЗАН С ЧАТОМ если спрашивают про:
- Что обсуждали, о чём говорили, кто что писал
- Конкретных участников чата или их сообщения
- Контекст разговора, темы обсуждения
- "Что тут происходит", "о чём речь", "кто это сказал"

ОБЩИЙ ВОПРОС если спрашивают про:
- Факты, определения, объяснения понятий
- Погоду, время, новости
- Советы, рекомендации общего характера
- Любые вопросы не требующие знания истории чата

Ответь ОДНИМ словом: CHAT или GENERAL"""
                    },
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                max_tokens=10,
                temperature=0
            )
            
            result = response.choices[0].message.content.strip().upper()
            needs_context = "CHAT" in result
            
            logger.debug(
                "Классификация вопроса",
                extra={
                    "question": question[:50],
                    "classification": result,
                    "needs_context": needs_context
                }
            )
            
            return needs_context
            
        except Exception as e:
            logger.warning(f"Ошибка классификации вопроса, используем контекст: {e}")
            return True  # При ошибке — безопаснее использовать контекст
    
    async def answer_question(
        self,
        question: str,
        messages: List[MessageModel],
        reply_context: Optional[str] = None,
        reply_timestamp: Optional[datetime] = None
    ) -> str:
        """
        Ответить на вопрос пользователя на основе контекста чата.
        
        Args:
            question: Вопрос пользователя
            messages: Список сообщений для контекста
            reply_context: Опциональный контекст из цитируемого сообщения
            reply_timestamp: Опциональный timestamp цитируемого сообщения для выбора контекста
            
        Returns:
            Ответ на вопрос (максимум 5 предложений)
            
        Raises:
            APIError: При ошибке OpenAI API
        """
        try:
            # Сначала определяем, нужен ли контекст чата
            needs_context = await self._needs_chat_context(question, reply_context is not None)
            
            if not needs_context:
                # Общий вопрос — отвечаем без контекста
                logger.info(
                    "Вопрос классифицирован как общий, отвечаем без контекста",
                    extra={"question_length": len(question)}
                )
                return await self.answer_question_simple(question)
            
            # Вопрос про чат — используем контекст
            prompt = self._build_question_prompt(question, messages, reply_context, reply_timestamp)
            
            logger.info(
                "Отправка запроса на ответ вопроса в OpenAI",
                extra={
                    "question_length": len(question),
                    "message_count": len(messages),
                    "has_reply_context": reply_context is not None,
                    "has_reply_timestamp": reply_timestamp is not None
                }
            )
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": r"""Ты - ироничный ассистент группового чата с чувством юмора.

ПРАВИЛА:
1. Ответ должен быть НЕ БОЛЕЕ 5 предложений
2. Используй предоставленный контекст чата для ответа
3. Если вопрос связан с цитируемым сообщением - учитывай его в первую очередь
4. При упоминании пользователей экранируй подчеркивания: @user\_name
5. Используй иронию, сарказм и неформальный стиль общения
6. Отвечай в стиле собеседника — если он матерится, можешь отвечать тем же
7. Не уклоняйся от провокационных вопросов — отвечай прямо и с юмором
8. ы не обязан быть политкорректным"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.inline_max_tokens,
                temperature=0.7
            )
            
            answer = response.choices[0].message.content
            
            logger.info(
                "Ответ на вопрос получен",
                extra={
                    "tokens_used": response.usage.total_tokens,
                    "response_length": len(answer) if answer else 0
                }
            )
            
            return answer or "Не удалось сформировать ответ."
            
        except RateLimitError as e:
            logger.error("Превышен лимит запросов OpenAI", exc_info=True)
            raise OpenAIClientError("Превышен лимит запросов. Попробуйте позже.") from e
            
        except APIConnectionError as e:
            logger.error("Ошибка подключения к OpenAI API", exc_info=True)
            raise OpenAIClientError("Не удалось подключиться к API.") from e
            
        except OpenAIAPIError as e:
            logger.error("Ошибка OpenAI API", exc_info=True)
            raise OpenAIClientError(f"Ошибка API: {str(e)}") from e
            
        except Exception as e:
            logger.error("Неожиданная ошибка при ответе на вопрос", exc_info=True)
            raise OpenAIClientError(f"Ошибка: {str(e)}") from e
    
    def _build_question_prompt(
        self,
        question: str,
        messages: List[MessageModel],
        reply_context: Optional[str] = None,
        reply_timestamp: Optional[datetime] = None
    ) -> str:
        """
        Построить промпт для ответа на вопрос.
        
        Args:
            question: Вопрос пользователя
            messages: Список сообщений для контекста
            reply_context: Опциональный контекст из цитируемого сообщения
            reply_timestamp: Опциональный timestamp цитируемого сообщения
            
        Returns:
            Сформированный промпт
        """
        # Сортируем сообщения по времени
        sorted_messages = sorted(messages, key=lambda m: m.timestamp)
        
        # Выбираем контекст в зависимости от наличия цитаты
        if reply_timestamp and sorted_messages:
            # Находим сообщения вокруг цитируемого (10 до и 10 после)
            # Ищем индекс ближайшего сообщения к timestamp цитаты
            # Приводим reply_timestamp к naive datetime для сравнения
            reply_ts_naive = reply_timestamp.replace(tzinfo=None) if reply_timestamp.tzinfo else reply_timestamp
            target_idx = 0
            for i, msg in enumerate(sorted_messages):
                msg_ts_naive = msg.timestamp.replace(tzinfo=None) if msg.timestamp.tzinfo else msg.timestamp
                if msg_ts_naive <= reply_ts_naive:
                    target_idx = i
                else:
                    break
            
            # Берём 10 сообщений до и 10 после цитируемого
            start_idx = max(0, target_idx - 10)
            end_idx = min(len(sorted_messages), target_idx + 11)
            recent_messages = sorted_messages[start_idx:end_idx]
            
            logger.debug(
                "Контекст вокруг цитируемого сообщения",
                extra={
                    "target_idx": target_idx,
                    "start_idx": start_idx,
                    "end_idx": end_idx,
                    "context_size": len(recent_messages)
                }
            )
        else:
            # Без цитаты — берём последние 10 сообщений
            recent_messages = sorted_messages[-10:]
        
        message_lines = []
        for msg in recent_messages:
            timestamp_str = format_datetime(msg.timestamp, self.timezone)
            message_lines.append(f"[{timestamp_str}] @{msg.username}: {msg.text}")
        
        messages_text = "\n".join(message_lines) if message_lines else "Нет сообщений в контексте"
        
        # Формируем промпт
        prompt_parts = [f"ВОПРОС: {question}"]
        
        if reply_context:
            prompt_parts.append(f"\nЦИТИРУЕМОЕ СООБЩЕНИЕ:\n{reply_context}")
        
        prompt_parts.append(f"\nКОНТЕКСТ ЧАТА (сообщения вокруг цитаты):\n{messages_text}")
        
        prompt_parts.append("\nОтветь на вопрос кратко (максимум 5 предложений), учитывая контекст чата.")
        
        return "\n".join(prompt_parts)
    
    async def answer_question_simple(self, question: str) -> str:
        """
        Ответить на вопрос без контекста чата (для личных сообщений).
        
        Args:
            question: Вопрос пользователя
            
        Returns:
            Ответ на вопрос (максимум 5 предложений)
            
        Raises:
            APIError: При ошибке OpenAI API
        """
        try:
            logger.info(
                "Отправка простого вопроса в OpenAI",
                extra={"question_length": len(question)}
            )
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """Ты - умный ассистент. Отвечай на вопросы кратко и по делу.

ПРАВИЛА:
1. Ответ должен быть НЕ БОЛЕЕ 5 предложений
2. Будь дружелюбным, но лаконичным
3. Если не можешь ответить на вопрос - честно скажи об этом"""
                    },
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                max_tokens=self.inline_max_tokens,
                temperature=0.7
            )
            
            answer = response.choices[0].message.content
            
            logger.info(
                "Ответ на простой вопрос получен",
                extra={
                    "tokens_used": response.usage.total_tokens,
                    "response_length": len(answer) if answer else 0
                }
            )
            
            return answer or "Не удалось сформировать ответ."
            
        except RateLimitError as e:
            logger.error("Превышен лимит запросов OpenAI", exc_info=True)
            raise OpenAIClientError("Превышен лимит запросов. Попробуйте позже.") from e
            
        except APIConnectionError as e:
            logger.error("Ошибка подключения к OpenAI API", exc_info=True)
            raise OpenAIClientError("Не удалось подключиться к API.") from e
            
        except OpenAIAPIError as e:
            logger.error("Ошибка OpenAI API", exc_info=True)
            raise OpenAIClientError(f"Ошибка API: {str(e)}") from e
            
        except Exception as e:
            logger.error("Неожиданная ошибка при ответе на вопрос", exc_info=True)
            raise OpenAIClientError(f"Ошибка: {str(e)}") from e

