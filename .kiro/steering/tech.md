# Technology Stack

## Core Technologies

- **Python**: 3.12+
- **Framework**: aiogram 3.13.1 (async Telegram bot framework)
- **Database**: SQLite with aiosqlite 0.20.0
- **AI/LLM**: OpenAI SDK 2.8.0 (default model: gpt-4o-mini)
- **Configuration**: python-dotenv 1.0.1

## Testing

- pytest 8.3.3
- pytest-asyncio 0.24.0
- pytest-mock 3.14.0
- pytest-cov 5.0.0

## Deployment

- Docker & Docker Compose
- Volume mount for persistent SQLite database

## Common Commands

### Local Development
```bash
# Setup virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run bot
python -m bot.main
```

### Docker
```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test types
pytest -m unit
pytest -m integration
```

### Database Utilities
```bash
# Check database state
python check_db.py

# Diagnose bot message collection
python scripts/diagnose_bot.py
```

## Configuration

All configuration via environment variables in `.env` file (see `.env.example` for template).
Never commit `.env` to version control.
