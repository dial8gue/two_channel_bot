"""
Script to clear all bot commands from Telegram.

Use this to reset all command configurations.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aiogram import Bot
from aiogram.types import (
    BotCommandScopeDefault,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeChat,
)
from config.settings import Config


async def clear_all_commands():
    """Clear all bot commands from all scopes."""
    config = Config.from_env()
    bot = Bot(token=config.bot_token)
    
    try:
        print("🗑️  Clearing all bot commands...\n")
        
        # Clear default scope
        try:
            await bot.delete_my_commands(scope=BotCommandScopeDefault())
            print("✅ Cleared BotCommandScopeDefault")
        except Exception as e:
            print(f"❌ BotCommandScopeDefault: {e}")
        
        # Clear all private chats
        try:
            await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
            print("✅ Cleared BotCommandScopeAllPrivateChats")
        except Exception as e:
            print(f"❌ BotCommandScopeAllPrivateChats: {e}")
        
        # Clear all group chats
        try:
            await bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())
            print("✅ Cleared BotCommandScopeAllGroupChats")
        except Exception as e:
            print(f"❌ BotCommandScopeAllGroupChats: {e}")
        
        # Clear all chat administrators
        try:
            await bot.delete_my_commands(scope=BotCommandScopeAllChatAdministrators())
            print("✅ Cleared BotCommandScopeAllChatAdministrators")
        except Exception as e:
            print(f"❌ BotCommandScopeAllChatAdministrators: {e}")
        
        # Clear admin-specific scope
        try:
            await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=config.admin_id))
            print(f"✅ Cleared BotCommandScopeChat for admin (ID: {config.admin_id})")
        except Exception as e:
            print(f"❌ BotCommandScopeChat for admin: {e}")
        
        print("\n✅ All commands cleared successfully!")
        print("\nNext steps:")
        print("1. Restart your Telegram client")
        print("2. Run 'python scripts/set_bot_commands.py' to set new commands")
        
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(clear_all_commands())
