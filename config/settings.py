"""Configuration module for loading and validating environment variables."""

import os
import logging
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration class for bot settings loaded from environment variables."""
    
    # Telegram
    bot_token: str
    admin_id: int
    debug_mode: bool
    
    # OpenAI
    openai_api_key: str
    openai_base_url: Optional[str]
    openai_model: str
    max_tokens: int
    
    # Database
    db_path: str
    storage_period_hours: int
    
    # Analysis
    analysis_period_hours: int
    
    # User Analysis Command
    anal_period_hours: int
    
    # Cache
    cache_ttl_minutes: int
    
    # Debounce
    debounce_interval_seconds: int
    
    # Collection
    collection_enabled: bool
    
    # Buffering
    buffer_size: int
    buffer_flush_interval_seconds: int
    
    # Message Formatting
    default_parse_mode: str
    enable_markdown_escaping: bool
    max_message_length: int
    
    # Timezone
    timezone: Optional[str]
    
    # Inline Mode
    inline_debounce_seconds: int
    inline_max_tokens: int
    
    @classmethod
    def from_env(cls) -> "Config":
        """
        Load configuration from environment variables.
        
        Returns:
            Config: Configuration instance with loaded values
            
        Raises:
            ValueError: If required environment variables are missing or invalid
        """
        # Load .env file if it exists
        load_dotenv()
        
        # Validate and load required parameters
        bot_token = cls._get_required_env("BOT_TOKEN")
        admin_id = cls._get_required_int_env("ADMIN_ID")
        openai_api_key = cls._get_required_env("OPENAI_API_KEY")
        
        # Load optional parameters with defaults
        debug_mode = cls._get_bool_env("DEBUG_MODE", default=False)
        openai_base_url = os.getenv("OPENAI_BASE_URL")  # Optional, defaults to OpenAI's endpoint
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        max_tokens = cls._get_int_env("MAX_TOKENS", default=4000)
        db_path = os.getenv("DB_PATH", "/app/data/bot.db")
        storage_period_hours = cls._get_int_env("STORAGE_PERIOD_HOURS", default=168)  # 7 days
        analysis_period_hours = cls._get_int_env("ANALYSIS_PERIOD_HOURS", default=24)
        anal_period_hours = cls._get_int_env("ANAL_PERIOD_HOURS", default=8)
        cache_ttl_minutes = cls._get_int_env("CACHE_TTL_MINUTES", default=60)
        debounce_interval_seconds = cls._get_int_env("DEBOUNCE_INTERVAL_SECONDS", default=300)  # 5 minutes
        collection_enabled = cls._get_bool_env("COLLECTION_ENABLED", default=True)
        buffer_size = cls._get_int_env("BUFFER_SIZE", default=50)  # Flush after 50 messages
        buffer_flush_interval_seconds = cls._get_int_env("BUFFER_FLUSH_INTERVAL_SECONDS", default=30)  # Flush every 30 seconds
        default_parse_mode = os.getenv("DEFAULT_PARSE_MODE", "Markdown")
        enable_markdown_escaping = cls._get_bool_env("ENABLE_MARKDOWN_ESCAPING", default=True)
        max_message_length = cls._get_int_env("MAX_MESSAGE_LENGTH", default=4096)
        timezone = cls._get_validated_timezone_env("TIMEZONE", default=None)
        inline_debounce_seconds = cls._get_int_env("INLINE_DEBOUNCE_SECONDS", default=3600)  # 1 hour
        inline_max_tokens = cls._get_int_env("INLINE_MAX_TOKENS", default=500)
        
        # Validate positive values
        cls._validate_positive("MAX_TOKENS", max_tokens)
        cls._validate_positive("STORAGE_PERIOD_HOURS", storage_period_hours)
        cls._validate_positive("ANALYSIS_PERIOD_HOURS", analysis_period_hours)
        cls._validate_positive("ANAL_PERIOD_HOURS", anal_period_hours)
        cls._validate_positive("CACHE_TTL_MINUTES", cache_ttl_minutes)
        cls._validate_positive("DEBOUNCE_INTERVAL_SECONDS", debounce_interval_seconds)
        cls._validate_positive("BUFFER_SIZE", buffer_size)
        cls._validate_positive("BUFFER_FLUSH_INTERVAL_SECONDS", buffer_flush_interval_seconds)
        cls._validate_positive("MAX_MESSAGE_LENGTH", max_message_length)
        cls._validate_positive("INLINE_DEBOUNCE_SECONDS", inline_debounce_seconds)
        cls._validate_positive("INLINE_MAX_TOKENS", inline_max_tokens)
        
        # Validate parse mode
        valid_parse_modes = ["Markdown", "HTML", "None", None]
        if default_parse_mode not in valid_parse_modes:
            raise ValueError(f"DEFAULT_PARSE_MODE must be one of {valid_parse_modes}, got: {default_parse_mode}")
        
        return cls(
            bot_token=bot_token,
            admin_id=admin_id,
            debug_mode=debug_mode,
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            openai_model=openai_model,
            max_tokens=max_tokens,
            db_path=db_path,
            storage_period_hours=storage_period_hours,
            analysis_period_hours=analysis_period_hours,
            anal_period_hours=anal_period_hours,
            cache_ttl_minutes=cache_ttl_minutes,
            debounce_interval_seconds=debounce_interval_seconds,
            collection_enabled=collection_enabled,
            buffer_size=buffer_size,
            buffer_flush_interval_seconds=buffer_flush_interval_seconds,
            default_parse_mode=default_parse_mode,
            enable_markdown_escaping=enable_markdown_escaping,
            max_message_length=max_message_length,
            timezone=timezone,
            inline_debounce_seconds=inline_debounce_seconds,
            inline_max_tokens=inline_max_tokens,
        )
    
    @staticmethod
    def _get_required_env(key: str) -> str:
        """
        Get required environment variable.
        
        Args:
            key: Environment variable name
            
        Returns:
            str: Environment variable value
            
        Raises:
            ValueError: If environment variable is not set or empty
        """
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Required environment variable '{key}' is not set")
        return value
    
    @staticmethod
    def _get_required_int_env(key: str) -> int:
        """
        Get required integer environment variable.
        
        Args:
            key: Environment variable name
            
        Returns:
            int: Environment variable value as integer
            
        Raises:
            ValueError: If environment variable is not set, empty, or not a valid integer
        """
        value = Config._get_required_env(key)
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"Environment variable '{key}' must be a valid integer, got: {value}")
    
    @staticmethod
    def _get_int_env(key: str, default: int) -> int:
        """
        Get optional integer environment variable with default.
        
        Args:
            key: Environment variable name
            default: Default value if not set
            
        Returns:
            int: Environment variable value as integer or default
            
        Raises:
            ValueError: If environment variable is set but not a valid integer
        """
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"Environment variable '{key}' must be a valid integer, got: {value}")
    
    @staticmethod
    def _get_bool_env(key: str, default: bool) -> bool:
        """
        Get optional boolean environment variable with default.
        
        Args:
            key: Environment variable name
            default: Default value if not set
            
        Returns:
            bool: Environment variable value as boolean or default
        """
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")
    
    @staticmethod
    def _validate_positive(key: str, value: int) -> None:
        """
        Validate that a value is positive.
        
        Args:
            key: Parameter name for error message
            value: Value to validate
            
        Raises:
            ValueError: If value is not positive
        """
        if value <= 0:
            raise ValueError(f"Parameter '{key}' must be positive, got: {value}")
    
    @staticmethod
    def _get_validated_timezone_env(key: str, default: Optional[str]) -> Optional[str]:
        """
        Get and validate timezone environment variable.
        
        Args:
            key: Environment variable name
            default: Default value if not set
            
        Returns:
            Optional[str]: Valid timezone identifier or None (UTC)
            
        Logs warning if invalid timezone provided.
        """
        value = os.getenv(key)
        if value is None:
            return default
        
        try:
            import pytz
            pytz.timezone(value)  # Validate timezone exists
            return value
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(f"Invalid timezone '{value}', defaulting to UTC")
            return None
