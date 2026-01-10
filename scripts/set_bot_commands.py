"""
Script to set bot commands in Telegram.

This helps users discover available commands through the Telegram UI.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aiogram import Bot
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
)
from config.settings import Config


async def set_commands():
    """Set bot commands for different scopes."""
    config = Config.from_env()
    bot = Bot(token=config.bot_token)
    
    try:
        # First, delete any admin-specific commands that might override group commands
        from aiogram.types import BotCommandScopeChat
        
        print("🗑️  Clearing admin-specific command scopes...")
        try:
            await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=config.admin_id))
            print("   ✓ Cleared BotCommandScopeChat for admin")
        except Exception as e:
            print(f"   ⚠️  BotCommandScopeChat: {e}")
        
        # Commands for all group chats (available to all users)
        group_commands = [
            BotCommand(command="anal", description="Анализ сообщений (6 часов)"),
            BotCommand(command="deep_anal", description="Глубокий анализ (12 часов)"),
            BotCommand(command="horoscope", description="Гороскоп на основе сообщений"),
            BotCommand(command="ask", description="Задать вопрос боту"),
        ]
        
        await bot.set_my_commands(
            commands=group_commands,
            scope=BotCommandScopeAllGroupChats()
        )
        print("✅ Group commands set successfully")
        
        # Commands for all private chats (admin will see these in private chat with bot)
        private_commands = [
            BotCommand(command="analyze", description="Анализ сообщений"),
            BotCommand(command="horoscope", description="Создать гороскоп для пользователя"),
            BotCommand(command="ask", description="Задать вопрос боту"),
            BotCommand(command="stats", description="Статистика базы данных"),
            BotCommand(command="clear_db", description="Очистить базу данных"),
            BotCommand(command="set_storage", description="Установить период хранения"),
            BotCommand(command="set_analysis", description="Установить период анализа"),
            BotCommand(command="start_collection", description="Запустить сбор сообщений"),
            BotCommand(command="stop_collection", description="Остановить сбор сообщений"),
        ]
        
        await bot.set_my_commands(
            commands=private_commands,
            scope=BotCommandScopeAllPrivateChats()
        )
        print("✅ Private chat commands set successfully")
        
        # Note: BotCommandScopeAllPrivateChats doesn't override group commands
        # Admin will see group commands (anal, deep_anal) in groups
        # and admin commands in private chat with bot
        
        print("\n📋 Registered commands:")
        print("\nGroup commands (all users including admin):")
        for cmd in group_commands:
            print(f"  /{cmd.command} - {cmd.description}")
        
        print("\nPrivate chat commands (admin):")
        for cmd in private_commands:
            print(f"  /{cmd.command} - {cmd.description}")
        
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(set_commands())
