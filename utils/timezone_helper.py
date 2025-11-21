"""Timezone conversion utilities for datetime formatting."""

from datetime import datetime
from typing import Optional
import logging
import pytz

logger = logging.getLogger(__name__)


def convert_to_timezone(
    dt: datetime,
    timezone_str: Optional[str]
) -> datetime:
    """
    Convert UTC datetime to specified timezone.
    
    Args:
        dt: UTC datetime (naive or aware)
        timezone_str: IANA timezone identifier or None for UTC
        
    Returns:
        Timezone-aware datetime in specified timezone
    """
    # If no timezone specified, return as UTC
    if timezone_str is None:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=pytz.UTC)
        return dt
    
    # Ensure datetime is UTC-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    
    # Convert to target timezone
    try:
        target_tz = pytz.timezone(timezone_str)
        return dt.astimezone(target_tz)
    except pytz.exceptions.UnknownTimeZoneError:
        logger.error(f"Unknown timezone '{timezone_str}', falling back to UTC")
        return dt


def format_datetime(
    dt: datetime,
    timezone_str: Optional[str],
    format_str: str = "%Y-%m-%d %H:%M:%S"
) -> str:
    """
    Format datetime in specified timezone.
    
    Args:
        dt: UTC datetime
        timezone_str: IANA timezone identifier or None for UTC
        format_str: strftime format string
        
    Returns:
        Formatted datetime string
    """
    try:
        converted_dt = convert_to_timezone(dt, timezone_str)
        return converted_dt.strftime(format_str)
    except Exception as e:
        logger.error(f"Timezone conversion failed: {e}, using UTC")
        # Fallback to UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt.strftime(format_str)
