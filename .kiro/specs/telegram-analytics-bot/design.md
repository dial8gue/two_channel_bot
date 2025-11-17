# Design Document

## Overview

Telegram-бот для анализа групповых чатов построен на основе асинхронной архитектуры с использованием Aiogram 3.x. Система состоит из нескольких слоев: обработчики сообщений, бизнес-логика, слой данных и интеграция с OpenAI API. Бот работает в режиме long polling, сохраняет сообщения в SQLite, использует кеширование для оптимизации запросов к LLM и предоставляет административный интерфейс через команды в личном чате.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Telegram API                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Aiogram Bot Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Routers    │  │  Middlewares │  │   Filters    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Service Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Message    │  │   Analysis   │  │    Admin     │      │
│  │   Service    │  │   Service    │  │   Service    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Database   │  │  OpenAI API  │  │    Cache     │
│   (SQLite)   │  │     Client   │  │   Manager    │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Component Interaction Flow

1. **Message Collection Flow**: Telegram → Bot → Message Service → Database
2. **Analysis Flow**: Admin Command → Analysis Service → Cache Check → OpenAI API → Response
3. **Admin Flow**: Admin Command → Admin Service → Database/Config Update

## Components and Interfaces

### 1. Bot Layer (`bot/`)

#### `main.py`
Точка входа приложения, инициализация бота и запуск polling.

```python
async def main():
    # Загрузка конфигурации
    # Инициализация Database
    # Регистрация роутеров и middleware
    # Запуск polling
```

#### `routers/`

**`message_router.py`**
Обработка входящих сообщений из группового чата.

```python
@router.message(ChatTypeFilter(chat_type=["group", "supergroup"]))
async def handle_group_message(message: Message, message_service: MessageService):
    # Сохранение сообщения в БД
```

**`admin_router.py`**
Обработка административных команд в личном чате.

```python
@router.message(Command("analyze"), IsAdminFilter())
async def cmd_analyze(message: Message, analysis_service: AnalysisService):
    # Запуск анализа сообщений

@router.message(Command("clear_db"), IsAdminFilter())
async def cmd_clear_db(message: Message, admin_service: AdminService):
    # Очистка базы данных

@router.message(Command("set_storage_period"), IsAdminFilter())
async def cmd_set_storage(message: Message, admin_service: AdminService):
    # Настройка периода хранения

@router.message(Command("set_analysis_period"), IsAdminFilter())
async def cmd_set_analysis(message: Message, admin_service: AdminService):
    # Настройка периода анализа

@router.message(Command("stop_collection"), IsAdminFilter())
async def cmd_stop_collection(message: Message, admin_service: AdminService):
    # Остановка сохранения сообщений

@router.message(Command("start_collection"), IsAdminFilter())
async def cmd_start_collection(message: Message, admin_service: AdminService):
    # Запуск сохранения сообщений
```

**`reaction_router.py`**
Обработка обновлений реакций на сообщения.

```python
@router.message_reaction()
async def handle_reaction(reaction: MessageReactionUpdated, message_service: MessageService):
    # Обновление реакций в БД
```

#### `filters/`

**`admin_filter.py`**
Фильтр для проверки прав администратора.

```python
class IsAdminFilter(BaseFilter):
    async def __call__(self, message: Message, config: Config) -> bool:
        return message.from_user.id == config.admin_id
```

**`chat_type_filter.py`**
Фильтр для определения типа чата.

#### `middlewares/`

**`collection_middleware.py`**
Middleware для проверки статуса сбора сообщений.

```python
class CollectionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if not config.collection_enabled:
            return
        return await handler(event, data)
```

### 2. Service Layer (`services/`)

#### `message_service.py`
Управление сохранением и извлечением сообщений.

```python
class MessageService:
    async def save_message(self, message: Message) -> None:
        # Сохранение сообщения в БД
        
    async def update_reactions(self, message_id: int, reactions: dict) -> None:
        # Обновление реакций
        
    async def get_messages_by_period(self, hours: int) -> List[MessageModel]:
        # Получение сообщений за период
        
    async def cleanup_old_messages(self, storage_period: int) -> int:
        # Удаление старых сообщений
```

#### `analysis_service.py`
Анализ сообщений с использованием OpenAI API.

```python
class AnalysisService:
    async def analyze_messages(self, hours: int = 24) -> str:
        # Проверка debounce
        # Проверка кеша
        # Получение сообщений
        # Вызов OpenAI API
        # Кеширование результата
        # Возврат анализа
        
    async def _check_debounce(self) -> bool:
        # Проверка времени последнего запроса
        
    async def _generate_cache_key(self, messages: List[MessageModel]) -> str:
        # Генерация ключа кеша на основе хеша сообщений
```

#### `admin_service.py`
Управление административными функциями.

```python
class AdminService:
    async def clear_database(self) -> None:
        # Очистка всех сообщений
        
    async def set_storage_period(self, hours: int) -> None:
        # Обновление периода хранения
        
    async def set_analysis_period(self, hours: int) -> None:
        # Обновление периода анализа
        
    async def toggle_collection(self, enabled: bool) -> None:
        # Включение/выключение сбора сообщений
        
    async def get_stats(self) -> dict:
        # Получение статистики БД
```

### 3. Data Layer (`database/`)

#### `models.py`
Определение моделей данных.

```python
@dataclass
class MessageModel:
    id: int
    message_id: int
    chat_id: int
    user_id: int
    username: str
    text: str
    timestamp: datetime
    reactions: dict  # JSON: {emoji: count}
    reply_to_message_id: Optional[int]
    
@dataclass
class ConfigModel:
    key: str
    value: str
    
@dataclass
class CacheModel:
    key: str
    value: str
    created_at: datetime
    expires_at: datetime
    
@dataclass
class DebounceModel:
    operation: str
    last_execution: datetime
```

#### `repository.py`
Слой доступа к данным.

```python
class MessageRepository:
    async def create(self, message: MessageModel) -> int:
        # INSERT сообщения
        
    async def update_reactions(self, message_id: int, reactions: dict) -> None:
        # UPDATE реакций
        
    async def get_by_period(self, start_time: datetime) -> List[MessageModel]:
        # SELECT сообщений за период
        
    async def delete_older_than(self, timestamp: datetime) -> int:
        # DELETE старых сообщений
        
    async def clear_all(self) -> None:
        # DELETE всех сообщений

class ConfigRepository:
    async def get(self, key: str) -> Optional[str]:
        # SELECT конфигурации
        
    async def set(self, key: str, value: str) -> None:
        # INSERT/UPDATE конфигурации

class CacheRepository:
    async def get(self, key: str) -> Optional[str]:
        # SELECT из кеша с проверкой expires_at
        
    async def set(self, key: str, value: str, ttl_minutes: int) -> None:
        # INSERT в кеш
        
    async def cleanup_expired(self) -> None:
        # DELETE истекших записей

class DebounceRepository:
    async def get_last_execution(self, operation: str) -> Optional[datetime]:
        # SELECT последнего выполнения
        
    async def update_execution(self, operation: str) -> None:
        # INSERT/UPDATE времени выполнения
```

#### `connection.py`
Управление подключением к БД.

```python
class DatabaseConnection:
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    async def init_db(self) -> None:
        # Создание таблиц
        
    async def get_connection(self) -> aiosqlite.Connection:
        # Возврат подключения
```

### 4. OpenAI Integration (`openai_client/`)

#### `client.py`
Клиент для работы с OpenAI API.

```python
class OpenAIClient:
    def __init__(self, api_key: str, base_url: str = None, model: str = "gpt-4o-mini", max_tokens: int = 4000):
        # Инициализация клиента с поддержкой кастомного base_url
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**client_kwargs)
        self.model = model
        self.max_tokens = max_tokens
        
    async def analyze_messages(self, messages: List[MessageModel]) -> str:
        # Формирование промпта
        # Вызов API с использованием self.model
        # Обработка ответа
        
    def _build_prompt(self, messages: List[MessageModel]) -> str:
        # Создание промпта для анализа
```

### 5. Configuration (`config/`)

#### `settings.py`
Управление конфигурацией из переменных окружения.

```python
@dataclass
class Config:
    # Telegram
    bot_token: str
    admin_id: int
    debug_mode: bool
    
    # OpenAI
    openai_api_key: str
    openai_base_url: Optional[str]  # Опциональный кастомный endpoint
    openai_model: str  # Модель для использования
    max_tokens: int
    
    # Database
    db_path: str
    storage_period_hours: int
    
    # Analysis
    analysis_period_hours: int
    
    # Cache
    cache_ttl_minutes: int
    
    # Debounce
    debounce_interval_seconds: int
    
    # Collection
    collection_enabled: bool
    
    @classmethod
    def from_env(cls) -> "Config":
        # Загрузка из .env
```

### 6. Utilities (`utils/`)

#### `cache_manager.py`
Управление кешированием.

```python
class CacheManager:
    async def get(self, key: str) -> Optional[str]:
        # Получение из кеша
        
    async def set(self, key: str, value: str, ttl_minutes: int) -> None:
        # Сохранение в кеш
        
    async def cleanup(self) -> None:
        # Очистка истекших записей
```

#### `debounce_manager.py`
Управление debounce логикой.

```python
class DebounceManager:
    async def can_execute(self, operation: str, interval_seconds: int) -> bool:
        # Проверка возможности выполнения
        
    async def mark_executed(self, operation: str) -> None:
        # Отметка выполнения
```

#### `message_formatter.py`
Форматирование сообщений для отправки.

```python
class MessageFormatter:
    @staticmethod
    def format_analysis_result(analysis: str, period_hours: int) -> str:
        # Форматирование результата анализа
        
    @staticmethod
    def format_stats(stats: dict) -> str:
        # Форматирование статистики
```

## Data Models

### Database Schema

```sql
-- Таблица сообщений
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    text TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    reactions TEXT,  -- JSON
    reply_to_message_id INTEGER,
    UNIQUE(message_id, chat_id)
);

CREATE INDEX idx_messages_timestamp ON messages(timestamp);
CREATE INDEX idx_messages_chat_id ON messages(chat_id);

-- Таблица конфигурации
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Таблица кеша
CREATE TABLE cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL
);

CREATE INDEX idx_cache_expires ON cache(expires_at);

-- Таблица debounce
CREATE TABLE debounce (
    operation TEXT PRIMARY KEY,
    last_execution DATETIME NOT NULL
);
```

### Message Flow Data

```python
# Входящее сообщение из Telegram
{
    "message_id": 12345,
    "chat": {"id": -100123456789, "type": "supergroup"},
    "from": {"id": 987654321, "username": "user123"},
    "text": "Текст сообщения",
    "date": 1699999999
}

# Сохраненное сообщение в БД
MessageModel(
    id=1,
    message_id=12345,
    chat_id=-100123456789,
    user_id=987654321,
    username="user123",
    text="Текст сообщения",
    timestamp=datetime(2024, 11, 16, 12, 0, 0),
    reactions={"👍": 5, "❤️": 3},
    reply_to_message_id=None
)
```

## Error Handling

### Error Categories

1. **Telegram API Errors**
   - Network errors: Retry with exponential backoff
   - Rate limiting: Wait and retry
   - Invalid token: Log and exit

2. **Database Errors**
   - Connection errors: Retry connection
   - Constraint violations: Log and skip
   - Disk full: Alert admin

3. **OpenAI API Errors**
   - Rate limiting: Use cached result or inform user
   - Invalid API key: Log and alert admin
   - Token limit exceeded: Reduce message batch size
   - Network errors: Retry with backoff

4. **Configuration Errors**
   - Missing env variables: Log and exit with clear message
   - Invalid values: Use defaults and log warning

### Error Handling Strategy

```python
# Декоратор для retry логики
@retry(max_attempts=3, backoff=2.0, exceptions=(NetworkError,))
async def api_call():
    pass

# Централизованная обработка ошибок
class ErrorHandler:
    async def handle_telegram_error(self, error: Exception) -> None:
        # Логирование и уведомление админа
        
    async def handle_openai_error(self, error: Exception) -> str:
        # Возврат понятного сообщения пользователю
```

### Logging Strategy

```python
# Структурированное логирование
logger.info("Message saved", extra={
    "message_id": message.message_id,
    "chat_id": message.chat.id,
    "user_id": message.from_user.id
})

# Уровни логирования
# DEBUG: Детальная информация для отладки
# INFO: Основные события (сохранение сообщений, выполнение команд)
# WARNING: Неожиданные ситуации (debounce срабатывание, кеш промах)
# ERROR: Ошибки, требующие внимания
# CRITICAL: Критические ошибки (невозможность подключения к БД)
```

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_message_service.py
async def test_save_message():
    # Тест сохранения сообщения
    
async def test_cleanup_old_messages():
    # Тест очистки старых сообщений

# tests/unit/test_analysis_service.py
async def test_analyze_with_cache():
    # Тест использования кеша
    
async def test_debounce_prevents_rapid_calls():
    # Тест debounce механизма

# tests/unit/test_cache_manager.py
async def test_cache_expiration():
    # Тест истечения кеша

# tests/unit/test_admin_service.py
async def test_clear_database():
    # Тест очистки БД
    
async def test_toggle_collection():
    # Тест включения/выключения сбора
```

### Integration Tests

```python
# tests/integration/test_bot_flow.py
async def test_message_collection_flow():
    # Тест полного цикла сохранения сообщения
    
async def test_analysis_flow():
    # Тест полного цикла анализа

# tests/integration/test_database.py
async def test_database_operations():
    # Тест операций с БД
```

### Test Fixtures

```python
@pytest.fixture
async def db_connection():
    # Временная БД для тестов
    
@pytest.fixture
def mock_openai_client():
    # Mock OpenAI клиента
    
@pytest.fixture
def sample_messages():
    # Набор тестовых сообщений
```

### Testing Tools

- **pytest**: Основной фреймворк для тестирования
- **pytest-asyncio**: Поддержка асинхронных тестов
- **pytest-mock**: Мокирование зависимостей
- **pytest-cov**: Измерение покрытия кода

## Deployment

### Docker Configuration

**Dockerfile**
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN python -m venv venv && \
    . venv/bin/activate && \
    pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . .

# Создание директории для БД
RUN mkdir -p /app/data

# Запуск бота
CMD ["venv/bin/python", "-m", "bot.main"]
```

**docker-compose.yml**
```yaml
version: '3.8'

services:
  telegram-bot:
    build: .
    env_file:
      - .env
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

**.env.example**
```
# Telegram
BOT_TOKEN=your_bot_token_here
ADMIN_ID=123456789
DEBUG_MODE=false

# OpenAI
OPENAI_API_KEY=your_openai_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
MAX_TOKENS=4000

# Database
DB_PATH=/app/data/bot.db
STORAGE_PERIOD_HOURS=168

# Analysis
ANALYSIS_PERIOD_HOURS=24

# Cache
CACHE_TTL_MINUTES=60

# Debounce
DEBOUNCE_INTERVAL_SECONDS=300

# Collection
COLLECTION_ENABLED=true
```

### Project Structure

```
telegram-analytics-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── message_router.py
│   │   ├── admin_router.py
│   │   └── reaction_router.py
│   ├── filters/
│   │   ├── __init__.py
│   │   ├── admin_filter.py
│   │   └── chat_type_filter.py
│   └── middlewares/
│       ├── __init__.py
│       └── collection_middleware.py
├── services/
│   ├── __init__.py
│   ├── message_service.py
│   ├── analysis_service.py
│   └── admin_service.py
├── database/
│   ├── __init__.py
│   ├── models.py
│   ├── repository.py
│   └── connection.py
├── openai_client/
│   ├── __init__.py
│   └── client.py
├── config/
│   ├── __init__.py
│   └── settings.py
├── utils/
│   ├── __init__.py
│   ├── cache_manager.py
│   ├── debounce_manager.py
│   └── message_formatter.py
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_message_service.py
│   │   ├── test_analysis_service.py
│   │   ├── test_admin_service.py
│   │   └── test_cache_manager.py
│   └── integration/
│       ├── test_bot_flow.py
│       └── test_database.py
├── data/
│   └── .gitkeep
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

### Dependencies (requirements.txt)

```
aiogram==3.13.1
aiosqlite==0.20.0
openai==1.54.0
python-dotenv==1.0.1
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-mock==3.14.0
pytest-cov==5.0.0
```

## Security Considerations

1. **API Keys**: Хранение в переменных окружения, никогда в коде
2. **Admin Verification**: Строгая проверка ADMIN_ID для всех административных команд
3. **Input Validation**: Валидация всех входных данных от пользователей
4. **SQL Injection**: Использование параметризованных запросов
5. **Rate Limiting**: Debounce механизм для предотвращения злоупотреблений
6. **Data Privacy**: Автоматическое удаление старых сообщений

## Performance Considerations

1. **Database Indexing**: Индексы на timestamp и chat_id для быстрых запросов
2. **Caching**: Кеширование результатов OpenAI для идентичных запросов
3. **Batch Processing**: Обработка сообщений пакетами при анализе
4. **Async Operations**: Полностью асинхронная архитектура
5. **Connection Pooling**: Переиспользование подключений к БД
6. **Memory Management**: Ограничение размера кеша и периодическая очистка


## Development Environment Setup

### Local Development with virtualenv

```bash
# Создание виртуального окружения
python -m venv venv

# Активация (Linux/Mac)
source venv/bin/activate

# Активация (Windows)
venv\Scripts\activate

# Установка зависимостей
pip install -r requirements.txt

# Запуск бота
python -m bot.main

# Запуск тестов
pytest

# Запуск тестов с покрытием
pytest --cov=. --cov-report=html
```

### Environment Variables

Создайте файл `.env` на основе `.env.example` и заполните необходимые значения перед запуском.
