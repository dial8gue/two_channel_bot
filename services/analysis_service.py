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
    
    def __init__(
        self,
        message_repository: MessageRepository,
        openai_client: OpenAIClient,
        cache_manager: CacheManager,
        debounce_manager: DebounceManager,
        debounce_interval_seconds: int,
        cache_ttl_minutes: int,
        analysis_period_hours: int
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
        """
        self.message_repository = message_repository
        self.openai_client = openai_client
        self.cache_manager = cache_manager
        self.debounce_manager = debounce_manager
        self.debounce_interval_seconds = debounce_interval_seconds
        self.cache_ttl_minutes = cache_ttl_minutes
        self.analysis_period_hours = analysis_period_hours
    
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
            
            # Check debounce unless bypassed
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
            else:
                logger.debug(
                    "Bypassing debounce check",
                    extra={"user_id": user_id, "operation_key": operation_key}
                )
            
            # Call existing analyze_messages method for actual analysis
            # Note: We pass chat_id to filter messages for this specific chat
            analysis_result, from_cache = await self._analyze_without_debounce(
                hours=hours,
                chat_id=chat_id
            )
            
            # Mark operation as executed for debounce (only if not from cache)
            if not from_cache and not bypass_debounce:
                await self.debounce_manager.mark_executed(operation_key)
                logger.debug(
                    f"Marked operation as executed for debounce",
                    extra={"operation_key": operation_key}
                )
            
            logger.info(
                "Chat-level debounced analysis completed",
                extra={
                    "operation_key": operation_key,
                    "user_id": user_id,
                    "from_cache": from_cache
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
        
        This method implements:
        1. Debounce check to prevent rapid repeated requests
        2. Cache check to avoid redundant OpenAI API calls
        3. Message retrieval and analysis
        4. Result caching for future requests
        
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
        try:
            # Use default period if not specified
            period_hours = hours or self.analysis_period_hours
            
            logger.info(
                "Starting message analysis",
                extra={
                    "period_hours": period_hours,
                    "chat_id": chat_id
                }
            )
            
            # Check debounce
            if not await self._check_debounce():
                remaining = await self._get_remaining_debounce_time()
                raise ValueError(
                    f"Анализ был выполнен недавно. "
                    f"Пожалуйста, подождите еще {remaining:.0f} секунд."
                )
            
            # Get messages for the period
            start_time = datetime.now() - timedelta(hours=period_hours)
            messages = await self.message_repository.get_by_period(
                start_time=start_time,
                chat_id=chat_id
            )
            
            if not messages:
                logger.warning("No messages found for analysis period")
                return "Нет сообщений для анализа за указанный период.", False
            
            logger.info(
                f"Retrieved {len(messages)} messages for analysis",
                extra={"message_count": len(messages)}
            )
            
            # Generate cache key based on messages
            cache_key = self._generate_cache_key(messages)
            
            # Check cache
            cached_result = await self.cache_manager.get(cache_key)
            if cached_result:
                logger.info("Returning cached analysis result")
                return cached_result, True
            
            # Perform analysis with OpenAI
            logger.info("Performing new analysis with OpenAI")
            analysis_result = await self.openai_client.analyze_messages(messages)
            
            # Cache the result
            await self.cache_manager.set(
                key=cache_key,
                value=analysis_result,
                ttl_minutes=self.cache_ttl_minutes
            )
            
            # Mark operation as executed for debounce
            await self.debounce_manager.mark_executed(self.ANALYSIS_OPERATION)
            
            logger.info(
                "Analysis completed successfully",
                extra={
                    "period_hours": period_hours,
                    "message_count": len(messages),
                    "from_cache": False
                }
            )
            
            return analysis_result, False
            
        except ValueError:
            # Re-raise debounce errors
            raise
        except Exception as e:
            logger.error(
                f"Failed to analyze messages: {e}",
                extra={
                    "period_hours": hours or self.analysis_period_hours,
                    "chat_id": chat_id
                },
                exc_info=True
            )
            raise
    
    async def _analyze_without_debounce(
        self,
        hours: int,
        chat_id: int
    ) -> tuple[str, bool]:
        """
        Perform analysis without debounce check.
        
        This is a helper method used by analyze_messages_with_debounce
        to perform the actual analysis after debounce has been checked.
        
        Args:
            hours: Number of hours to analyze
            chat_id: Chat ID to filter messages by
            
        Returns:
            Tuple of (analysis_result, from_cache)
        """
        try:
            # Get messages for the period
            start_time = datetime.now() - timedelta(hours=hours)
            messages = await self.message_repository.get_by_period(
                start_time=start_time,
                chat_id=chat_id
            )
            
            if not messages:
                logger.warning("No messages found for analysis period")
                return "Нет сообщений для анализа за указанный период.", False
            
            logger.info(
                f"Retrieved {len(messages)} messages for analysis",
                extra={"message_count": len(messages)}
            )
            
            # Generate cache key based on messages
            cache_key = self._generate_cache_key(messages)
            
            # Check cache
            cached_result = await self.cache_manager.get(cache_key)
            if cached_result:
                logger.info("Returning cached analysis result")
                return cached_result, True
            
            # Perform analysis with OpenAI
            logger.info("Performing new analysis with OpenAI")
            analysis_result = await self.openai_client.analyze_messages(messages)
            
            # Cache the result
            await self.cache_manager.set(
                key=cache_key,
                value=analysis_result,
                ttl_minutes=self.cache_ttl_minutes
            )
            
            logger.info(
                "Analysis completed successfully",
                extra={
                    "period_hours": hours,
                    "message_count": len(messages),
                    "from_cache": False
                }
            )
            
            return analysis_result, False
            
        except Exception as e:
            logger.error(
                f"Failed to analyze messages: {e}",
                extra={
                    "period_hours": hours,
                    "chat_id": chat_id
                },
                exc_info=True
            )
            raise
    
    async def _check_debounce(self) -> bool:
        """
        Check if analysis can be executed based on debounce interval.
        
        Returns:
            True if analysis can be executed, False if still in debounce period
        """
        try:
            can_execute, remaining = await self.debounce_manager.can_execute(
                operation=self.ANALYSIS_OPERATION,
                interval_seconds=self.debounce_interval_seconds
            )
            
            if not can_execute:
                logger.warning(
                    f"Analysis blocked by debounce "
                    f"(interval: {self.debounce_interval_seconds}s, remaining: {remaining:.1f}s)"
                )
            
            return can_execute
            
        except Exception as e:
            logger.error(f"Error checking debounce: {e}", exc_info=True)
            # On error, allow execution to avoid blocking legitimate requests
            return True
    
    async def _get_remaining_debounce_time(self) -> float:
        """
        Get remaining time in debounce period.
        
        Returns:
            Remaining seconds in debounce period, or 0 if not in debounce
        """
        try:
            remaining = await self.debounce_manager.get_remaining_time(
                operation=self.ANALYSIS_OPERATION,
                interval_seconds=self.debounce_interval_seconds
            )
            return remaining
            
        except Exception as e:
            logger.error(f"Error getting remaining debounce time: {e}")
            return 0
    
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
