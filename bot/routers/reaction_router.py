"""Router for handling message reactions."""

import logging
from typing import Dict

from aiogram import Router
from aiogram.types import MessageReactionUpdated, ReactionTypeEmoji

from services.message_service import MessageService


logger = logging.getLogger(__name__)

# Create router for reaction handling
router = Router(name="reaction_router")


@router.message_reaction()
async def handle_reaction(reaction_update: MessageReactionUpdated, message_service: MessageService):
    """
    Handle message reaction updates.
    
    This handler:
    1. Receives reaction updates from Telegram
    2. Processes the new reaction state
    3. Updates reactions in the database
    
    Args:
        reaction_update: Reaction update event from Telegram
        message_service: Service for message operations
    """
    try:
        message_id = reaction_update.message_id
        chat_id = reaction_update.chat.id
        
        # Get user's old and new reactions
        old_emojis = set()
        new_emojis = set()
        
        if reaction_update.old_reaction:
            for reaction in reaction_update.old_reaction:
                if isinstance(reaction, ReactionTypeEmoji):
                    old_emojis.add(reaction.emoji)
        
        if reaction_update.new_reaction:
            for reaction in reaction_update.new_reaction:
                if isinstance(reaction, ReactionTypeEmoji):
                    new_emojis.add(reaction.emoji)
        
        # Calculate what was added and removed by this user
        added_emojis = new_emojis - old_emojis
        removed_emojis = old_emojis - new_emojis
        
        # Get current reactions from database
        reactions = await message_service.get_reactions(
            message_id=message_id,
            chat_id=chat_id
        )
        
        # Apply changes: increment for added, decrement for removed
        for emoji in added_emojis:
            reactions[emoji] = reactions.get(emoji, 0) + 1
        
        for emoji in removed_emojis:
            current_count = reactions.get(emoji, 0)
            if current_count > 1:
                reactions[emoji] = current_count - 1
            elif emoji in reactions:
                del reactions[emoji]  # Remove if count becomes 0
        
        logger.debug(
            "Processing reaction update",
            extra={
                "message_id": message_id,
                "chat_id": chat_id,
                "added": list(added_emojis),
                "removed": list(removed_emojis),
                "total_reactions": len(reactions)
            }
        )
        
        # Update reactions in database
        await message_service.update_reactions(
            message_id=message_id,
            chat_id=chat_id,
            reactions=reactions
        )
        
    except Exception as e:
        logger.error(
            f"Error handling reaction update: {e}",
            extra={
                "message_id": reaction_update.message_id if reaction_update else None,
                "chat_id": reaction_update.chat.id if reaction_update and reaction_update.chat else None
            },
            exc_info=True
        )
        # Don't re-raise - we don't want to stop the bot on reaction handling errors
