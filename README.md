# 🏢 Microservice Reservation System

Enterprise-grade система бронирования ресурсов (столиков, помещений, услуг), построенная на базе микросервисной архитектуры. Проект демонстрирует современные подходы к backend-разработке на Python: асинхронность, Event-Driven Architecture (EDA), предотвращение состояния гонки (Race Conditions) и Stateless авторизацию.

## 🛠 Технологический стек

Проект написан на **Python 3.11+** с использованием практик строгой типизации и чистой архитектуры (вдохновлено экосистемой .NET / C#).

*   **Web Framework:** FastAPI (асинхронный REST API)
*   **Database & ORM:** PostgreSQL + SQLAlchemy 2.0 + asyncpg
*   **Migrations:** Alembic
*   **Message Broker:** RabbitMQ + FastStream
*   **Authentication:** JWT (JSON Web Tokens) + OAuth2 + bcrypt
*   **Validation:** Pydantic V2
*   **Infrastructure:** Docker & Docker Compose

## 🏗 Архитектура проекта

Проект использует паттерн **Database-per-Service** (своя независимая БД для каждого сервиса) и состоит из 4 независимых компонентов:

1.  🔐 **Identity Service (`:8001`)**
    *   Регистрация и аутентификация пользователей.
    *   Хэширование паролей и генерация JWT-токенов.
    *   *База данных:* `reservation_db`
2.  🏪 **Catalog Service (`:8002`)**
    *   Управление заведениями (Venues) и ресурсами/столиками (Resources).
    *   Stateless проверка токенов без обращения к Identity.
    *   *База данных:* `catalog_db`
3.  📅 **Booking Service (`:8003`)**
    *   Создание и управление бронированиями.
    *   **Ключевая фича:** Защита от двойного бронирования (Double Booking) на уровне SQL-транзакций (Overlap checks).
    *   Публикация событий в RabbitMQ при создании/отмене брони.
    *   *База данных:* `booking_db`
4.  🔔 **Notification Service (Background Worker)**
    *   Фоновый консьюмер без HTTP-интерфейса.
    *   Мгновенно читает очередь `booking_notifications` из RabbitMQ и "отправляет" уведомления (Email/Push) пользователям.

## 🚀 Как запустить проект локально

### 1. Подготовка инфраструктуры (Docker)
Убедитесь, что у вас установлен Docker Desktop. В корне проекта создайте файл `.env` (см. `env.example`) и запустите базы данных и брокер сообщений:
```bash
docker-compose up -d
```

### 2. Установка зависимостей Python
Создайте виртуальное окружение и установите библиотеки:
```bash
python -m venv venv
source venv/Scripts/activate  # Для Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Применение миграций БД
Выполните миграции для каждого сервиса, чтобы создать таблицы в PostgreSQL:
```bash
# Для Identity Service
alembic -c alembic.ini -x db=identity revision --autogenerate
alembic upgrade head

# (Повторить для Catalog и Booking сервисов, предварительно настроив alembic.ini)
```
*Примечание: В проекте также реализован механизм `EnsureCreated` через `lifespan` FastAPI для автоматического создания таблиц при старте.*

### 4. Запуск микросервисов
Откройте 4 разных окна терминала (с активированным `venv`) и запустите каждый сервис:

```bash
# Терминал 1: Identity Service
uvicorn identity_service.main:app --reload --port 8001

# Терминал 2: Catalog Service
uvicorn catalog_service.main:app --reload --port 8002

# Терминал 3: Booking Service
uvicorn booking_service.main:app --reload --port 8003

# Терминал 4: Notification Worker (RabbitMQ Consumer)
faststream run notification_service.main:app
```

## 📚 Документация API (Swagger UI)

FastAPI автоматически генерирует интерактивную OpenAPI документацию. После запуска сервисов, перейдите по ссылкам:
*   Identity API: [http://localhost:8001/api/docs](http://localhost:8001/api/docs)
*   Catalog API: [http://localhost:8002/api/docs](http://localhost:8002/api/docs)
*   Booking API:[http://localhost:8003/api/docs](http://localhost:8003/api/docs)

В каждом Swagger-интерфейсе доступна кнопка **Authorize** для тестирования защищенных эндпоинтов с помощью JWT.

## 💡 Особенности реализации (Highlights)

*   **Fail-Fast конфигурация:** Использование `pydantic-settings` не позволяет приложению запуститься, если отсутствуют критические переменные окружения.
*   **Clean Dependency Injection:** Использование `Depends()` в FastAPI для внедрения сессий БД и парсинга токенов (аналог `IServiceCollection` в .NET).
*   **Graceful Shutdown:** Корректное закрытие пулов соединений к PostgreSQL и RabbitMQ при остановке приложения через контекстные менеджеры `lifespan`.
