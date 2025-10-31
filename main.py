from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

from app.database.database import engine, Base
from app.api.v1 import auth, workspaces, tasks, profile, comments, invites, chat

# Создаем таблицы в базе данных
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запуск приложения
    print("🚀 NextTask Server is starting...")
    yield
    # Остановка приложения
    print("🛑 NextTask Server is shutting down...")

app = FastAPI(
    title="NextTask API",
    description="API для системы управления задачами и рабочими пространствами",
    version="1.0.0",
    lifespan=lifespan
)

# Настройка CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
if allowed_origins == "*":
    allow_origins_list = ["*"]
else:
    allow_origins_list = [origin.strip() for origin in allowed_origins.split(",")]

print(f"CORS Origins: {allow_origins_list}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем статические файлы для аватаров
if os.path.exists("uploads"):
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Подключаем роуты API
api_prefix = "/api/v1"

# Основные пути с префиксом
app.include_router(auth.router, prefix=f"{api_prefix}/auth", tags=["auth"])
app.include_router(workspaces.router, prefix=f"{api_prefix}/workspaces", tags=["workspaces"])
app.include_router(tasks.router, prefix=f"{api_prefix}/tasks", tags=["tasks"])
app.include_router(profile.router, prefix=f"{api_prefix}/profile", tags=["profile"])
app.include_router(comments.router, prefix=f"{api_prefix}/comments", tags=["comments"])
app.include_router(invites.router, prefix=f"{api_prefix}/invites", tags=["invites"])
app.include_router(chat.router, prefix=f"{api_prefix}/chat", tags=["chat"])

# Прямые пути без префикса для обратной совместимости
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(profile.router, prefix="/profile", tags=["profile"])
app.include_router(comments.router, prefix="/comments", tags=["comments"])
app.include_router(invites.router, prefix="/invites", tags=["invites"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])

# Дополнительный путь для задач рабочих пространств
app.include_router(tasks.router, prefix="/workspaces", tags=["workspace-tasks"])

@app.get("/")
def root():
    """Корневой эндпоинт"""
    return {
        "message": "Welcome to NextTask API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "auth": {
                "v1": "/api/v1/auth/register",
                "direct": "/auth/register"
            },
            "workspaces": {
                "v1": "/api/v1/workspaces/",
                "direct": "/workspaces/"
            },
            "tasks": {
                "v1": "/api/v1/tasks/",
                "direct": "/tasks/",
                "workspace_tasks": "/workspaces/{workspace_id}/tasks"
            },
            "profile": {
                "v1": "/api/v1/profile/me",
                "direct": "/profile/me"
            }
        }
    }

@app.get("/health")
def health_check():
    """Проверка здоровья сервера"""
    return {"status": "healthy", "service": "NextTask API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
