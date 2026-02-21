"""Router for handling group chat messages."""

import logging
from datetime import datetime

from aiogram import Router
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION, LEAVE_TRANSITION
from aiogram.enums import ChatType
from aiogram.dispatcher.event.bases import SkipHandler

from services.message_service import MessageService
from services.admin_service import AdminService


logger = logging.getLogger(__name__)

# Create router for message handling
router = Router(name="message_router")


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def on_bot_added_to_group(event: ChatMemberUpdated, admin_service: AdminService):
    """
    Handle bot being added to a group.
    
    Registers the group in the database.
    
    Args:
        event: Chat member update event
        admin_service: Service for admin operations
    """
    try:
        chat = event.chat
        
        # Only handle group chats
        if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            return
        
        logger.info(
            f"Bot added to group: {chat.title} (ID: {chat.id})",
            extra={"chat_id": chat.id, "chat_title": chat.title}
        )
        
        # Register group in database
        await admin_service.add_or_update_group(
            chat_id=chat.id,
            title=chat.title or f"Group {chat.id}"
        )
        
        logger.info(f"Group {chat.id} registered in database")
        
    except Exception as e:
        logger.error(f"Error handling bot added to group: {e}", exc_info=True)


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=LEAVE_TRANSITION))
async def on_bot_removed_from_group(event: ChatMemberUpdated, admin_service: AdminService):
    """
    Handle bot being removed from a group.
    
    Removes the group and its messages from the database.
    
    Args:
        event: Chat member update event
        admin_service: Service for admin operations
    """
    try:
        chat = event.chat
        
        if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            return
        
        logger.info(
            f"Bot removed from group: {chat.title} (ID: {chat.id})",
            extra={"chat_id": chat.id, "chat_title": chat.title}
        )
        
        await admin_service.remove_group(chat.id)
        logger.info(f"Group {chat.id} and its messages removed from database")
        
    except Exception as e:
        logger.error(f"Error handling bot removed from group: {e}", exc_info=True)


@router.message(
    lambda message: message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP],
    lambda message: not message.text or not message.text.startswith('/'),
    lambda message: message.from_user and not message.from_user.is_bot
)
async def handle_group_message(message: Message, message_service: MessageService, admin_service: AdminService):
    """
    Handle incoming messages from group chats.
    
    This handler:
    1. Filters messages from group and supergroup chats
    2. Registers group if not already registered
    3. Extracts message data (text or sticker info)
    4. Saves message to database via MessageService
    5. Triggers cleanup of old messages
    
    Args:
        message: Incoming message from Telegram
        message_service: Service for message operations
        admin_service: Service for admin operations
    """
    try:
        # Register group if not already registered
        try:
            await admin_service.add_or_update_group(
                chat_id=message.chat.id,
                title=message.chat.title or f"Group {message.chat.id}"
            )
        except Exception as e:
            logger.error(f"Failed to register group: {e}", exc_info=True)
        
        # Extract text content or sticker description
        text = message.text
        
        if not text and message.sticker:
            # Build sticker description for analysis
            emoji = message.sticker.emoji or "стикер"
            text = f"[стикер: {emoji}]"
        
        if not text and message.animation:
            text = "[GIF]"
        
        # Skip messages without text, sticker, or animation
        if not text:
            logger.debug(
                "Skipping message without text, sticker, or animation",
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
                "text_length": len(text)
            }
        )
        
        # Save message to database
        await message_service.save_message(
            message_id=message.message_id,
            chat_id=message.chat.id,
            user_id=user_id,
            username=username,
            text=text,
            timestamp=timestamp,
            reactions={},  # Reactions will be updated separately
            reply_to_message_id=reply_to_message_id
        )
        
        # Trigger cleanup of old messages (with debounce protection)
        await message_service.cleanup_old_messages()
        
        # Skip message for processing by other handlers (e.g., @mention)
        raise SkipHandler()
        
    except SkipHandler:
        # Re-raise SkipHandler to continue processing
        raise
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


@router.edited_message(
    lambda message: message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP],
    lambda message: message.from_user and not message.from_user.is_bot
)
async def handle_edited_message(message: Message, message_service: MessageService):
    """
    Handle edited messages in group chats.
    
    Updates message text in the database.
    
    Args:
        message: Edited message from Telegram
        message_service: Service for message operations
    """
    try:
        if not message.text:
            logger.debug(
                "Skipping edited message without text",
                extra={
                    "message_id": message.message_id,
                    "chat_id": message.chat.id
                }
            )
            return
        
        user_id = message.from_user.id if message.from_user else 0
        username = message.from_user.username or message.from_user.first_name or "Unknown"
        
        reply_to_message_id = None
        if message.reply_to_message:
            reply_to_message_id = message.reply_to_message.message_id
        
        # Use edit_date if available, otherwise use date
        edit_date = message.edit_date or message.date
        if isinstance(edit_date, int):
            timestamp = datetime.fromtimestamp(edit_date)
        else:
            timestamp = datetime.fromtimestamp(edit_date.timestamp())
        
        logger.debug(
            "Processing edited message",
            extra={
                "message_id": message.message_id,
                "chat_id": message.chat.id,
                "user_id": user_id,
                "username": username,
                "text_length": len(message.text)
            }
        )
        
        # Save/update message in database (ON CONFLICT will update text)
        await message_service.save_message(
            message_id=message.message_id,
            chat_id=message.chat.id,
            user_id=user_id,
            username=username,
            text=message.text,
            timestamp=timestamp,
            reactions={},
            reply_to_message_id=reply_to_message_id
        )
        
        logger.info(
            f"Message {message.message_id} updated in database",
            extra={"chat_id": message.chat.id}
        )
        
    except Exception as e:
        logger.error(
            f"Error handling edited message: {e}",
            extra={
                "message_id": message.message_id if message else None,
                "chat_id": message.chat.id if message and message.chat else None
            },
            exc_info=True
        )
