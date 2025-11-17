"""
Message formatter for Telegram bot responses.
"""
import logging
from typing import Dict, Any


logger = logging.getLogger(__name__)


class MessageFormatter:
    """Formats messages for Telegram with Markdown support."""
    
    @staticmethod
    def format_analysis_result(analysis: str, period_hours: int, from_cache: bool = False) -> str:
        """
        Format analysis result for Telegram message.
        
        Args:
            analysis: Raw analysis text from OpenAI
            period_hours: Number of hours analyzed
            from_cache: Whether the result was retrieved from cache
            
        Returns:
            Formatted message with Markdown
        """
        try:
            # Create header with period information
            header = f"📊 *Анализ сообщений за последние {period_hours} ч*\n\n"
            
            # Add the analysis content
            # Ensure proper Markdown escaping for special characters if needed
            formatted_analysis = analysis.strip()
            
            # Add footer
            if from_cache:
                footer = "\n\n_Анализ выполнен с помощью AI (из кеша)_"
            else:
                footer = "\n\n_Анализ выполнен с помощью AI_"
            
            result = header + formatted_analysis + footer
            
            logger.debug(f"Formatted analysis result ({len(result)} chars, from_cache={from_cache})")
            return result
            
        except Exception as e:
            logger.error(f"Error formatting analysis result: {e}")
            # Return a safe fallback
            return f"📊 Анализ за {period_hours} ч\n\n{analysis}"
    
    @staticmethod
    def format_stats(stats: Dict[str, Any]) -> str:
        """
        Format database statistics for Telegram message.
        
        Args:
            stats: Dictionary containing statistics data
            
        Returns:
            Formatted statistics message with Markdown
        """
        try:
            message_parts = ["📈 *Статистика базы данных*\n"]
            
            # Total messages
            if 'total_messages' in stats:
                message_parts.append(f"📝 Всего сообщений: *{stats['total_messages']}*")
            
            # Oldest message
            if 'oldest_message' in stats and stats['oldest_message']:
                message_parts.append(f"📅 Самое старое сообщение: {stats['oldest_message']}")
            
            # Newest message
            if 'newest_message' in stats and stats['newest_message']:
                message_parts.append(f"📅 Самое новое сообщение: {stats['newest_message']}")
            
            # Cache entries
            if 'cache_entries' in stats:
                message_parts.append(f"💾 Записей в кеше: *{stats['cache_entries']}*")
            
            # Storage period
            if 'storage_period_hours' in stats:
                message_parts.append(f"⏱ Период хранения: *{stats['storage_period_hours']} ч*")
            
            # Collection status
            if 'collection_enabled' in stats:
                status = "✅ Включен" if stats['collection_enabled'] else "❌ Выключен"
                message_parts.append(f"🔄 Сбор сообщений: {status}")
            
            result = "\n".join(message_parts)
            
            logger.debug("Formatted statistics message")
            return result
            
        except Exception as e:
            logger.error(f"Error formatting stats: {e}")
            return "📈 Статистика\n\nОшибка форматирования данных"
    
    @staticmethod
    def format_error(error_message: str) -> str:
        """
        Format error message for Telegram.
        
        Args:
            error_message: Error message text
            
        Returns:
            Formatted error message
        """
        return f"❌ *Ошибка*\n\n{error_message}"
    
    @staticmethod
    def format_success(message: str) -> str:
        """
        Format success message for Telegram.
        
        Args:
            message: Success message text
            
        Returns:
            Formatted success message
        """
        return f"✅ {message}"
    
    @staticmethod
    def format_debounce_warning(operation: str, remaining_seconds: float) -> str:
        """
        Format debounce warning message.
        
        Args:
            operation: Name of the operation
            remaining_seconds: Seconds remaining in debounce period
            
        Returns:
            Formatted warning message
        """
        minutes = int(remaining_seconds // 60)
        seconds = int(remaining_seconds % 60)
        
        if minutes > 0:
            time_str = f"{minutes} мин {seconds} сек"
        else:
            time_str = f"{seconds} сек"
        
        return (
            f"⏳ *Слишком частый запрос*\n\n"
            f"Операция '{operation}' была выполнена недавно.\n"
            f"Пожалуйста, подождите еще {time_str}."
        )
