"""
Diagnostic script to test if bot receives commands in groups.

This script will show all updates the bot receives to help diagnose
why commands might not be working in group chats.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aiogram import Bot, Dispatcher
from aiogram.types import Update, Message
from aiogram.filters import Command
from config.settings import Config


async def diagnose():
    """Run diagnostic bot to see what updates are received."""
    config = Config.from_env()
    bot = Bot(token=config.bot_token)
    dp = Dispatcher()
    
    print("=" * 60)
    print("🔍 DIAGNOSTIC MODE - Testing Group Commands")
    print("=" * 60)
    print(f"Admin ID: {config.admin_id}")
    print(f"Bot Token: {config.bot_token[:10]}...")
    print()
    
    # Get bot info
    try:
        bot_info = await bot.get_me()
        print(f"✅ Bot connected: @{bot_info.username}")
        print(f"   Bot ID: {bot_info.id}")
        print(f"   Can join groups: {bot_info.can_join_groups}")
        print(f"   Can read all group messages: {bot_info.can_read_all_group_messages}")
        print()
    except Exception as e:
        print(f"❌ Failed to get bot info: {e}")
        return
    
    if not bot_info.can_read_all_group_messages:
        print("⚠️  WARNING: Bot cannot read all group messages!")
        print("   Go to @BotFather → Bot Settings → Group Privacy → Turn OFF")
        print()
    
    # Log all updates
    @dp.update()
    async def log_all_updates(update: Update):
        """Log every update received."""
        print(f"\n📨 Update received: {update.update_id}")
        
        if update.message:
            msg = update.message
            chat_type = msg.chat.type
            user = msg.from_user
            
            print(f"   Type: MESSAGE")
            print(f"   Chat: {msg.chat.title or msg.chat.first_name} (ID: {msg.chat.id}, Type: {chat_type})")
            print(f"   From: {user.first_name} (ID: {user.id}, Username: @{user.username or 'none'})")
            print(f"   Text: {msg.text or '[no text]'}")
            
            if msg.text and msg.text.startswith('/'):
                print(f"   ⚡ COMMAND DETECTED: {msg.text.split()[0]}")
        
        elif update.callback_query:
            print(f"   Type: CALLBACK_QUERY")
            print(f"   Data: {update.callback_query.data}")
        
        else:
            print(f"   Type: {update.model_dump_json(indent=2)}")
    
    # Test command handlers
    @dp.message(Command("anal"))
    async def test_anal(message: Message):
        """Test /anal command."""
        print(f"\n✅ /anal command handler triggered!")
        print(f"   Chat type: {message.chat.type}")
        await message.answer("✅ Команда /anal получена! Бот работает.")
    
    @dp.message(Command("deep_anal"))
    async def test_deep_anal(message: Message):
        """Test /deep_anal command."""
        print(f"\n✅ /deep_anal command handler triggered!")
        print(f"   Chat type: {message.chat.type}")
        await message.answer("✅ Команда /deep_anal получена! Бот работает.")
    
    @dp.message(Command("test"))
    async def test_command(message: Message):
        """Test /test command."""
        print(f"\n✅ /test command handler triggered!")
        print(f"   Chat type: {message.chat.type}")
        await message.answer("✅ Тестовая команда получена! Бот работает.")
    
    print("🚀 Starting diagnostic bot...")
    print("=" * 60)
    print("Instructions:")
    print("1. Add bot to a group if not already added")
    print("2. Send /test command in the group")
    print("3. Send /anal command in the group")
    print("4. Watch the output below")
    print("=" * 60)
    print("\n⏳ Waiting for updates... (Press Ctrl+C to stop)\n")
    
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except KeyboardInterrupt:
        print("\n\n👋 Diagnostic stopped by user")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(diagnose())
