"""Bot routers for handling different types of updates."""

from bot.routers.message_router import router as message_router
from bot.routers.reaction_router import router as reaction_router
from bot.routers.admin_router import create_admin_router

__all__ = [
    "message_router",
    "reaction_router",
    "create_admin_router",
]
