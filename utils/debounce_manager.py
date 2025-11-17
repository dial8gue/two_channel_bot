"""
Debounce manager for preventing rapid repeated operations.
"""
import logging
from datetime import datetime, timedelta

from database.repository import DebounceRepository


logger = logging.getLogger(__name__)


class DebounceManager:
    """Manages debouncing of operations to prevent rapid repeated executions."""
    
    def __init__(self, debounce_repository: DebounceRepository):
        """
        Initialize debounce manager.
        
        Args:
            debounce_repository: Repository for debounce operations
        """
        self.debounce_repository = debounce_repository
    
    async def can_execute(self, operation: str, interval_seconds: int) -> bool:
        """
        Check if an operation can be executed based on debounce interval.
        
        Args:
            operation: Name of the operation to check
            interval_seconds: Minimum interval between executions in seconds
            
        Returns:
            True if operation can be executed, False if still in debounce period
        """
        try:
            last_execution = await self.debounce_repository.get_last_execution(operation)
            
            if last_execution is None:
                # Never executed before, allow execution
                logger.debug(f"Operation '{operation}' has no previous execution, allowing")
                return True
            
            now = datetime.now()
            time_since_last = (now - last_execution).total_seconds()
            
            if time_since_last >= interval_seconds:
                # Enough time has passed, allow execution
                logger.debug(
                    f"Operation '{operation}' last executed {time_since_last:.1f}s ago, "
                    f"allowing (interval: {interval_seconds}s)"
                )
                return True
            else:
                # Still in debounce period, deny execution
                remaining = interval_seconds - time_since_last
                logger.warning(
                    f"Operation '{operation}' is in debounce period. "
                    f"Wait {remaining:.1f}s more (last executed {time_since_last:.1f}s ago)"
                )
                return False
                
        except Exception as e:
            logger.error(f"Error checking debounce for operation '{operation}': {e}")
            # On error, allow execution to avoid blocking legitimate requests
            return True
    
    async def mark_executed(self, operation: str) -> None:
        """
        Mark an operation as executed at the current time.
        
        This should be called after successfully executing an operation.
        
        Args:
            operation: Name of the operation that was executed
        """
        try:
            await self.debounce_repository.update_execution(operation)
            logger.debug(f"Operation '{operation}' marked as executed")
            
        except Exception as e:
            logger.error(f"Error marking operation '{operation}' as executed: {e}")
            raise
