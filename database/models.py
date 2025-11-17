"""
Data models for the Telegram analytics bot.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json


@dataclass
class MessageModel:
    """Model for storing Telegram messages."""
    message_id: int
    chat_id: int
    user_id: int
    username: str
    text: str
    timestamp: datetime
    reactions: dict = field(default_factory=dict)
    reply_to_message_id: Optional[int] = None
    id: Optional[int] = None
    
    def reactions_to_json(self) -> str:
        """Serialize reactions dict to JSON string."""
        return json.dumps(self.reactions, ensure_ascii=False)
    
    @staticmethod
    def reactions_from_json(json_str: Optional[str]) -> dict:
        """Deserialize reactions from JSON string to dict."""
        if not json_str:
            return {}
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'message_id': self.message_id,
            'chat_id': self.chat_id,
            'user_id': self.user_id,
            'username': self.username,
            'text': self.text,
            'timestamp': self.timestamp.isoformat(),
            'reactions': self.reactions,
            'reply_to_message_id': self.reply_to_message_id
        }


@dataclass
class ConfigModel:
    """Model for storing configuration key-value pairs."""
    key: str
    value: str
    
    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            'key': self.key,
            'value': self.value
        }


@dataclass
class CacheModel:
    """Model for storing cached analysis results."""
    key: str
    value: str
    created_at: datetime
    expires_at: datetime
    
    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            'key': self.key,
            'value': self.value,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat()
        }


@dataclass
class DebounceModel:
    """Model for tracking operation execution times."""
    operation: str
    last_execution: datetime
    
    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            'operation': self.operation,
            'last_execution': self.last_execution.isoformat()
        }
