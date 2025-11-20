# Project Structure

## Architecture Pattern

Layered architecture with clear separation of concerns:

```
bot/          → Presentation layer (routers, filters, middleware)
services/     → Business logic layer
database/     → Data access layer (models, repositories, connection)
openai_client/→ External API integration
config/       → Configuration management
utils/        → Cross-cutting utilities
```

## Directory Layout

### `/bot`
Telegram bot interface layer
- `main.py` - Entry point, dependency injection, bot initialization
- `routers/` - Command and message handlers (admin, message, reaction)
- `filters/` - Custom filters (admin authentication)
- `middlewares/` - Request processing middleware (collection toggle)

### `/services`
Business logic services (no direct Telegram or database dependencies)
- `message_service.py` - Message collection and cleanup
- `analysis_service.py` - Message analysis orchestration with caching/debouncing
- `admin_service.py` - Admin operations (config, stats, database management)

### `/database`
Data persistence layer
- `connection.py` - Database connection management
- `models.py` - Data models (Message, Config, Cache, Debounce)
- `repository.py` - Data access repositories (CRUD operations)

### `/openai_client`
OpenAI API integration
- `client.py` - OpenAI client wrapper for message analysis

### `/config`
Configuration management
- `settings.py` - Environment variable loading and validation

### `/utils`
Shared utilities
- `cache_manager.py` - Result caching logic
- `debounce_manager.py` - Operation rate limiting
- `message_formatter.py` - Telegram message formatting with escaping

### `/tests`
Test suite
- `unit/` - Unit tests for individual components
- `integration/` - Integration tests for component interactions

### `/scripts`
Utility scripts
- `check_database.py` - Database inspection
- `diagnose_bot.py` - Message collection diagnostics

### `/data`
Runtime data (created automatically)
- SQLite database file (path configurable via DB_PATH)

## Key Design Patterns

- **Dependency Injection**: Services injected via dispatcher in `bot/main.py`
- **Repository Pattern**: Database access abstracted through repositories
- **Service Layer**: Business logic isolated from framework code
- **Async/Await**: Fully asynchronous using asyncio
- **Dataclasses**: Models defined as dataclasses for immutability

## Module Entry Point

Run as module: `python -m bot.main`
