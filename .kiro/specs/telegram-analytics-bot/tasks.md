# Implementation Plan

- [x] 1. Настройка проекта и базовой инфраструктуры





  - Создать структуру директорий проекта
  - Создать requirements.txt с необходимыми зависимостями
  - Создать .env.example с шаблоном переменных окружения
  - Создать .gitignore для Python проекта
  - _Requirements: 10.1, 10.2_

- [x] 2. Реализация слоя конфигурации





  - Создать config/settings.py с классом Config для загрузки переменных окружения
  - Реализовать валидацию обязательных параметров конфигурации
  - Добавить значения по умолчанию для опциональных параметров
  - Добавить поддержку OPENAI_BASE_URL и OPENAI_MODEL для гибкой конфигурации OpenAI
  - _Requirements: 2.1, 3.1, 3.4, 5.1, 6.1, 6.2, 6.3, 6.4, 6.5, 7.4_

- [x] 3. Реализация слоя базы данных






- [x] 3.1 Создать модели данных

  - Создать database/models.py с dataclass моделями (MessageModel, ConfigModel, CacheModel, DebounceModel)
  - Добавить методы сериализации/десериализации для JSON полей
  - _Requirements: 8.1, 8.2, 8.3_


- [x] 3.2 Реализовать подключение к БД

  - Создать database/connection.py с классом DatabaseConnection
  - Реализовать метод init_db() для создания таблиц и индексов
  - Добавить SQL схему для всех таблиц (messages, config, cache, debounce)
  - _Requirements: 5.1, 10.4_

- [x] 3.3 Реализовать репозитории


  - Создать database/repository.py с классами MessageRepository, ConfigRepository, CacheRepository, DebounceRepository
  - Реализовать CRUD операции для каждого репозитория
  - Использовать параметризованные запросы для защиты от SQL injection
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 5.2, 5.3_

- [x] 4. Реализация утилит для кеширования и debounce






- [x] 4.1 Создать менеджер кеша

  - Создать utils/cache_manager.py с классом CacheManager
  - Реализовать методы get(), set() и cleanup() для работы с кешем
  - Добавить проверку истечения TTL при получении из кеша
  - _Requirements: 6.1, 6.2, 6.3, 6.4_


- [x] 4.2 Создать менеджер debounce

  - Создать utils/debounce_manager.py с классом DebounceManager
  - Реализовать методы can_execute() и mark_executed()
  - Добавить логику проверки временного интервала между операциями
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 4.3 Создать форматтер сообщений


  - Создать utils/message_formatter.py с классом MessageFormatter
  - Реализовать методы форматирования результатов анализа и статистики
  - Добавить поддержку Markdown форматирования для Telegram
  - _Requirements: 1.3, 1.4, 1.5_

- [x] 5. Реализация OpenAI клиента





  - Создать openai_client/client.py с классом OpenAIClient
  - Реализовать метод analyze_messages() для вызова OpenAI API
  - Создать метод _build_prompt() для формирования промпта на русском языке
  - Добавить обработку ошибок API и ограничения по токенам
  - Включить в промпт инструкции для анализа: кто о чем говорил, самые обсуждаемые посты, кто собрал больше реакций
  - Добавить поддержку кастомного base_url и выбора модели через параметры конструктора
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 6.1, 6.2, 6.3, 6.5_

- [x] 6. Реализация сервисного слоя




- [x] 6.1 Создать сервис сообщений


  - Создать services/message_service.py с классом MessageService
  - Реализовать методы save_message(), update_reactions(), get_messages_by_period()
  - Реализовать метод cleanup_old_messages() с проверкой частоты выполнения
  - Добавить логирование операций с сообщениями
  - _Requirements: 8.1, 8.2, 8.3, 5.2, 5.3, 5.4_

- [x] 6.2 Создать сервис анализа


  - Создать services/analysis_service.py с классом AnalysisService
  - Реализовать метод analyze_messages() с интеграцией debounce и кеша
  - Добавить метод _check_debounce() для проверки возможности выполнения
  - Добавить метод _generate_cache_key() на основе хеша сообщений
  - Интегрировать OpenAIClient для получения анализа
  - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3_

- [x] 6.3 Создать административный сервис


  - Создать services/admin_service.py с классом AdminService
  - Реализовать методы clear_database(), set_storage_period(), set_analysis_period()
  - Реализовать метод toggle_collection() для управления сбором сообщений
  - Добавить метод get_stats() для получения статистики БД
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 7. Реализация фильтров и middleware




- [x] 7.1 Создать фильтр администратора


  - Создать bot/filters/admin_filter.py с классом IsAdminFilter
  - Реализовать проверку user_id против ADMIN_ID из конфигурации
  - _Requirements: 3.4, 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 7.2 Создать middleware для контроля сбора


  - Создать bot/middlewares/collection_middleware.py с классом CollectionMiddleware
  - Реализовать проверку флага collection_enabled перед сохранением сообщений
  - _Requirements: 8.4, 4.4, 4.5_

- [x] 8. Реализация роутеров бота




- [x] 8.1 Создать роутер для групповых сообщений


  - Создать bot/routers/message_router.py с обработчиком групповых сообщений
  - Добавить фильтр для типа чата (group, supergroup)
  - Интегрировать MessageService для сохранения сообщений
  - Добавить обработку ошибок и логирование
  - _Requirements: 8.1, 8.2_

- [x] 8.2 Создать роутер для реакций


  - Создать bot/routers/reaction_router.py с обработчиком обновлений реакций
  - Интегрировать MessageService для обновления реакций в БД
  - _Requirements: 8.3_

- [x] 8.3 Создать роутер для административных команд


  - Создать bot/routers/admin_router.py с обработчиками команд
  - Реализовать команду /analyze для запуска анализа с опциональным параметром периода
  - Реализовать команду /clear_db для очистки базы данных
  - Реализовать команду /set_storage <hours> для настройки периода хранения
  - Реализовать команду /set_analysis <hours> для настройки периода анализа
  - Реализовать команду /stop_collection для остановки сбора сообщений
  - Реализовать команду /start_collection для запуска сбора сообщений
  - Реализовать команду /stats для получения статистики
  - Добавить фильтр IsAdminFilter для всех команд
  - Интегрировать AnalysisService и AdminService
  - Реализовать логику отправки результатов: в личку админу в debug режиме, иначе в групповой чат
  - _Requirements: 1.1, 2.2, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 9. Создать точку входа приложения





  - Создать bot/main.py с функцией main()
  - Инициализировать конфигурацию из переменных окружения
  - Инициализировать подключение к БД и создать таблицы
  - Создать экземпляры всех сервисов и утилит
  - Зарегистрировать роутеры и middleware
  - Запустить polling бота
  - Добавить graceful shutdown для корректного завершения
  - Настроить логирование с уровнями DEBUG/INFO/WARNING/ERROR
  - _Requirements: 1.1, 3.1, 3.2, 3.3, 8.1, 8.2, 8.3, 8.4_

- [x] 10. Создать Docker конфигурацию





  - Создать Dockerfile с использованием Python 3.12 и virtualenv
  - Создать docker-compose.yml с настройкой volume для БД
  - Добавить инструкции по сборке и запуску в README.md
  - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 11. Реализация тестов





- [x] 11.1 Создать unit тесты для сервисов


  - Создать tests/unit/test_message_service.py с тестами для MessageService
  - Создать tests/unit/test_analysis_service.py с тестами для AnalysisService (включая debounce и кеш)
  - Создать tests/unit/test_admin_service.py с тестами для AdminService
  - Создать tests/unit/test_cache_manager.py с тестами для CacheManager (включая истечение TTL)
  - Использовать pytest fixtures для mock объектов и тестовых данных
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 11.2 Создать integration тесты


  - Создать tests/integration/test_bot_flow.py с тестами полного цикла сохранения и анализа
  - Создать tests/integration/test_database.py с тестами операций БД
  - Использовать временную БД для изоляции тестов
  - _Requirements: 9.1, 9.2, 9.3_

- [x] 11.3 Настроить pytest конфигурацию


  - Создать pytest.ini или pyproject.toml с настройками pytest
  - Настроить pytest-asyncio для асинхронных тестов
  - Настроить pytest-cov для измерения покрытия кода
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 12. Создать документацию





  - Создать README.md с описанием проекта, установки и использования
  - Добавить примеры команд и переменных окружения
  - Добавить инструкции по запуску в Docker и локально с virtualenv
  - Добавить описание административных команд
  - _Requirements: 1.1, 2.1, 3.1, 4.1, 4.2, 4.3, 4.4, 4.5_
