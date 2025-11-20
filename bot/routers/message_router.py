"""Router for handling group chat messages."""

import logging
from datetime import datetime

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import ChatMemberUpdatedFilter
from aiogram.enums import ChatType

from services.message_service import MessageService


logger = logging.getLogger(__name__)

# Create router for message handling
router = Router(name="message_router")


@router.message(
    lambda message: message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP],
    lambda message: not message.text or not message.text.startswith('/')
)
async def handle_group_message(message: Message, message_service: MessageService):
    """
    Handle incoming messages from group chats.
    
    This handler:
    1. Filters messages from group and supergroup chats
    2. Extracts message data
    3. Saves message to database via MessageService
    4. Triggers cleanup of old messages
    
    Args:
        message: Incoming message from Telegram
        message_service: Service for message operations
    """
    try:
        # Skip messages without text
        if not message.text:
            logger.debug(
                "Skipping message without text",
                extra={
                    "message_id": message.message_id,
                    "chat_id": message.chat.id
                }
            )
            return
        
        # Extract user information
        user_id = message.from_user.id if message.from_user else 0
        username = message.from_user.username or message.from_user.first_name or "Unknown"
        
        # Extract reply information
        reply_to_message_id = None
        if message.reply_to_message:
            reply_to_message_id = message.reply_to_message.message_id
        
        # Convert timestamp
        timestamp = datetime.fromtimestamp(message.date.timestamp())
        
        logger.debug(
            "Processing group message",
            extra={
                "message_id": message.message_id,
                "chat_id": message.chat.id,
                "user_id": user_id,
                "username": username,
                "text_length": len(message.text)
            }
        )
        
        # Save message to database
        await message_service.save_message(
            message_id=message.message_id,
            chat_id=message.chat.id,
            user_id=user_id,
            username=username,
            text=message.text,
            timestamp=timestamp,
            reactions={},  # Reactions will be updated separately
            reply_to_message_id=reply_to_message_id
        )
        
        # Trigger cleanup of old messages (with debounce protection)
        await message_service.cleanup_old_messages()
        
    except Exception as e:
        logger.error(
            f"Error handling group message: {e}",
            extra={
                "message_id": message.message_id if message else None,
                "chat_id": message.chat.id if message and message.chat else None
            },
            exc_info=True
        )
        # Don't re-raise - we don't want to stop the bot on message handling errors
