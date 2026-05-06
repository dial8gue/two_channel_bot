"""
OpenAI client for analyzing Telegram messages.
"""
import base64
import logging
from datetime import datetime
from typing import List, Optional
from openai import AsyncOpenAI, RateLimitError, APIConnectionError
from openai import APIError as OpenAIAPIError
from database.models import MessageModel
from utils.timezone_helper import format_datetime
from utils.message_formatter import MessageFormatter
from .prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    QUESTION_CLASSIFIER_SYSTEM_PROMPT,
    QUESTION_WITH_CONTEXT_SYSTEM_PROMPT,
    SIMPLE_QUESTION_SYSTEM_PROMPT,
    IMAGE_DESCRIPTION_SYSTEM_PROMPT,
    build_analysis_user_prompt,
    build_question_user_prompt,
)


logger = logging.getLogger(__name__)


class OpenAIClientError(Exception):
    """OpenAI client error."""
    pass


class OpenAIClient:
    """Client for interacting with OpenAI API to analyze messages."""
    
    def __init__(self, api_key: str, base_url: str = None, model: str = "gpt-4o-mini", classifier_model: str = "deepseek/deepseek-chat", max_tokens: int = 4000, inline_max_tokens: int = 500, timezone: Optional[str] = None, vision_model: str = "google/gemini-2.5-flash", vision_enabled: bool = True, vision_max_tokens: int = 2000):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key
            base_url: Optional base URL for API (defaults to OpenAI's endpoint)
            model: Model to use for analysis
            classifier_model: Model to use for question classification
            max_tokens: Maximum tokens for API requests (analysis)
            inline_max_tokens: Maximum tokens for inline question answers
            timezone: Optional IANA timezone identifier for timestamp formatting
            vision_model: Model to use for image recognition
            vision_enabled: Whether image recognition is enabled
            vision_max_tokens: Maximum tokens for vision API requests
        """
        import httpx
        # Read timeout resets on each chunk received, so long generation won't be interrupted
        self._timeout = httpx.Timeout(connect=30.0, read=60.0, write=30.0, pool=30.0)
        self._api_key = api_key
        self._base_url = base_url
        self.client = self._build_client(api_key, base_url)
        self.model = model
        self.default_model = model  # Store default for reference
        self.classifier_model = classifier_model
        self.max_tokens = max_tokens
        self.inline_max_tokens = inline_max_tokens
        self.timezone = timezone
        self.vision_model = vision_model
        self.vision_enabled = vision_enabled
        self.vision_max_tokens = vision_max_tokens
        logger.info(
            "OpenAI client initialized",
            extra={
                "model": model,
                "classifier_model": classifier_model,
                "max_tokens": max_tokens,
                "inline_max_tokens": inline_max_tokens,
                "base_url": base_url or "default",
                "timezone": timezone or "UTC",
                "vision_model": vision_model,
                "vision_enabled": vision_enabled,
                "vision_max_tokens": vision_max_tokens
            }
        )
    
    def _build_client(self, api_key: str, base_url: Optional[str]) -> AsyncOpenAI:
        """Build a new AsyncOpenAI client with given credentials."""
        kwargs = {"api_key": api_key, "timeout": self._timeout}
        if base_url:
            kwargs["base_url"] = base_url
        return AsyncOpenAI(**kwargs)
    
    @staticmethod
    def mask_api_key(api_key: Optional[str]) -> str:
        """
        Return a masked representation of the API key safe for logging/display.
        
        Examples:
            "sk-or-v1-a32cd4..."  →  "sk-or-v1…7629a"
            ""/None               →  "(not set)"
        """
        if not api_key:
            return "(not set)"
        if len(api_key) <= 12:
            return "***"
        return f"{api_key[:8]}…{api_key[-4:]}"
    
    def set_api_key(self, api_key: str) -> None:
        """
        Replace the API key. Internally rebuilds the AsyncOpenAI client.
        """
        if not api_key or not api_key.strip():
            raise ValueError("API key cannot be empty")
        self._api_key = api_key.strip()
        self.client = self._build_client(self._api_key, self._base_url)
        logger.info(
            "OpenAI API key changed",
            extra={"api_key": self.mask_api_key(self._api_key)},
        )
    
    def get_api_key_masked(self) -> str:
        """Return masked current API key (safe for display)."""
        return self.mask_api_key(self._api_key)
    
    def set_base_url(self, base_url: Optional[str]) -> None:
        """
        Replace the base URL. Pass empty string or None to reset to OpenAI default.
        Rebuilds the AsyncOpenAI client.
        """
        value = base_url.strip() if base_url else None
        self._base_url = value or None
        self.client = self._build_client(self._api_key, self._base_url)
        logger.info(
            "OpenAI base URL changed",
            extra={"base_url": self._base_url or "default"},
        )
    
    def get_base_url(self) -> str:
        """Return current base URL or 'default' if not set."""
        return self._base_url or "default"
    
    def set_model(self, model: str) -> None:
        """
        Change the model used for API requests.
        
        Args:
            model: New model name to use
        """
        old_model = self.model
        self.model = model
        logger.info(
            "OpenAI model changed",
            extra={"old_model": old_model, "new_model": model}
        )
    
    def get_model(self) -> str:
        """
        Get the current model name.
        
        Returns:
            Current model name
        """
        return self.model

    def set_classifier_model(self, model: str) -> None:
        """
        Change the classifier model used for question routing (CHAT/GENERAL).
        
        Args:
            model: New classifier model name
        """
        old_model = self.classifier_model
        self.classifier_model = model
        logger.info(
            "Classifier model changed",
            extra={"old_model": old_model, "new_model": model},
        )
    
    def get_classifier_model(self) -> str:
        """Get the current classifier model name."""
        return self.classifier_model
    
    def set_vision_model(self, model: str) -> None:
        """
        Change the vision model used for image description.
        
        Args:
            model: New vision model name
        """
        old_model = self.vision_model
        self.vision_model = model
        logger.info(
            "Vision model changed",
            extra={"old_model": old_model, "new_model": model},
        )
    
    def get_vision_model(self) -> str:
        """Get the current vision model name."""
        return self.vision_model

    @staticmethod
    def _extract_reasoning_fallback(response) -> Optional[str]:
        """
        Try to extract answer text from reasoning fields when content is empty.
        
        Some OpenRouter reasoning models (e.g. z-ai/glm-4.7, deepseek-r1) may return
        200 OK with empty `message.content` while the useful text sits in
        `message.reasoning` or the last entry of `message.reasoning_details`.
        
        Returns the extracted text or None if nothing usable is found.
        """
        try:
            dump = response.model_dump() if hasattr(response, "model_dump") else {}
            choices = dump.get("choices") or []
            if not choices:
                return None
            msg = choices[0].get("message") or {}
            
            reasoning = msg.get("reasoning")
            if isinstance(reasoning, str) and reasoning.strip():
                return reasoning.strip()
            
            details = msg.get("reasoning_details")
            if isinstance(details, list) and details:
                # Берём последний фрагмент — обычно это итоговый вывод модели
                for entry in reversed(details):
                    if not isinstance(entry, dict):
                        continue
                    text = entry.get("text") or entry.get("content") or entry.get("summary")
                    if isinstance(text, str) and text.strip():
                        return text.strip()
        except Exception as e:
            logger.warning(f"Failed to extract reasoning fallback: {e}")
        return None
    
    def _log_empty_response(self, method: str, response) -> None:
        """
        Log diagnostic info when API returns empty content.
        
        Happens when provider returns 200 OK but content is empty/None.
        Common causes: unknown model id, provider refusal, content filter,
        max_tokens hit before any text, OpenRouter routing failure.
        """
        try:
            choice = response.choices[0] if response.choices else None
            msg = getattr(choice, "message", None) if choice else None
            finish_reason = getattr(choice, "finish_reason", None) if choice else None
            refusal = getattr(msg, "refusal", None) if msg else None
            model_used = getattr(response, "model", None)
            usage = getattr(response, "usage", None)
            # OpenRouter-specific error field
            raw_error = None
            try:
                raw = response.model_dump() if hasattr(response, "model_dump") else {}
                raw_error = raw.get("error")
            except Exception:
                raw = {}
            
            logger.error(
                "Empty response content from model API",
                extra={
                    "method": method,
                    "configured_model": self.model,
                    "model_returned": model_used,
                    "finish_reason": finish_reason,
                    "refusal": refusal,
                    "prompt_tokens": getattr(usage, "prompt_tokens", None),
                    "completion_tokens": getattr(usage, "completion_tokens", None),
                    "raw_error": raw_error,
                    "response_dump": raw,
                }
            )
        except Exception as e:
            logger.error(f"Failed to log empty response details: {e}", exc_info=True)
    
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
            
            # Post-process: escape underscores in @username mentions
            if analysis:
                analysis = MessageFormatter.escape_usernames_markdown(analysis)
            
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
                "Превышен лимит запросов к OpenAI API. Попробуй позже."
            ) from e
            
        except APIConnectionError as e:
            logger.error("Failed to connect to OpenAI API", exc_info=True)
            raise OpenAIClientError(
                "Не удалось подключиться к OpenAI API. Проверь соединение."
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
                model=self.classifier_model,
                messages=[
                    {"role": "system", "content": QUESTION_CLASSIFIER_SYSTEM_PROMPT},
                    {"role": "user", "content": question}
                ],
                max_tokens=10,
                temperature=0
            )
            
            result = response.choices[0].message.content.strip().upper()
            needs_context = "GENERAL" not in result
            
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
        asking_user: Optional[str] = None,
        image_description: Optional[str] = None
    ) -> str:
        """
        Answer user's question based on chat context.
        
        Args:
            question: User's question
            messages: List of messages for context
            reply_context: Optional context from quoted message
            reply_timestamp: Optional timestamp of quoted message for context selection
            asking_user: Optional username of the person asking
            image_description: Optional description of attached image
            
        Returns:
            Answer to the question (max 5 sentences)
            
        Raises:
            APIError: On OpenAI API error
        """
        try:
            needs_context = await self._needs_chat_context(question, reply_context is not None)
            
            if not needs_context and not image_description:
                logger.info(
                    "Question classified as general, answering without context",
                    extra={"question_length": len(question)}
                )
                return await self.answer_question_simple(question)
            
            messages_text = self._get_context_messages_text(messages, reply_timestamp)
            prompt = build_question_user_prompt(question, messages_text, reply_context, asking_user, image_description)
            
            logger.info(
                "Sending question request to OpenAI",
                extra={
                    "question_length": len(question),
                    "message_count": len(messages),
                    "has_reply_context": reply_context is not None,
                    "has_reply_timestamp": reply_timestamp is not None,
                    "has_image": image_description is not None
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
            
            # Post-process: escape underscores in @username mentions
            if answer:
                answer = MessageFormatter.escape_usernames_markdown(answer)
            
            logger.info(
                "Question answer received",
                extra={
                    "tokens_used": response.usage.total_tokens,
                    "response_length": len(answer) if answer else 0,
                    "finish_reason": response.choices[0].finish_reason,
                    "model_used": getattr(response, "model", self.model),
                }
            )
            
            if not answer:
                self._log_empty_response("answer_question", response)
                answer = self._extract_reasoning_fallback(response)
                if answer:
                    logger.warning(
                        "Recovered answer from reasoning fallback",
                        extra={"method": "answer_question", "recovered_length": len(answer)},
                    )
                    answer = MessageFormatter.escape_usernames_markdown(answer)
            
            return answer or "Что-то пошло не так! Господи помилуй."
            
        except RateLimitError as e:
            logger.error("OpenAI rate limit exceeded", exc_info=True)
            raise OpenAIClientError("Превышен лимит запросов. Попробуй позже.") from e
            
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
                    "response_length": len(answer) if answer else 0,
                    "finish_reason": response.choices[0].finish_reason,
                    "model_used": getattr(response, "model", self.model),
                }
            )
            
            if not answer:
                self._log_empty_response("answer_question_simple", response)
                answer = self._extract_reasoning_fallback(response)
                if answer:
                    logger.warning(
                        "Recovered answer from reasoning fallback",
                        extra={"method": "answer_question_simple", "recovered_length": len(answer)},
                    )
            
            return answer or "Что-то пошло не так! Господи помилуй."
            
        except RateLimitError as e:
            logger.error("OpenAI rate limit exceeded", exc_info=True)
            raise OpenAIClientError("Превышен лимит запросов. Попробуй позже.") from e
            
        except APIConnectionError as e:
            logger.error("OpenAI API connection error", exc_info=True)
            raise OpenAIClientError("Не удалось подключиться к API.") from e
            
        except OpenAIAPIError as e:
            logger.error("OpenAI API error", exc_info=True)
            raise OpenAIClientError(f"Ошибка API: {str(e)}") from e
            
        except Exception as e:
            logger.error("Unexpected error while answering simple question", exc_info=True)
            raise OpenAIClientError(f"Ошибка: {str(e)}") from e

    async def describe_image(self, image_data: bytes) -> str:
        """
        Describe image content using vision model.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Text description of the image
            
        Raises:
            OpenAIClientError: If API call fails or vision is disabled
        """
        if not self.vision_enabled:
            raise OpenAIClientError("Распознавание изображений отключено.")
        
        try:
            b64_image = base64.b64encode(image_data).decode("utf-8")
            
            logger.info(
                "Sending image to vision model",
                extra={
                    "vision_model": self.vision_model,
                    "image_size_bytes": len(image_data)
                }
            )
            
            response = await self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {"role": "system", "content": IMAGE_DESCRIPTION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=self.vision_max_tokens,
                temperature=0.3
            )
            
            description = response.choices[0].message.content
            
            logger.info(
                "Image described successfully",
                extra={
                    "tokens_used": response.usage.total_tokens,
                    "description_length": len(description) if description else 0
                }
            )
            
            return description or "Не удалось описать изображение."
            
        except RateLimitError as e:
            logger.error("Vision API rate limit exceeded", exc_info=True)
            raise OpenAIClientError("Превышен лимит запросов к API. Попробуй позже.") from e
            
        except APIConnectionError as e:
            logger.error("Vision API connection error", exc_info=True)
            raise OpenAIClientError("Не удалось подключиться к API.") from e
            
        except OpenAIAPIError as e:
            logger.error("Vision API error", exc_info=True)
            raise OpenAIClientError(f"Ошибка API: {str(e)}") from e
            
        except Exception as e:
            logger.error("Unexpected error describing image", exc_info=True)
            raise OpenAIClientError(f"Ошибка при распознавании изображения: {str(e)}") from e
