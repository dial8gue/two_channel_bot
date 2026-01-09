"""
OpenAI client for analyzing Telegram messages.
"""
import logging
from typing import List, Optional
from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError
from database.models import MessageModel
from utils.timezone_helper import format_datetime


logger = logging.getLogger(__name__)


class OpenAIClient:
    """Client for interacting with OpenAI API to analyze messages."""
    
    def __init__(self, api_key: str, base_url: str = None, model: str = "gpt-4o-mini", max_tokens: int = 4000, horoscope_max_tokens: int = 2000, timezone: Optional[str] = None):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key
            base_url: Optional base URL for API (defaults to OpenAI's endpoint)
            model: Model to use for analysis
            max_tokens: Maximum tokens for API requests (analysis)
            horoscope_max_tokens: Maximum tokens for horoscope requests
            timezone: Optional IANA timezone identifier for timestamp formatting
        """
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        
        self.client = AsyncOpenAI(**client_kwargs)
        self.model = model
        self.max_tokens = max_tokens
        self.horoscope_max_tokens = horoscope_max_tokens
        self.timezone = timezone
        logger.info(
            "OpenAI client initialized",
            extra={
                "model": model,
                "max_tokens": max_tokens,
                "horoscope_max_tokens": horoscope_max_tokens,
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
            raise APIError(
                "Превышен лимит запросов к OpenAI API. Попробуйте позже."
            ) from e
            
        except APIConnectionError as e:
            logger.error("Failed to connect to OpenAI API", exc_info=True)
            raise APIError(
                "Не удалось подключиться к OpenAI API. Проверьте соединение."
            ) from e
            
        except APIError as e:
            logger.error("OpenAI API error", exc_info=True)
            raise APIError(
                f"Ошибка OpenAI API: {str(e)}"
            ) from e
            
        except Exception as e:
            logger.error("Unexpected error during analysis", exc_info=True)
            raise APIError(
                f"Неожиданная ошибка при анализе: {str(e)}"
            ) from e
    
    async def create_horoscope(self, messages: List[MessageModel], username: str) -> str:
        """
        Create an ironic horoscope based on user's messages.
        
        Args:
            messages: List of user's messages to analyze
            username: Username for personalization
            
        Returns:
            Horoscope result as formatted text
            
        Raises:
            APIError: If OpenAI API returns an error
            RateLimitError: If rate limit is exceeded
            APIConnectionError: If connection to API fails
        """
        if not messages:
            logger.warning("No messages provided for horoscope")
            return f"@{username.replace('_', r'\_')}, у вас нет сообщений за последние 12 часов. Звезды молчат... 🌟"
        
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
                temperature=0.8  # Более высокая температура для креативности
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
            raise APIError(
                "Превышен лимит запросов к OpenAI API. Попробуйте позже."
            ) from e
            
        except APIConnectionError as e:
            logger.error("Failed to connect to OpenAI API", exc_info=True)
            raise APIError(
                "Не удалось подключиться к OpenAI API. Проверьте соединение."
            ) from e
            
        except APIError as e:
            logger.error("OpenAI API error", exc_info=True)
            raise APIError(
                f"Ошибка OpenAI API: {str(e)}"
            ) from e
            
        except Exception as e:
            logger.error("Unexpected error during horoscope creation", exc_info=True)
            raise APIError(
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
        
        messages_text = "\n".join(message_lines)
        
        # Escape username for Markdown
        escaped_username = username.replace('_', r'\_')
        
        # Build complete horoscope prompt
        prompt = f"""Составь максимально кринжовый и токсичный гороскоп для пользователя @{escaped_username} на основе его сообщений за последние 12 часов. Используй имиджбордовский слэнг, мемы, мат и шутки на грани.

СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЯ:
{messages_text}

ФОРМАТ ОТВЕТА (СТРОГО соблюдай каждую деталь):

*⭐ Анализ твоего кринжа*
- Разбери стиль общения пользователя в максимально токсичном ключе
- Определи его "астрологический тип" используя имиджбордовские мемы (например: "Знак Анона", "Восходящий Шизик", "Луна в доме Аутизма")
- Оцени уровень кринжа и социофобии по шкале от "норми" до "полный дегенерат"
- Используй слэнг: анон, шизик, тян, кун, норми, чд, соевый, базированный, кринж, etc.

*🌟 Что тебя ждет, анончик*
- Дай максимально едкие предсказания на основе его сообщений
- Предскажи его судьбу в чатах и в жизни
- Какие темы будут его триггерить
- Совместимость с другими участниками (кого он будет бесить)
- Используй мат и грубые выражения где уместно

*💫 Советы от звезд (которые ты не послушаешь)*
- Максимально саркастичные и токсичные советы
- Что нужно делать, чтобы стать менее кринжовым (спойлер: ничего не поможет)
- Какие мемы использовать, чтобы не выглядеть как кринж
- Предупреждения о том, как не стать еще большим лузером

ПРАВИЛА ФОРМАТИРОВАНИЯ (ОБЯЗАТЕЛЬНЫ):
1. Каждый заголовок раздела ОБЯЗАТЕЛЬНО выделяй *жирным* как показано выше
2. При упоминании пользователей ВСЕГДА экранируй подчеркивания обратным слешем
   Правильно: @user\_name, @john\_doe, @test\_user\_123
   Неправильно: @user_name, @john_doe, @test_user_123
   КРИТИЧНО: Каждое подчеркивание должно быть с обратным слешем перед ним
3. Используй астрологическую терминологию в максимально кринжовом ключе

СТИЛЬ: Будь максимально токсичным, используй имиджбордовский слэнг, мемы, мат. Не стесняйся грубых выражений и едких шуток. Гороскоп должен быть персональным, основанным на реальных сообщениях, но при этом максимально кринжовым и на грани. Представь, что ты анон с /b/, который решил потроллить пользователя.

НЕ ДОБАВЛЯЙ ВСТУПЛЕНИЙ."""
        return prompt

