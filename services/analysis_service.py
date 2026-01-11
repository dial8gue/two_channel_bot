"""
Analysis service for analyzing messages using OpenAI.
"""
import logging
import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Optional

from database.models import MessageModel
from database.repository import MessageRepository
from openai_client.client import OpenAIClient
from utils.cache_manager import CacheManager
from utils.debounce_manager import DebounceManager


logger = logging.getLogger(__name__)


class AnalysisService:
    """Service for analyzing messages with caching and debounce support."""
    
    # Operation name for debounce
    ANALYSIS_OPERATION = "analyze_messages"
    INLINE_OPERATION = "inline_question"
    
    def __init__(
        self,
        message_repository: MessageRepository,
        openai_client: OpenAIClient,
        cache_manager: CacheManager,
        debounce_manager: DebounceManager,
        debounce_interval_seconds: int,
        cache_ttl_minutes: int,
        analysis_period_hours: int,
        inline_debounce_seconds: int = 3600
    ):
        """
        Initialize analysis service.
        
        Args:
            message_repository: Repository for message operations
            openai_client: Client for OpenAI API
            cache_manager: Manager for caching results
            debounce_manager: Manager for debouncing operations
            debounce_interval_seconds: Minimum interval between analysis requests
            cache_ttl_minutes: Time to live for cached results
            analysis_period_hours: Default analysis period in hours
            inline_debounce_seconds: Minimum interval between inline questions for users
        """
        self.message_repository = message_repository
        self.openai_client = openai_client
        self.cache_manager = cache_manager
        self.debounce_manager = debounce_manager
        self.debounce_interval_seconds = debounce_interval_seconds
        self.cache_ttl_minutes = cache_ttl_minutes
        self.analysis_period_hours = analysis_period_hours
        self.inline_debounce_seconds = inline_debounce_seconds
    
    async def analyze_messages_with_debounce(
        self,
        hours: int,
        chat_id: int,
        user_id: int,
        operation_type: str,
        bypass_debounce: bool = False
    ) -> tuple[str, bool]:
        """
        Analyze messages with chat-level debounce protection.
        
        This method wraps analyze_messages with chat-level debounce tracking.
        The debounce is applied per chat and operation type, allowing different
        chats to have independent rate limiting.
        
        Args:
            hours: Analysis period in hours
            chat_id: Chat ID for analysis and debounce tracking
            user_id: User ID for logging purposes
            operation_type: Operation identifier (e.g., "anal", "deep_anal")
            bypass_debounce: If True, skip debounce check (for admin users)
            
        Returns:
            Tuple of (analysis_result, from_cache) where:
                - analysis_result: The analysis text
                - from_cache: True if result was from cache, False if new analysis
                
        Raises:
            ValueError: If debounced, with remaining time in seconds in the message
            Exception: If analysis fails
        """
        try:
            # Format operation key as "{operation_type}:{chat_id}"
            operation_key = f"{operation_type}:{chat_id}"
            
            logger.info(
                "Starting chat-level debounced analysis",
                extra={
                    "operation_key": operation_key,
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "hours": hours,
                    "bypass_debounce": bypass_debounce
                }
            )
            
            # First, check if we have a cached result
            # We need to get messages to generate cache key
            start_time = datetime.now() - timedelta(hours=hours)
            messages = await self.message_repository.get_by_period(
                start_time=start_time,
                chat_id=chat_id
            )
            
            if not messages:
                logger.warning("No messages found for analysis period")
                return "Нет сообщений для анализа за указанный период.", False
            
            # Generate cache key and check cache
            cache_key = self._generate_cache_key(messages)
            cached_result = await self.cache_manager.get(cache_key)
            
            if cached_result:
                # Return cached result without debounce check/set
                logger.info("Returning cached analysis result (no debounce applied)")
                return cached_result, True
            
            # No cache hit - check and set debounce before making API call
            if not bypass_debounce:
                can_execute, remaining = await self.debounce_manager.can_execute(
                    operation=operation_key,
                    interval_seconds=self.debounce_interval_seconds
                )
                
                if not can_execute:
                    logger.warning(
                        f"Analysis blocked by chat-level debounce",
                        extra={
                            "operation_key": operation_key,
                            "user_id": user_id,
                            "remaining_seconds": remaining
                        }
                    )
                    raise ValueError(f"{remaining}")
                
                # Mark operation as executed IMMEDIATELY after check passes
                # This prevents concurrent requests from bypassing debounce
                await self.debounce_manager.mark_executed(operation_key)
                logger.debug(
                    f"Marked operation as executed for debounce (before API call)",
                    extra={"operation_key": operation_key}
                )
            else:
                logger.debug(
                    "Bypassing debounce check",
                    extra={"user_id": user_id, "operation_key": operation_key}
                )
            
            # Perform new analysis with OpenAI
            logger.info("Performing new analysis with OpenAI")
            analysis_result = await self.openai_client.analyze_messages(messages)
            
            # Cache the result
            await self.cache_manager.set(
                key=cache_key,
                value=analysis_result,
                ttl_minutes=self.cache_ttl_minutes
            )
            
            from_cache = False
            
            logger.info(
                "Chat-level debounced analysis completed",
                extra={
                    "operation_key": operation_key,
                    "user_id": user_id,
                    "from_cache": from_cache,
                    "message_count": len(messages)
                }
            )
            
            return analysis_result, from_cache
            
        except ValueError:
            # Re-raise debounce errors
            raise
        except Exception as e:
            logger.error(
                f"Failed to analyze messages with debounce: {e}",
                extra={
                    "operation_type": operation_type,
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "hours": hours
                },
                exc_info=True
            )
            raise
    
    async def analyze_messages(
        self,
        hours: Optional[int] = None,
        chat_id: Optional[int] = None
    ) -> tuple[str, bool]:
        """
        Analyze messages from the specified period.
        
        Legacy method for backward compatibility with tests.
        Delegates to analyze_messages_with_debounce with default operation type.
        
        Args:
            hours: Number of hours to analyze (uses default if not specified)
            chat_id: Optional chat ID to filter by
            
        Returns:
            Tuple of (analysis_result, from_cache) where:
                - analysis_result: The analysis text
                - from_cache: True if result was from cache, False if new analysis
                
        Raises:
            ValueError: If debounce check fails
            Exception: If analysis fails
        """
        period_hours = hours or self.analysis_period_hours
        effective_chat_id = chat_id or 0  # Use 0 as default for legacy behavior
        
        return await self.analyze_messages_with_debounce(
            hours=period_hours,
            chat_id=effective_chat_id,
            user_id=0,  # Legacy method doesn't track user
            operation_type=self.ANALYSIS_OPERATION,
            bypass_debounce=False
        )
    
    async def answer_question_with_debounce(
        self,
        question: str,
        chat_id: int,
        user_id: int,
        reply_context: Optional[str] = None,
        reply_timestamp: Optional[datetime] = None,
        bypass_debounce: bool = False
    ) -> str:
        """
        Answer user question with spam protection (debounce).
        
        Args:
            question: User question
            chat_id: Chat ID for context retrieval
            user_id: User ID for debounce
            reply_context: Optional context from quoted message
            reply_timestamp: Optional timestamp of quoted message for context selection
            bypass_debounce: Skip debounce check (for admin)
            
        Returns:
            Answer to the question
            
        Raises:
            ValueError: If debounced, with remaining time in seconds
            Exception: If answer generation fails
        """
        try:
            # Format operation key for debounce (per user per chat)
            operation_key = f"{self.INLINE_OPERATION}:{user_id}:{chat_id}"
            
            logger.info(
                "Starting inline question processing",
                extra={
                    "operation_key": operation_key,
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "question_length": len(question),
                    "has_reply_context": reply_context is not None,
                    "has_reply_timestamp": reply_timestamp is not None,
                    "bypass_debounce": bypass_debounce
                }
            )
            
            # Check debounce (if not admin)
            if not bypass_debounce:
                can_execute, remaining = await self.debounce_manager.can_execute(
                    operation=operation_key,
                    interval_seconds=self.inline_debounce_seconds
                )
                
                if not can_execute:
                    logger.warning(
                        "Inline question blocked by debounce",
                        extra={
                            "operation_key": operation_key,
                            "user_id": user_id,
                            "remaining_seconds": remaining
                        }
                    )
                    raise ValueError(f"{remaining}")
                
                # Mark operation as executed immediately after check
                await self.debounce_manager.mark_executed(operation_key)
                logger.debug(
                    "Operation marked as executed for debounce",
                    extra={"operation_key": operation_key}
                )
            else:
                logger.debug(
                    "Bypassing debounce check for admin",
                    extra={"user_id": user_id, "operation_key": operation_key}
                )
            
            # Get message context (last 6 hours)
            start_time = datetime.now() - timedelta(hours=6)
            messages = await self.message_repository.get_by_period(
                start_time=start_time,
                chat_id=chat_id
            )
            
            # Generate answer via OpenAI
            logger.info("Generating answer via OpenAI")
            answer = await self.openai_client.answer_question(
                question=question,
                messages=messages,
                reply_context=reply_context,
                reply_timestamp=reply_timestamp
            )
            
            logger.info(
                "Question answer generated",
                extra={
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "answer_length": len(answer),
                    "context_messages": len(messages)
                }
            )
            
            return answer
            
        except ValueError:
            # Re-raise debounce errors
            raise
        except Exception as e:
            logger.error(
                f"Error answering question: {e}",
                extra={
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "question": question[:100]
                },
                exc_info=True
            )
            raise
    


    
    def _generate_cache_key(self, messages: List[MessageModel]) -> str:
        """
        Generate a cache key based on message content hash.
        
        The cache key is generated from:
        - Message IDs
        - Message texts
        - Reaction counts
        
        This ensures that identical message sets return the same cache key,
        while any changes (new messages, updated reactions) generate a new key.
        
        Args:
            messages: List of messages to generate key for
            
        Returns:
            SHA256 hash string to use as cache key
        """
        try:
            # Sort messages by ID for consistent ordering
            sorted_messages = sorted(messages, key=lambda m: (m.chat_id, m.message_id))
            
            # Build a string representation of all messages
            message_data = []
            for msg in sorted_messages:
                # Include message ID, text, and reaction summary
                reaction_summary = json.dumps(msg.reactions, sort_keys=True)
                message_data.append(
                    f"{msg.chat_id}:{msg.message_id}:{msg.text}:{reaction_summary}"
                )
            
            # Create hash of the combined data
            combined = "|".join(message_data)
            cache_key = hashlib.sha256(combined.encode('utf-8')).hexdigest()
            
            logger.debug(
                f"Generated cache key for {len(messages)} messages",
                extra={
                    "cache_key": cache_key[:16] + "...",
                    "message_count": len(messages)
                }
            )
            
            return cache_key
            
        except Exception as e:
            logger.error(f"Error generating cache key: {e}", exc_info=True)
            # Return a timestamp-based key as fallback (won't cache effectively)
            return f"fallback_{datetime.now().isoformat()}"
