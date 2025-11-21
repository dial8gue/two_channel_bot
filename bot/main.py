"""
Main entry point for the Telegram analytics bot.

This module initializes all components and starts the bot.
"""
import asyncio
import logging
import sys
from signal import SIGINT, SIGTERM

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config.settings import Config
from database.connection import DatabaseConnection
from database.repository import (
    MessageRepository,
    ConfigRepository,
    CacheRepository,
    DebounceRepository
)
from services.message_service import MessageService
from services.analysis_service import AnalysisService
from services.admin_service import AdminService
from openai_client.client import OpenAIClient
from utils.cache_manager import CacheManager
from utils.debounce_manager import DebounceManager
from bot.routers.message_router import router as message_router
from bot.routers.reaction_router import router as reaction_router
from bot.routers.admin_router import create_admin_router
from bot.routers.user_router import create_user_router
from bot.middlewares.collection_middleware import CollectionMiddleware


# Configure logging
def setup_logging(debug_mode: bool = False) -> None:
    """
    Configure logging for the application.
    
    Args:
        debug_mode: If True, set logging level to DEBUG, otherwise INFO
    """
    log_level = logging.DEBUG if debug_mode else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific log levels for noisy libraries
    logging.getLogger('aiogram').setLevel(logging.INFO)
    logging.getLogger('aiosqlite').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.INFO)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level: {logging.getLevelName(log_level)}")


async def main() -> None:
    """
    Main function to initialize and run the bot.
    
    This function:
    1. Loads configuration from environment variables
    2. Initializes database connection and creates tables
    3. Creates all service instances
    4. Registers routers and middleware
    5. Starts bot polling
    6. Handles graceful shutdown
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration from environment
        logger.info("Loading configuration from environment variables...")
        config = Config.from_env()
        
        # Setup logging based on debug mode
        setup_logging(config.debug_mode)
        
        logger.info("Configuration loaded successfully")
        logger.info(f"Debug mode: {config.debug_mode}")
        logger.info(f"Admin ID: {config.admin_id}")
        logger.info(f"Database path: {config.db_path}")
        
        # Initialize database connection
        logger.info("Initializing database connection...")
        db_connection = DatabaseConnection(config.db_path)
        await db_connection.init_db()
        logger.info("Database initialized successfully")
        
        # Create repository instances
        logger.info("Creating repository instances...")
        message_repository = MessageRepository(db_connection)
        config_repository = ConfigRepository(db_connection)
        cache_repository = CacheRepository(db_connection)
        debounce_repository = DebounceRepository(db_connection)
        
        # Create utility instances
        logger.info("Creating utility instances...")
        cache_manager = CacheManager(cache_repository)
        debounce_manager = DebounceManager(debounce_repository)
        
        # Create OpenAI client
        logger.info("Initializing OpenAI client...")
        openai_client = OpenAIClient(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            model=config.openai_model,
            max_tokens=config.max_tokens,
            timezone=config.timezone
        )
        
        # Create service instances
        logger.info("Creating service instances...")
        message_service = MessageService(
            message_repository=message_repository,
            debounce_repository=debounce_repository,
            storage_period_hours=config.storage_period_hours
        )
        
        analysis_service = AnalysisService(
            message_repository=message_repository,
            openai_client=openai_client,
            cache_manager=cache_manager,
            debounce_manager=debounce_manager,
            debounce_interval_seconds=config.debounce_interval_seconds,
            cache_ttl_minutes=config.cache_ttl_minutes,
            analysis_period_hours=config.analysis_period_hours
        )
        
        admin_service = AdminService(
            message_repository=message_repository,
            config_repository=config_repository,
            cache_repository=cache_repository,
            timezone=config.timezone
        )
        
        # Initialize bot and dispatcher
        logger.info("Initializing bot and dispatcher...")
        bot = Bot(
            token=config.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
        )
        
        dp = Dispatcher()
        
        # Register middleware
        logger.info("Registering middleware...")
        collection_middleware = CollectionMiddleware(config)
        message_router.message.middleware(collection_middleware)
        
        # Register routers
        logger.info("Registering routers...")
        dp.include_router(message_router)
        dp.include_router(reaction_router)
        
        # Create and register admin router
        admin_router = create_admin_router(config)
        dp.include_router(admin_router)
        
        # Create and register user router
        user_router = create_user_router(config)
        dp.include_router(user_router)
        
        # Inject dependencies into handlers
        dp['message_service'] = message_service
        dp['analysis_service'] = analysis_service
        dp['admin_service'] = admin_service
        dp['config'] = config
        
        logger.info("Bot initialization complete")
        logger.info("=" * 50)
        logger.info("Starting bot polling...")
        logger.info("=" * 50)
        
        # Start polling
        try:
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types()
            )
        finally:
            # Graceful shutdown
            logger.info("Shutting down bot...")
            await bot.session.close()
            await db_connection.close()
            logger.info("Bot shutdown complete")
            
    except ValueError as e:
        # Configuration error
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
        
    except Exception as e:
        # Unexpected error
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    """Entry point when running the module directly."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
