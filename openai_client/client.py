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
from .prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    QUESTION_CLASSIFIER_SYSTEM_PROMPT,
    QUESTION_WITH_CONTEXT_SYSTEM_PROMPT,
    SIMPLE_QUESTION_SYSTEM_PROMPT,
    build_analysis_user_prompt,
    build_question_user_prompt,
)


logger = logging.getLogger(__name__)


class OpenAIClientError(Exception):
    """OpenAI client error."""
    pass


class OpenAIClient:
    """Client for interacting with OpenAI API to analyze messages."""
    
    def __init__(self, api_key: str, base_url: str = None, model: str = "gpt-4o-mini", max_tokens: int = 4000, inline_max_tokens: int = 500, timezone: Optional[str] = None):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key
            base_url: Optional base URL for API (defaults to OpenAI's endpoint)
            model: Model to use for analysis
            max_tokens: Maximum tokens for API requests (analysis)
            inline_max_tokens: Maximum tokens for inline question answers
            timezone: Optional IANA timezone identifier for timestamp formatting
        """
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        
        self.client = AsyncOpenAI(**client_kwargs)
        self.model = model
        self.max_tokens = max_tokens
        self.inline_max_tokens = inline_max_tokens
        self.timezone = timezone
        logger.info(
            "OpenAI client initialized",
            extra={
                "model": model,
                "max_tokens": max_tokens,
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
            messages_text = self._format_messages_for_prompt(messages)
            prompt = build_analysis_user_prompt(messages_text)
            
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
                    {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
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
    
    def _format_messages_for_prompt(self, messages: List[MessageModel]) -> str:
        """
        Format messages list into text for prompt.
        
        Args:
            messages: List of messages to format
            
        Returns:
            Formatted messages as string
        """
        sorted_messages = sorted(messages, key=lambda m: m.timestamp)
        
        message_lines = []
        for msg in sorted_messages:
            timestamp_str = format_datetime(msg.timestamp, self.timezone)
            reactions_str = ""
            
            if msg.reactions:
                reactions_list = [f"{emoji}: {count}" for emoji, count in msg.reactions.items()]
                reactions_str = f" [Реакции: {', '.join(reactions_list)}]"
            
            message_lines.append(
                f"[{timestamp_str}] @{msg.username}: {msg.text}{reactions_str}"
            )
        
        return "\n".join(message_lines)
    
    async def _needs_chat_context(self, question: str, has_reply: bool) -> bool:
        """
        Determine if chat context is needed to answer the question.
        
        Args:
            question: User's question
            has_reply: Whether there is a quoted message
            
        Returns:
            True if question is chat-related, False if general question
        """
        if has_reply:
            return True
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": QUESTION_CLASSIFIER_SYSTEM_PROMPT},
                    {"role": "user", "content": question}
                ],
                max_tokens=10,
                temperature=0
            )
            
            result = response.choices[0].message.content.strip().upper()
            needs_context = "CHAT" in result
            
            logger.debug(
                "Question classification",
                extra={
                    "question": question[:50],
                    "classification": result,
                    "needs_context": needs_context
                }
            )
            
            return needs_context
            
        except Exception as e:
            logger.warning(f"Error classifying question, using context: {e}")
            return True
    
    async def answer_question(
        self,
        question: str,
        messages: List[MessageModel],
        reply_context: Optional[str] = None,
        reply_timestamp: Optional[datetime] = None,
        asking_user: Optional[str] = None
    ) -> str:
        """
        Answer user's question based on chat context.
        
        Args:
            question: User's question
            messages: List of messages for context
            reply_context: Optional context from quoted message
            reply_timestamp: Optional timestamp of quoted message for context selection
            asking_user: Optional username of the person asking
            
        Returns:
            Answer to the question (max 5 sentences)
            
        Raises:
            APIError: On OpenAI API error
        """
        try:
            needs_context = await self._needs_chat_context(question, reply_context is not None)
            
            if not needs_context:
                logger.info(
                    "Question classified as general, answering without context",
                    extra={"question_length": len(question)}
                )
                return await self.answer_question_simple(question)
            
            messages_text = self._get_context_messages_text(messages, reply_timestamp)
            prompt = build_question_user_prompt(question, messages_text, reply_context, asking_user)
            
            logger.info(
                "Sending question request to OpenAI",
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
                    {"role": "system", "content": QUESTION_WITH_CONTEXT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.inline_max_tokens,
                temperature=0.8
            )
            
            answer = response.choices[0].message.content
            
            logger.info(
                "Question answer received",
                extra={
                    "tokens_used": response.usage.total_tokens,
                    "response_length": len(answer) if answer else 0
                }
            )
            
            return answer or "Не удалось сформировать ответ."
            
        except RateLimitError as e:
            logger.error("OpenAI rate limit exceeded", exc_info=True)
            raise OpenAIClientError("Превышен лимит запросов. Попробуйте позже.") from e
            
        except APIConnectionError as e:
            logger.error("OpenAI API connection error", exc_info=True)
            raise OpenAIClientError("Не удалось подключиться к API.") from e
            
        except OpenAIAPIError as e:
            logger.error("OpenAI API error", exc_info=True)
            raise OpenAIClientError(f"Ошибка API: {str(e)}") from e
            
        except Exception as e:
            logger.error("Unexpected error while answering question", exc_info=True)
            raise OpenAIClientError(f"Ошибка: {str(e)}") from e
    
    def _get_context_messages_text(
        self,
        messages: List[MessageModel],
        reply_timestamp: Optional[datetime] = None
    ) -> str:
        """
        Get formatted context messages around reply or recent messages.
        
        Args:
            messages: All available messages
            reply_timestamp: Optional timestamp to center context around
            
        Returns:
            Formatted messages text
        """
        sorted_messages = sorted(messages, key=lambda m: m.timestamp)
        
        if reply_timestamp and sorted_messages:
            reply_ts_naive = reply_timestamp.replace(tzinfo=None) if reply_timestamp.tzinfo else reply_timestamp
            target_idx = 0
            for i, msg in enumerate(sorted_messages):
                msg_ts_naive = msg.timestamp.replace(tzinfo=None) if msg.timestamp.tzinfo else msg.timestamp
                if msg_ts_naive <= reply_ts_naive:
                    target_idx = i
                else:
                    break
            
            start_idx = max(0, target_idx - 10)
            end_idx = min(len(sorted_messages), target_idx + 11)
            recent_messages = sorted_messages[start_idx:end_idx]
            
            logger.debug(
                "Context around quoted message",
                extra={
                    "target_idx": target_idx,
                    "start_idx": start_idx,
                    "end_idx": end_idx,
                    "context_size": len(recent_messages)
                }
            )
        else:
            recent_messages = sorted_messages[-10:]
        
        message_lines = []
        for msg in recent_messages:
            timestamp_str = format_datetime(msg.timestamp, self.timezone)
            message_lines.append(f"[{timestamp_str}] @{msg.username}: {msg.text}")
        
        return "\n".join(message_lines) if message_lines else "Нет сообщений в контексте"
    
    async def answer_question_simple(self, question: str) -> str:
        """
        Answer question without chat context (for private messages).
        
        Args:
            question: User's question
            
        Returns:
            Answer to the question (max 5 sentences)
            
        Raises:
            APIError: On OpenAI API error
        """
        try:
            logger.info(
                "Sending simple question to OpenAI",
                extra={"question_length": len(question)}
            )
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SIMPLE_QUESTION_SYSTEM_PROMPT},
                    {"role": "user", "content": question}
                ],
                max_tokens=self.inline_max_tokens,
                temperature=0.8
            )
            
            answer = response.choices[0].message.content
            
            logger.info(
                "Simple question answer received",
                extra={
                    "tokens_used": response.usage.total_tokens,
                    "response_length": len(answer) if answer else 0
                }
            )
            
            return answer or "Не удалось сформировать ответ."
            
        except RateLimitError as e:
            logger.error("OpenAI rate limit exceeded", exc_info=True)
            raise OpenAIClientError("Превышен лимит запросов. Попробуйте позже.") from e
            
        except APIConnectionError as e:
            logger.error("OpenAI API connection error", exc_info=True)
            raise OpenAIClientError("Не удалось подключиться к API.") from e
            
        except OpenAIAPIError as e:
            logger.error("OpenAI API error", exc_info=True)
            raise OpenAIClientError(f"Ошибка API: {str(e)}") from e
            
        except Exception as e:
            logger.error("Unexpected error while answering simple question", exc_info=True)
            raise OpenAIClientError(f"Ошибка: {str(e)}") from e
