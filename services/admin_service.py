"""
Admin service for administrative operations.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from database.repository import MessageRepository, ConfigRepository, CacheRepository, GroupRepository


logger = logging.getLogger(__name__)


class AdminService:
    """Service for administrative operations and configuration management."""
    
    # Configuration keys
    CONFIG_STORAGE_PERIOD = "storage_period_hours"
    CONFIG_ANALYSIS_PERIOD = "analysis_period_hours"
    CONFIG_COLLECTION_ENABLED = "collection_enabled"
    CONFIG_OPENAI_MODEL = "openai_model"
    CONFIG_CLASSIFIER_MODEL = "classifier_model"
    CONFIG_VISION_MODEL = "vision_model"
    CONFIG_VISION_ENABLED = "vision_enabled"
    CONFIG_OPENAI_API_KEY = "openai_api_key"
    CONFIG_OPENAI_BASE_URL = "openai_base_url"
    CONFIG_MAX_TOKENS = "max_tokens"
    CONFIG_INLINE_MAX_TOKENS = "inline_max_tokens"
    CONFIG_VISION_MAX_TOKENS = "vision_max_tokens"
    CONFIG_INLINE_DEBOUNCE_SECONDS = "inline_debounce_seconds"
    CONFIG_GUEST_MODE_ENABLED = "guest_mode_enabled"
    CONFIG_GUEST_DEBOUNCE_SECONDS = "guest_debounce_seconds"
    CONFIG_WEB_SEARCH_ENABLED = "web_search_enabled"
    CONFIG_WEB_SEARCH_ENGINE = "web_search_engine"
    CONFIG_WEB_SEARCH_MAX_RESULTS = "web_search_max_results"
    CONFIG_WEB_SEARCH_MAX_TOTAL_RESULTS = "web_search_max_total_results"
    CONFIG_WEB_SEARCH_CONTEXT_SIZE = "web_search_context_size"
    
    def __init__(
        self,
        message_repository: MessageRepository,
        config_repository: ConfigRepository,
        cache_repository: CacheRepository,
        group_repository: GroupRepository,
        timezone: Optional[str] = None
    ):
        """
        Initialize admin service.
        
        Args:
            message_repository: Repository for message operations
            config_repository: Repository for configuration operations
            cache_repository: Repository for cache operations
            group_repository: Repository for group operations
            timezone: IANA timezone identifier for timestamp formatting (optional)
        """
        self.message_repository = message_repository
        self.config_repository = config_repository
        self.cache_repository = cache_repository
        self.group_repository = group_repository
        self.timezone = timezone
    
    async def clear_database(self) -> None:
        """
        Clear all messages from the database.
        
        This operation also clears the cache to ensure consistency.
        """
        try:
            logger.info("Starting database clear operation")
            
            # Clear all messages
            await self.message_repository.clear_all()
            
            # Clear cache as well
            await self.cache_repository.clear_all()
            
            logger.info("Database cleared successfully")
            
        except Exception as e:
            logger.error(f"Failed to clear database: {e}", exc_info=True)
            raise
    
    async def set_storage_period(self, hours: int) -> None:
        """
        Set the storage period for messages.
        
        Args:
            hours: Number of hours to store messages
            
        Raises:
            ValueError: If hours is not positive
        """
        try:
            if hours <= 0:
                raise ValueError("Storage period must be positive")
            
            await self.config_repository.set(
                key=self.CONFIG_STORAGE_PERIOD,
                value=str(hours)
            )
            
            logger.info(
                "Storage period updated",
                extra={"storage_period_hours": hours}
            )
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to set storage period: {e}",
                extra={"hours": hours},
                exc_info=True
            )
            raise
    
    async def get_storage_period(self) -> Optional[int]:
        """
        Get the current storage period setting.
        
        Returns:
            Storage period in hours, or None if not set
        """
        try:
            value = await self.config_repository.get(self.CONFIG_STORAGE_PERIOD)
            if value:
                return int(value)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get storage period: {e}", exc_info=True)
            return None
    
    async def set_analysis_period(self, hours: int) -> None:
        """
        Set the default analysis period.
        
        Args:
            hours: Number of hours for analysis period
            
        Raises:
            ValueError: If hours is not positive
        """
        try:
            if hours <= 0:
                raise ValueError("Analysis period must be positive")
            
            await self.config_repository.set(
                key=self.CONFIG_ANALYSIS_PERIOD,
                value=str(hours)
            )
            
            logger.info(
                "Analysis period updated",
                extra={"analysis_period_hours": hours}
            )
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to set analysis period: {e}",
                extra={"hours": hours},
                exc_info=True
            )
            raise
    
    async def get_analysis_period(self) -> Optional[int]:
        """
        Get the current analysis period setting.
        
        Returns:
            Analysis period in hours, or None if not set
        """
        try:
            value = await self.config_repository.get(self.CONFIG_ANALYSIS_PERIOD)
            if value:
                return int(value)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get analysis period: {e}", exc_info=True)
            return None
    
    async def toggle_collection(self, enabled: bool) -> None:
        """
        Enable or disable message collection.
        
        Args:
            enabled: True to enable collection, False to disable
        """
        try:
            await self.config_repository.set(
                key=self.CONFIG_COLLECTION_ENABLED,
                value="true" if enabled else "false"
            )
            
            status = "enabled" if enabled else "disabled"
            logger.info(
                f"Message collection {status}",
                extra={"collection_enabled": enabled}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to toggle collection: {e}",
                extra={"enabled": enabled},
                exc_info=True
            )
            raise
    
    async def is_collection_enabled(self) -> bool:
        """
        Check if message collection is enabled.
        
        Returns:
            True if collection is enabled, False otherwise (defaults to True)
        """
        try:
            value = await self.config_repository.get(self.CONFIG_COLLECTION_ENABLED)
            if value is None:
                # Default to enabled if not set
                return True
            return value.lower() == "true"
            
        except Exception as e:
            logger.error(f"Failed to check collection status: {e}", exc_info=True)
            # Default to enabled on error
            return True
    
    async def set_openai_model(self, model: str) -> None:
        """
        Set the OpenAI model to use for analysis.
        
        Args:
            model: Model name (e.g., 'gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo')
            
        Raises:
            ValueError: If model name is empty
        """
        try:
            if not model or not model.strip():
                raise ValueError("Model name cannot be empty")
            
            model = model.strip()
            
            await self.config_repository.set(
                key=self.CONFIG_OPENAI_MODEL,
                value=model
            )
            
            logger.info(
                "OpenAI model updated",
                extra={"openai_model": model}
            )
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to set OpenAI model: {e}",
                extra={"model": model},
                exc_info=True
            )
            raise
    
    async def get_openai_model(self) -> Optional[str]:
        """
        Get the current OpenAI model setting.
        
        Returns:
            Model name, or None if not set (uses default from config)
        """
        try:
            value = await self.config_repository.get(self.CONFIG_OPENAI_MODEL)
            return value if value else None
            
        except Exception as e:
            logger.error(f"Failed to get OpenAI model: {e}", exc_info=True)
            return None
    
    async def set_classifier_model(self, model: str) -> None:
        """
        Set the model used for question classification (CHAT vs GENERAL).
        
        Args:
            model: Model name (e.g., 'google/gemini-2.5-flash-lite')
            
        Raises:
            ValueError: If model name is empty
        """
        try:
            if not model or not model.strip():
                raise ValueError("Model name cannot be empty")
            
            model = model.strip()
            
            await self.config_repository.set(
                key=self.CONFIG_CLASSIFIER_MODEL,
                value=model
            )
            
            logger.info(
                "Classifier model updated",
                extra={"classifier_model": model}
            )
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to set classifier model: {e}",
                extra={"model": model},
                exc_info=True
            )
            raise
    
    async def get_classifier_model(self) -> Optional[str]:
        """
        Get the current classifier model setting.
        
        Returns:
            Model name, or None if not set (uses default from env)
        """
        try:
            value = await self.config_repository.get(self.CONFIG_CLASSIFIER_MODEL)
            return value if value else None
            
        except Exception as e:
            logger.error(f"Failed to get classifier model: {e}", exc_info=True)
            return None
    
    async def set_vision_model(self, model: str) -> None:
        """
        Set the model used for image recognition (vision).
        
        Args:
            model: Model name (e.g., 'google/gemini-2.5-flash')
            
        Raises:
            ValueError: If model name is empty
        """
        try:
            if not model or not model.strip():
                raise ValueError("Model name cannot be empty")
            
            model = model.strip()
            
            await self.config_repository.set(
                key=self.CONFIG_VISION_MODEL,
                value=model
            )
            
            logger.info(
                "Vision model updated",
                extra={"vision_model": model}
            )
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to set vision model: {e}",
                extra={"model": model},
                exc_info=True
            )
            raise
    
    async def get_vision_model(self) -> Optional[str]:
        """
        Get the current vision model setting.
        
        Returns:
            Model name, or None if not set (uses default from env)
        """
        try:
            value = await self.config_repository.get(self.CONFIG_VISION_MODEL)
            return value if value else None
            
        except Exception as e:
            logger.error(f"Failed to get vision model: {e}", exc_info=True)
            return None
    
    async def set_openai_api_key(self, api_key: str) -> None:
        """
        Persist a new OpenAI API key in the config store.
        
        Args:
            api_key: New API key
        
        Raises:
            ValueError: If api_key is empty
        """
        try:
            if not api_key or not api_key.strip():
                raise ValueError("API key cannot be empty")
            
            api_key = api_key.strip()
            await self.config_repository.set(
                key=self.CONFIG_OPENAI_API_KEY,
                value=api_key,
            )
            # Avoid logging the key itself
            logger.info(
                "OpenAI API key updated",
                extra={"api_key_len": len(api_key)},
            )
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to set OpenAI API key: {e}", exc_info=True)
            raise
    
    async def get_openai_api_key(self) -> Optional[str]:
        """Return persisted API key override, or None if not set."""
        try:
            value = await self.config_repository.get(self.CONFIG_OPENAI_API_KEY)
            return value if value else None
        except Exception as e:
            logger.error(f"Failed to get OpenAI API key: {e}", exc_info=True)
            return None
    
    async def set_openai_base_url(self, base_url: Optional[str]) -> None:
        """
        Persist a new OpenAI base URL. Empty/None value clears the override
        (client will use OpenAI's default endpoint).
        
        Args:
            base_url: New base URL (e.g. 'https://openrouter.ai/api/v1')
                     or empty string to reset to default.
        """
        try:
            value = base_url.strip() if base_url else ""
            await self.config_repository.set(
                key=self.CONFIG_OPENAI_BASE_URL,
                value=value,
            )
            logger.info(
                "OpenAI base URL updated",
                extra={"base_url": value or "default"},
            )
        except Exception as e:
            logger.error(f"Failed to set OpenAI base URL: {e}", exc_info=True)
            raise
    
    async def get_openai_base_url(self) -> Optional[str]:
        """Return persisted base URL override (or None if not set / reset)."""
        try:
            value = await self.config_repository.get(self.CONFIG_OPENAI_BASE_URL)
            if value is None or value == "":
                return None
            return value
        except Exception as e:
            logger.error(f"Failed to get OpenAI base URL: {e}", exc_info=True)
            return None
    
    async def _set_positive_int(self, key: str, value: int, label: str) -> None:
        """Helper: validate value is positive int and persist to config."""
        try:
            if value <= 0:
                raise ValueError(f"{label} must be positive")
            await self.config_repository.set(key=key, value=str(int(value)))
            logger.info(f"{label} updated", extra={key: value})
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to set {label}: {e}", extra={"value": value}, exc_info=True)
            raise
    
    async def _get_optional_int(self, key: str) -> Optional[int]:
        """Helper: read int value from config, None if unset or invalid."""
        try:
            value = await self.config_repository.get(key)
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            logger.warning(f"Invalid integer stored for config key '{key}'")
            return None
        except Exception as e:
            logger.error(f"Failed to get config '{key}': {e}", exc_info=True)
            return None
    
    async def set_max_tokens(self, value: int) -> None:
        """Set MAX_TOKENS for analysis requests."""
        await self._set_positive_int(self.CONFIG_MAX_TOKENS, value, "max_tokens")
    
    async def get_max_tokens(self) -> Optional[int]:
        """Return persisted MAX_TOKENS override, or None if not set."""
        return await self._get_optional_int(self.CONFIG_MAX_TOKENS)
    
    async def set_inline_max_tokens(self, value: int) -> None:
        """Set INLINE_MAX_TOKENS for /ask answers."""
        await self._set_positive_int(self.CONFIG_INLINE_MAX_TOKENS, value, "inline_max_tokens")
    
    async def get_inline_max_tokens(self) -> Optional[int]:
        """Return persisted INLINE_MAX_TOKENS override, or None if not set."""
        return await self._get_optional_int(self.CONFIG_INLINE_MAX_TOKENS)
    
    async def set_vision_max_tokens(self, value: int) -> None:
        """Set VISION_MAX_TOKENS for image descriptions."""
        await self._set_positive_int(self.CONFIG_VISION_MAX_TOKENS, value, "vision_max_tokens")
    
    async def get_vision_max_tokens(self) -> Optional[int]:
        """Return persisted VISION_MAX_TOKENS override, or None if not set."""
        return await self._get_optional_int(self.CONFIG_VISION_MAX_TOKENS)
    
    async def set_inline_debounce_seconds(self, value: int) -> None:
        """Set INLINE_DEBOUNCE_SECONDS for /ask anti-spam."""
        await self._set_positive_int(
            self.CONFIG_INLINE_DEBOUNCE_SECONDS, value, "inline_debounce_seconds"
        )
    
    async def get_inline_debounce_seconds(self) -> Optional[int]:
        """Return persisted INLINE_DEBOUNCE_SECONDS override, or None if not set."""
        return await self._get_optional_int(self.CONFIG_INLINE_DEBOUNCE_SECONDS)
    
    async def toggle_guest_mode(self, enabled: bool) -> None:
        """
        Enable or disable Guest Mode handler in the bot.
        
        Note: Guest Mode must also be enabled in @BotFather MiniApp for the
        bot to receive `guest_message` updates at all. This flag only controls
        whether our handler answers them.
        
        Args:
            enabled: True to enable, False to disable
        """
        try:
            await self.config_repository.set(
                key=self.CONFIG_GUEST_MODE_ENABLED,
                value="true" if enabled else "false",
            )
            status = "enabled" if enabled else "disabled"
            logger.info(
                f"Guest mode {status}",
                extra={"guest_mode_enabled": enabled},
            )
        except Exception as e:
            logger.error(
                f"Failed to toggle guest mode: {e}",
                extra={"enabled": enabled},
                exc_info=True,
            )
            raise
    
    async def is_guest_mode_enabled(self) -> Optional[bool]:
        """
        Return persisted guest_mode_enabled override, or None if not set.
        
        Returns None when no explicit value is stored, so callers can fall back
        to the env default from Config.
        """
        try:
            value = await self.config_repository.get(self.CONFIG_GUEST_MODE_ENABLED)
            if value is None:
                return None
            return value.lower() == "true"
        except Exception as e:
            logger.error(f"Failed to read guest_mode_enabled: {e}", exc_info=True)
            return None
    
    async def set_guest_debounce_seconds(self, value: int) -> None:
        """Set per-user debounce interval for guest_message answers."""
        await self._set_positive_int(
            self.CONFIG_GUEST_DEBOUNCE_SECONDS, value, "guest_debounce_seconds"
        )
    
    async def get_guest_debounce_seconds(self) -> Optional[int]:
        """Return persisted guest_debounce_seconds override, or None if not set."""
        return await self._get_optional_int(self.CONFIG_GUEST_DEBOUNCE_SECONDS)
    
    async def toggle_vision(self, enabled: bool) -> None:
        """
        Enable or disable image recognition (vision).
        
        Args:
            enabled: True to enable vision, False to disable
        """
        try:
            await self.config_repository.set(
                key=self.CONFIG_VISION_ENABLED,
                value="true" if enabled else "false"
            )
            
            status = "enabled" if enabled else "disabled"
            logger.info(
                f"Vision {status}",
                extra={"vision_enabled": enabled}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to toggle vision: {e}",
                extra={"enabled": enabled},
                exc_info=True
            )
            raise
    
    async def is_vision_enabled(self) -> bool:
        """
        Check if image recognition (vision) is enabled.
        
        Returns:
            True if vision is enabled, False otherwise (defaults to True)
        """
        try:
            value = await self.config_repository.get(self.CONFIG_VISION_ENABLED)
            if value is None:
                return True
            return value.lower() == "true"
            
        except Exception as e:
            logger.error(f"Failed to check vision status: {e}", exc_info=True)
            return True

    # ------------------------------------------------------------------ #
    # Web Search (OpenRouter server tool)                                #
    # ------------------------------------------------------------------ #

    async def toggle_web_search(self, enabled: bool) -> None:
        """Enable or disable OpenRouter web search server tool."""
        try:
            await self.config_repository.set(
                key=self.CONFIG_WEB_SEARCH_ENABLED,
                value="true" if enabled else "false",
            )
            status = "enabled" if enabled else "disabled"
            logger.info(
                f"Web search {status}",
                extra={"web_search_enabled": enabled},
            )
        except Exception as e:
            logger.error(
                f"Failed to toggle web search: {e}",
                extra={"enabled": enabled},
                exc_info=True,
            )
            raise

    async def is_web_search_enabled(self) -> Optional[bool]:
        """
        Return persisted web_search_enabled override, or None if not set.
        
        None means "use env default" — callers should fall back to Config.
        """
        try:
            value = await self.config_repository.get(self.CONFIG_WEB_SEARCH_ENABLED)
            if value is None:
                return None
            return value.lower() == "true"
        except Exception as e:
            logger.error(f"Failed to read web_search_enabled: {e}", exc_info=True)
            return None

    async def set_web_search_engine(self, engine: str) -> None:
        """Set web search engine. Validation is delegated to OpenAIClient."""
        try:
            if not engine or not engine.strip():
                raise ValueError("engine cannot be empty")
            engine = engine.strip().lower()
            await self.config_repository.set(
                key=self.CONFIG_WEB_SEARCH_ENGINE,
                value=engine,
            )
            logger.info(
                "Web search engine updated",
                extra={"web_search_engine": engine},
            )
        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to set web search engine: {e}",
                extra={"engine": engine},
                exc_info=True,
            )
            raise

    async def get_web_search_engine(self) -> Optional[str]:
        """Return persisted web_search_engine override, or None if not set."""
        try:
            value = await self.config_repository.get(self.CONFIG_WEB_SEARCH_ENGINE)
            return value if value else None
        except Exception as e:
            logger.error(f"Failed to get web search engine: {e}", exc_info=True)
            return None

    async def set_web_search_max_results(self, value: int) -> None:
        """Persist max results per single search call."""
        await self._set_positive_int(
            self.CONFIG_WEB_SEARCH_MAX_RESULTS, value, "web_search_max_results"
        )

    async def get_web_search_max_results(self) -> Optional[int]:
        """Return persisted web_search_max_results override, or None if not set."""
        return await self._get_optional_int(self.CONFIG_WEB_SEARCH_MAX_RESULTS)

    async def set_web_search_max_total_results(self, value: int) -> None:
        """Persist max total results across all search calls in a single request."""
        await self._set_positive_int(
            self.CONFIG_WEB_SEARCH_MAX_TOTAL_RESULTS,
            value,
            "web_search_max_total_results",
        )

    async def get_web_search_max_total_results(self) -> Optional[int]:
        """Return persisted web_search_max_total_results override, or None."""
        return await self._get_optional_int(self.CONFIG_WEB_SEARCH_MAX_TOTAL_RESULTS)

    async def set_web_search_context_size(self, value: str) -> None:
        """Persist search_context_size. Validation is delegated to OpenAIClient."""
        try:
            if not value or not value.strip():
                raise ValueError("context_size cannot be empty")
            value = value.strip().lower()
            await self.config_repository.set(
                key=self.CONFIG_WEB_SEARCH_CONTEXT_SIZE,
                value=value,
            )
            logger.info(
                "Web search context size updated",
                extra={"web_search_context_size": value},
            )
        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to set web search context size: {e}",
                extra={"value": value},
                exc_info=True,
            )
            raise

    async def get_web_search_context_size(self) -> Optional[str]:
        """Return persisted web_search_context_size override, or None."""
        try:
            value = await self.config_repository.get(
                self.CONFIG_WEB_SEARCH_CONTEXT_SIZE
            )
            return value if value else None
        except Exception as e:
            logger.error(
                f"Failed to get web search context size: {e}", exc_info=True
            )
            return None
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary containing various statistics:
                - total_messages: Total number of messages
                - oldest_message: Timestamp of oldest message
                - newest_message: Timestamp of newest message
                - cache_entries: Number of cache entries
                - storage_period_hours: Current storage period setting
                - analysis_period_hours: Current analysis period setting
                - collection_enabled: Whether collection is enabled
        """
        try:
            logger.info("Gathering database statistics")
            
            stats = {}
            
            # Get message count
            stats['total_messages'] = await self.message_repository.count()
            
            # Get oldest and newest message timestamps
            if stats['total_messages'] > 0:
                # Get all messages to find oldest and newest
                # This is not optimal for large datasets, but works for now
                from datetime import timedelta
                from utils.timezone_helper import format_datetime
                
                all_messages = await self.message_repository.get_by_period(
                    start_time=datetime.now() - timedelta(days=365 * 10)  # 10 years back
                )
                
                if all_messages:
                    timestamps = [msg.timestamp for msg in all_messages]
                    oldest = min(timestamps)
                    newest = max(timestamps)
                    
                    # Format with timezone
                    stats['oldest_message'] = format_datetime(oldest, self.timezone)
                    stats['newest_message'] = format_datetime(newest, self.timezone)
                else:
                    stats['oldest_message'] = None
                    stats['newest_message'] = None
            else:
                stats['oldest_message'] = None
                stats['newest_message'] = None
            
            # Get cache entry count (non-expired entries)
            try:
                cache_count = await self.cache_repository.count()
                stats['cache_entries'] = cache_count
            except Exception as e:
                logger.error(f"Failed to count cache entries: {e}", exc_info=True)
                stats['cache_entries'] = "Error"
            
            # Get configuration settings
            storage_period = await self.get_storage_period()
            stats['storage_period_hours'] = storage_period if storage_period else "Not set"
            
            analysis_period = await self.get_analysis_period()
            stats['analysis_period_hours'] = analysis_period if analysis_period else "Not set"
            
            stats['collection_enabled'] = await self.is_collection_enabled()
            
            # Get OpenAI model setting
            openai_model = await self.get_openai_model()
            stats['openai_model'] = openai_model if openai_model else "Default (from env)"
            
            # Get classifier model setting
            classifier_model = await self.get_classifier_model()
            stats['classifier_model'] = classifier_model if classifier_model else "Default (from env)"
            
            # Get vision model setting
            vision_model = await self.get_vision_model()
            stats['vision_model'] = vision_model if vision_model else "Default (from env)"
            
            # Get OpenAI base URL override
            base_url = await self.get_openai_base_url()
            stats['openai_base_url'] = base_url if base_url else "Default (from env)"
            
            # Get masked API key status (never store/log the full key)
            api_key = await self.get_openai_api_key()
            if api_key:
                from openai_client.client import OpenAIClient
                stats['openai_api_key'] = OpenAIClient.mask_api_key(api_key)
            else:
                stats['openai_api_key'] = "Default (from env)"
            
            # Get vision setting
            stats['vision_enabled'] = await self.is_vision_enabled()
            
            # Token limits and inline debounce
            max_tokens = await self.get_max_tokens()
            stats['max_tokens'] = max_tokens if max_tokens is not None else "Default (from env)"
            inline_max_tokens = await self.get_inline_max_tokens()
            stats['inline_max_tokens'] = inline_max_tokens if inline_max_tokens is not None else "Default (from env)"
            vision_max_tokens = await self.get_vision_max_tokens()
            stats['vision_max_tokens'] = vision_max_tokens if vision_max_tokens is not None else "Default (from env)"
            inline_debounce = await self.get_inline_debounce_seconds()
            stats['inline_debounce_seconds'] = inline_debounce if inline_debounce is not None else "Default (from env)"
            
            # Guest Mode settings
            stats['guest_mode_enabled'] = await self.is_guest_mode_enabled()
            guest_debounce = await self.get_guest_debounce_seconds()
            stats['guest_debounce_seconds'] = guest_debounce if guest_debounce is not None else "Default (from env)"
            
            # Web Search settings (OpenRouter server tool)
            stats['web_search_enabled'] = await self.is_web_search_enabled()
            web_engine = await self.get_web_search_engine()
            stats['web_search_engine'] = web_engine if web_engine else "Default (from env)"
            web_max = await self.get_web_search_max_results()
            stats['web_search_max_results'] = web_max if web_max is not None else "Default (from env)"
            web_total = await self.get_web_search_max_total_results()
            stats['web_search_max_total_results'] = web_total if web_total is not None else "Default (from env)"
            web_ctx = await self.get_web_search_context_size()
            stats['web_search_context_size'] = web_ctx if web_ctx else "Default (from env)"
            
            logger.info(
                "Statistics gathered successfully",
                extra={"total_messages": stats['total_messages']}
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}", exc_info=True)
            raise

    
    async def get_all_groups(self) -> list:
        """
        Get all groups from database.
        
        Returns:
            List of group models
        """
        try:
            groups = await self.group_repository.get_all()
            logger.info(f"Retrieved {len(groups)} groups")
            return groups
            
        except Exception as e:
            logger.error(f"Failed to get all groups: {e}", exc_info=True)
            raise
    
    async def add_or_update_group(self, chat_id: int, title: str) -> None:
        """
        Add or update group information.
        
        Args:
            chat_id: Telegram chat ID
            title: Group title
        """
        try:
            from database.models import GroupModel
            
            group = GroupModel(
                chat_id=chat_id,
                title=title,
                is_enabled=True,
                added_at=datetime.now()
            )
            
            await self.group_repository.add_or_update(group)
            logger.info(f"Group {chat_id} ({title}) added/updated")
            
        except Exception as e:
            logger.error(f"Failed to add/update group: {e}", exc_info=True)
            raise
    
    async def toggle_group(self, chat_id: int, enabled: bool) -> None:
        """
        Enable or disable a group.
        
        Args:
            chat_id: Telegram chat ID
            enabled: True to enable, False to disable
        """
        try:
            await self.group_repository.set_enabled(chat_id, enabled)
            status = "enabled" if enabled else "disabled"
            logger.info(f"Group {chat_id} {status}")
            
        except Exception as e:
            logger.error(f"Failed to toggle group: {e}", exc_info=True)
            raise
    
    async def is_group_enabled(self, chat_id: int) -> bool:
        """
        Check if group is enabled.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            True if enabled, False if disabled
        """
        try:
            return await self.group_repository.is_enabled(chat_id)
            
        except Exception as e:
            logger.error(f"Failed to check if group is enabled: {e}", exc_info=True)
            return True
    
    async def remove_group(self, chat_id: int) -> None:
        """
        Remove group from database and clear its messages.
        
        Args:
            chat_id: Telegram chat ID
        """
        try:
            # Clear messages for this group
            deleted_count = await self.message_repository.delete_by_chat_id(chat_id)
            logger.info(f"Deleted {deleted_count} messages for group {chat_id}")
            
            # Remove group record
            await self.group_repository.delete(chat_id)
            logger.info(f"Group {chat_id} removed from database")
            
        except Exception as e:
            logger.error(f"Failed to remove group: {e}", exc_info=True)
            raise
