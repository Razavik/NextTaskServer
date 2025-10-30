from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database.database import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.models.task import Task, task_assignees
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskResponse, TasksResponse, TaskAssigneesRequest
)
from app.core.security import get_current_active_user

router = APIRouter()

def check_workspace_access(workspace_id: int, user: User, db: Session) -> Workspace:
    """Проверяет доступ пользователя к рабочему пространству"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Проверяем, является ли пользователь владельцем или участником
    if workspace.owner_id != user.id:
        membership = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="Access denied to workspace")
    
    return workspace

@router.get("/workspaces/{workspace_id}/tasks", response_model=TasksResponse)
def get_tasks(
    workspace_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить список задач рабочего пространства"""
    workspace = check_workspace_access(workspace_id, current_user, db)
    
    tasks = db.query(Task).filter(Task.workspace_id == workspace_id).all()
    return TasksResponse(tasks=tasks)

@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить конкретную задачу"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Проверяем доступ к рабочему пространству задачи
    check_workspace_access(task.workspace_id, current_user, db)
    
    return task

@router.post("/", response_model=TaskResponse)
def create_task(
    task_data: TaskCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Создать новую задачу"""
    workspace = check_workspace_access(task_data.workspace_id, current_user, db)
    
    task = Task(
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        priority=task_data.priority,
        due_date=task_data.due_date,
        workspace_id=task_data.workspace_id,
        creator_id=current_user.id
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return task

@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    task_data: TaskUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Обновить задачу"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Проверяем доступ к рабочему пространству
    workspace = check_workspace_access(task.workspace_id, current_user, db)
    
    # Обновляем поля
    update_data = task_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    
    # Если статус меняется на "done", устанавливаем время завершения
    if task_data.status == "done" and task.completed_at is None:
        task.completed_at = datetime.utcnow()
    elif task_data.status != "done":
        task.completed_at = None
    
    db.commit()
    db.refresh(task)
    return task

@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Удалить задачу"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Проверяем доступ к рабочему пространству
    workspace = check_workspace_access(task.workspace_id, current_user, db)
    
    # Только владелец рабочего пространства или создатель задачи может удалить её
    if workspace.owner_id != current_user.id and task.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only workspace owner or task creator can delete task")
    
    db.delete(task)
    db.commit()
    return {"message": "Task deleted successfully"}

@router.patch("/workspaces/{workspace_id}/tasks/{task_id}/toggle", response_model=TaskResponse)
def toggle_task(
    workspace_id: int,
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Переключить статус задачи (включить/выключить)"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.workspace_id != workspace_id:
        raise HTTPException(status_code=400, detail="Task does not belong to this workspace")
    
    # Проверяем доступ
    check_workspace_access(workspace_id, current_user, db)
    
    # Переключаем статус между todo и done
    if task.status == "done":
        task.status = "todo"
        task.completed_at = None
    else:
        task.status = "done"
        task.completed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(task)
    return task

@router.post("/{task_id}/assignees", response_model=TaskResponse)
def set_task_assignees(
    task_id: int,
    assignees_data: TaskAssigneesRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Установить исполнителей задачи"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Проверяем доступ к рабочему пространству
    workspace = check_workspace_access(task.workspace_id, current_user, db)
    
    # Очищаем текущих исполнителей
    task.assignees.clear()
    
    # Добавляем новых исполнителей
    for user_id in assignees_data.assignees_ids:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            # Проверяем, является ли пользователь участником рабочего пространства
            membership = db.query(WorkspaceMember).filter(
                WorkspaceMember.workspace_id == task.workspace_id,
                WorkspaceMember.user_id == user_id
            ).first()
            if membership or workspace.owner_id == user_id:
                task.assignees.append(user)
    
    db.commit()
    db.refresh(task)
    return task
