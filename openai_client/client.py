"""
OpenAI client for analyzing Telegram messages.
"""
import logging
from typing import List
from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError
from database.models import MessageModel


logger = logging.getLogger(__name__)


class OpenAIClient:
    """Client for interacting with OpenAI API to analyze messages."""
    
    def __init__(self, api_key: str, base_url: str = None, model: str = "gpt-4o-mini", max_tokens: int = 4000):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key
            base_url: Optional base URL for API (defaults to OpenAI's endpoint)
            model: Model to use for analysis
            max_tokens: Maximum tokens for API requests
        """
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        
        self.client = AsyncOpenAI(**client_kwargs)
        self.model = model
        self.max_tokens = max_tokens
        logger.info(
            "OpenAI client initialized",
            extra={
                "model": model,
                "max_tokens": max_tokens,
                "base_url": base_url or "default"
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
                        "content": "Ты - аналитик групповых чатов. Твоя задача - анализировать сообщения и предоставлять краткую, структурированную сводку на русском языке."
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
            timestamp_str = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            reactions_str = ""
            
            if msg.reactions:
                reactions_list = [f"{emoji}: {count}" for emoji, count in msg.reactions.items()]
                reactions_str = f" [Реакции: {', '.join(reactions_list)}]"
            
            reply_str = ""
            if msg.reply_to_message_id:
                reply_str = f" [Ответ на сообщение #{msg.reply_to_message_id}]"
            
            message_lines.append(
                f"[{timestamp_str}] @{msg.username}: {msg.text}{reactions_str}{reply_str}"
            )
        
        messages_text = "\n".join(message_lines)
        
        # Build complete prompt
        prompt = f"""Проанализируй следующие сообщения из группового чата и предоставь краткую сводку.

СООБЩЕНИЯ:
{messages_text}

ЗАДАНИЕ:
Предоставь структурированный анализ в следующем формате:

1. **Основные темы обсуждения**
   - Перечисли главные темы, о которых говорили участники
   - Укажи, кто был наиболее активен в каждой теме

2. **Самые обсуждаемые посты**
   - Определи сообщения, которые вызвали больше всего ответов и обсуждений
   - Укажи автора и краткое содержание поста
   - Если есть номер сообщения, укажи его

3. **Лидеры по реакциям**
   - Определи пользователей, чьи сообщения собрали больше всего реакций
   - Укажи общее количество реакций для каждого пользователя
   - Отметь наиболее популярные типы реакций

4. **Общая активность**
   - Краткая статистика: количество сообщений, активных участников
   - Общее настроение в чате (позитивное, нейтральное, негативное)

Будь кратким и конкретным. Используй эмодзи для улучшения читаемости."""
        
        return prompt

