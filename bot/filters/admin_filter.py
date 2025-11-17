"""Admin filter for verifying administrator privileges."""

from aiogram.filters import BaseFilter
from aiogram.types import Message
from config.settings import Config


class IsAdminFilter(BaseFilter):
    """Filter to check if the user is the bot administrator."""
    
    def __init__(self, config: Config):
        """
        Initialize the admin filter.
        
        Args:
            config: Bot configuration containing admin_id
        """
        self.config = config
    
    async def __call__(self, message: Message) -> bool:
        """
        Check if the message sender is the administrator.
        
        Args:
            message: Incoming message to check
            
        Returns:
            bool: True if sender is admin, False otherwise
        """
        if message.from_user is None:
            return False
        
        return message.from_user.id == self.config.admin_id
