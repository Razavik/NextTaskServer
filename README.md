# NextTask Server

FastAPI backend для системы управления задачами и рабочими пространствами.

## Возможности

- 🔐 **Аутентификация**: JWT токены, регистрация/вход
- 👥 **Рабочие пространства**: Создание, управление участниками, роли
- ✅ **Задачи**: CRUD операции, назначение исполнителей, статусы
- 💬 **Чат**: Личные сообщения и групповые чаты через WebSocket
- 📝 **Комментарии**: Комментарии к задачам
- 📧 **Приглашения**: Email-приглашения и приглашения по ссылке
- 👤 **Профиль**: Управление профилем, загрузка аватара

## Установка и запуск

### 1. Клонирование репозитория

```bash
git clone https://github.com/Razavik/NextTaskServer.git
cd NextTaskServer
```

### 2. Создание виртуального окружения

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Скопируйте `.env.example` в `.env` и настройте параметры:

```bash
cp .env.example .env
```

### 5. Запуск сервера

```bash
python main.py
```

Или с использованием uvicorn:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Сервер будет доступен по адресу: http://localhost:8000

## API Документация

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Структура проекта

```
NextTaskServer/
├── app/
│   ├── api/v1/          # API эндпоинты
│   │   ├── auth.py      # Аутентификация
│   │   ├── workspaces.py # Рабочие пространства
│   │   ├── tasks.py      # Задачи
│   │   ├── profile.py    # Профиль пользователя
│   │   ├── comments.py   # Комментарии
│   │   ├── invites.py    # Приглашения
│   │   └── chat.py       # Чат (WebSocket)
│   ├── core/
│   │   └── security.py   # Безопасность, JWT
│   ├── database/
│   │   └── database.py   # Конфигурация БД
│   ├── models/           # SQLAlchemy модели
│   ├── schemas/          # Pydantic схемы
│   └── services/         # Бизнес-логика
├── uploads/              # Загруженные файлы
├── main.py              # Основной файл приложения
├── requirements.txt     # Зависимости
└── .env.example         # Пример конфигурации
```

## API Эндпоинты

### Аутентификация
- `POST /api/v1/auth/register` - Регистрация
- `POST /api/v1/auth/token` - Вход
- `GET /api/v1/auth/users/me` - Получить текущего пользователя

### Рабочие пространства
- `GET /api/v1/workspaces/` - Список рабочих пространств
- `POST /api/v1/workspaces/` - Создать рабочее пространство
- `GET /api/v1/workspaces/{id}` - Получить рабочее пространство
- `PUT /api/v1/workspaces/{id}` - Обновить рабочее пространство
- `DELETE /api/v1/workspaces/{id}` - Удалить рабочее пространство

### Задачи
- `GET /api/v1/tasks/workspaces/{workspace_id}/tasks` - Задачи рабочего пространства
- `POST /api/v1/tasks/` - Создать задачу
- `GET /api/v1/tasks/{id}` - Получить задачу
- `PUT /api/v1/tasks/{id}` - Обновить задачу
- `DELETE /api/v1/tasks/{id}` - Удалить задачу

### Чат (WebSocket)
- `WS /api/v1/chat/ws?token={token}` - Личный чат
- `WS /api/v1/chat/ws/{workspace_id}?token={token}` - Групповой чат

## База данных

По умолчанию используется SQLite для разработки. Для продакшена рекомендуется PostgreSQL.

### Таблицы

- `users` - Пользователи
- `workspaces` - Рабочие пространства
- `workspace_members` - Участники рабочих пространств
- `tasks` - Задачи
- `task_assignees` - Исполнители задач
- `comments` - Комментарии
- `messages` - Личные сообщения
- `workspace_messages` - Сообщения групповых чатов
- `invites` - Приглашения по ссылке
- `email_invites` - Email-приглашения

## Разработка

### Добавление новых эндпоинтов

1. Создайте модель в `app/models/`
2. Создайте схему в `app/schemas/`
3. Добавьте эндпоинт в `app/api/v1/`
4. Зарегистрируйте роутер в `main.py`

### Миграции базы данных

Для миграций можно использовать Alembic:

```bash
pip install alembic
alembic init alembic
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

## Лицензия

MIT License
