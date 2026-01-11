"""Diagnostic script for checking bot message reception."""
import asyncio
import logging
import sys
from pathlib import Path

# Add root directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config.settings import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create router
router = Router()


@router.message()
async def debug_all_messages(message: Message):
    """Handler for all messages for diagnostics."""
    print("\n" + "=" * 70)
    print("📨 ПОЛУЧЕНО СООБЩЕНИЕ")
    print("=" * 70)
    print(f"Тип чата:        {message.chat.type}")
    print(f"ID чата:         {message.chat.id}")
    print(f"Название чата:   {message.chat.title or message.chat.first_name or 'N/A'}")
    print(f"ID сообщения:    {message.message_id}")
    
    if message.from_user:
        print(f"От пользователя: {message.from_user.id}")
        print(f"Username:        @{message.from_user.username or 'N/A'}")
        print(f"Имя:             {message.from_user.first_name or 'N/A'}")
    
    if message.text:
        preview = message.text[:100] + "..." if len(message.text) > 100 else message.text
        print(f"Текст:           {preview}")
    else:
        print(f"Текст:           [Нет текста]")
    
    # Check if message will be processed by main handler
    from aiogram.enums import ChatType
    is_group = message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]
    
    print(f"\n{'✅' if is_group else '❌'} Будет обработано основным ботом: {is_group}")
    
    if not is_group:
        print("\n⚠️  ВНИМАНИЕ: Это сообщение НЕ будет сохранено в БД!")
        print("   Основной бот обрабатывает только групповые сообщения.")
        print("   Добавьте бота в групповой чат для сохранения сообщений.")
    
    print("=" * 70 + "\n")


async def main():
    """Launch diagnostic bot."""
    print("\n" + "=" * 70)
    print("🔍 ДИАГНОСТИЧЕСКИЙ РЕЖИМ БОТА")
    print("=" * 70)
    
    # Load configuration
    try:
        config = Config.from_env()
        print(f"✅ Конфигурация загружена")
        print(f"   Admin ID: {config.admin_id}")
        print(f"   Collection enabled: {config.collection_enabled}")
        print(f"   Debug mode: {config.debug_mode}")
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")
        return
    
    # Create bot and dispatcher
    try:
        bot = Bot(
            token=config.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
        
        dp = Dispatcher()
        dp.include_router(router)
        
        print(f"✅ Бот инициализирован")
        print("\n" + "=" * 70)
        print("📡 БОТ ЗАПУЩЕН И ОЖИДАЕТ СООБЩЕНИЯ...")
        print("=" * 70)
        print("\nОтправьте любое сообщение боту:")
        print("  • В личные сообщения")
        print("  • В групповой чат (рекомендуется)")
        print("\nДля остановки нажмите Ctrl+C")
        print("=" * 70 + "\n")
        
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            await bot.session.close()
        except:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("🛑 БОТ ОСТАНОВЛЕН")
        print("=" * 70)
