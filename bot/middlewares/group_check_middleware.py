"""Middleware for checking if bot is enabled in a group."""

import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from aiogram.enums import ChatType

from services.admin_service import AdminService


logger = logging.getLogger(__name__)


class GroupCheckMiddleware(BaseMiddleware):
    """Middleware to check if bot is enabled in the current group."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """
        Check if bot is enabled in the group before processing message.
        
        Args:
            handler: Next handler in the chain
            event: Incoming message
            data: Handler data dictionary
            
        Returns:
            Handler result or None if bot is disabled
        """
        # Only check for group messages
        if event.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            return await handler(event, data)
        
        # Get admin service from data
        admin_service: AdminService = data.get('admin_service')
        
        if not admin_service:
            logger.warning("AdminService not found in middleware data")
            return await handler(event, data)
        
        # Check if group is enabled
        is_enabled = await admin_service.is_group_enabled(event.chat.id)
        
        if not is_enabled:
            # Bot is disabled for this group
            # Only respond to commands and mentions
            is_command = event.text and event.text.startswith('/')
            is_mention = False
            
            # Check for bot mention in entities
            if event.text and event.entities:
                for entity in event.entities:
                    if entity.type == "mention":
                        # Extract mentioned username
                        mentioned = event.text[entity.offset:entity.offset + entity.length]
                        # Check if it's a mention (will be validated by handler if it's for this bot)
                        is_mention = True
                        break
            
            if is_command or is_mention:
                logger.info(
                    f"Bot is disabled for group {event.chat.id}, responding to command/mention"
                )
                
                try:
                    await event.answer("Я отключен разработчиком в этой конфе.")
                except Exception as e:
                    logger.error(f"Failed to send disabled notification: {e}")
            else:
                logger.debug(
                    f"Bot is disabled for group {event.chat.id}, ignoring regular message"
                )
            
            # Don't process the message further
            return None
        
        # Group is enabled, continue processing
        return await handler(event, data)
