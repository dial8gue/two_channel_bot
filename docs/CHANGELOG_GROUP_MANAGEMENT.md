# Changelog: Управление группами

## Добавленная функциональность

### Новая команда `/manage_groups`
Администратор может управлять группами через интерактивный интерфейс:
- Просмотр списка всех групп с количеством сообщений
- Отключение/включение бота в конкретной группе
- Принудительный выход из группы

### Автоматическая регистрация групп
- Группы автоматически регистрируются при добавлении бота
- Также регистрируются при получении первого сообщения
- По умолчанию все группы включены

### Блокировка отключенных групп
Когда бот отключен в группе:
- Отвечает "Я отключен админом для этой конфы." только на команды и упоминания
- Обычные сообщения игнорируются
- Сообщения не сохраняются в базу данных
- Команды не обрабатываются

## Изменённые файлы

### Новые файлы:
1. `bot/middlewares/group_check_middleware.py` - middleware для проверки статуса группы
2. `scripts/migrate_add_groups_table.py` - скрипт миграции для существующих баз
3. `.kiro/steering/group-management.md` - документация по управлению группами
4. `CHANGELOG_GROUP_MANAGEMENT.md` - этот файл

### Изменённые файлы:

#### База данных:
- `database/models.py` - добавлена модель `GroupModel`
- `database/repository.py` - добавлен `GroupRepository` с методами CRUD
- `database/connection.py` - добавлено создание таблицы `groups`

#### Сервисы:
- `services/admin_service.py` - добавлены методы управления группами:
  - `get_all_groups()`
  - `add_or_update_group()`
  - `toggle_group()`
  - `is_group_enabled()`
  - `remove_group()`

#### Роутеры:
- `bot/routers/admin_router.py` - добавлены:
  - Команда `/manage_groups`
  - Callback handlers для действий с группами
- `bot/routers/message_router.py` - добавлены:
  - Обработчик события добавления бота в группу
  - Автоматическая регистрация группы при получении сообщения

#### Инициализация:
- `bot/main.py` - добавлены:
  - Создание `GroupRepository`
  - Инжекция в `AdminService`
  - Регистрация `GroupCheckMiddleware`
- `bot/middlewares/__init__.py` - экспорт `GroupCheckMiddleware`

#### Документация:
- `README.md` - добавлен раздел "Управление группами"

## Миграция для существующих пользователей

Если у вас уже есть работающий бот, выполните миграцию:

```bash
# Для Docker
docker-compose exec bot python scripts/migrate_add_groups_table.py

# Для локального запуска
python scripts/migrate_add_groups_table.py
```

## Структура таблицы groups

```sql
CREATE TABLE groups (
    chat_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    added_at DATETIME NOT NULL
)
```

## Использование

### Отключить бота в группе:
1. Отправьте `/manage_groups` боту в личные сообщения
2. Найдите нужную группу в списке
3. Нажмите "🔴 Отключить"

### Включить бота обратно:
1. Отправьте `/manage_groups` боту в личные сообщения
2. Найдите отключенную группу (помечена ⛔️)
3. Нажмите "🟢 Включить"

### Покинуть группу:
1. Отправьте `/manage_groups` боту в личные сообщения
2. Найдите нужную группу
3. Нажмите "🚪 Покинуть"
4. Бот отправит в группу "Я ливаю отсюда!" и выйдет
5. Группа будет удалена из базы данных

## Технические детали

### Архитектура
Следует layered architecture pattern проекта:
- **Models** (`database/models.py`) - данные
- **Repository** (`database/repository.py`) - доступ к данным
- **Service** (`services/admin_service.py`) - бизнес-логика
- **Router** (`bot/routers/admin_router.py`) - обработка команд
- **Middleware** (`bot/middlewares/group_check_middleware.py`) - проверка статуса

### Dependency Injection
Все зависимости инжектятся через dispatcher в `bot/main.py`

### Async/Await
Все операции асинхронные, используют `asyncio`

## Безопасность

- Команда `/manage_groups` доступна только администратору (проверка через `IsAdminFilter`)
- Все операции с базой данных используют prepared statements (защита от SQL injection)
- Middleware проверяет статус группы перед обработкой каждого сообщения

## Производительность

- Проверка статуса группы выполняется через индексированное поле `chat_id` (PRIMARY KEY)
- Middleware работает только для групповых сообщений
- Минимальное количество запросов к базе данных
