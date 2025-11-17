"""Middleware for controlling message collection."""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message
from config.settings import Config


class CollectionMiddleware(BaseMiddleware):
    """Middleware to check if message collection is enabled before processing."""
    
    def __init__(self, config: Config):
        """
        Initialize the collection middleware.
        
        Args:
            config: Bot configuration containing collection_enabled flag
        """
        super().__init__()
        self.config = config
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """
        Check if collection is enabled before processing the message.
        
        Args:
            handler: Next handler in the chain
            event: Incoming message event
            data: Additional data dictionary
            
        Returns:
            Handler result if collection is enabled, None otherwise
        """
        # If collection is disabled, skip message processing
        if not self.config.collection_enabled:
            return None
        
        # Collection is enabled, proceed with handler
        return await handler(event, data)
