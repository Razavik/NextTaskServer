from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from app.database.database import get_db
from app.models.user import User
from app.models.task import Task
from app.models.workspace import Workspace, WorkspaceMember
from app.models.comment import Comment
from app.schemas.comment import (
    CommentCreate, CommentUpdate, CommentResponse, CommentsQuery
)
from app.core.security import get_current_active_user

router = APIRouter()

def check_task_access(task_id: int, user: User, db: Session) -> Task:
    """Проверяет доступ пользователя к задаче"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Проверяем доступ к рабочему пространству задачи
    workspace = db.query(Workspace).filter(Workspace.id == task.workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Проверяем, является ли пользователь владельцем или участником
    if workspace.owner_id != user.id:
        membership = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user.id
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="Access denied to task")
    
    return task

@router.get("/tasks/{task_id}/comments", response_model=List[CommentResponse])
def get_task_comments(
    task_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить комментарии задачи"""
    task = check_task_access(task_id, current_user, db)
    
    query = db.query(Comment).filter(Comment.task_id == task_id)
    
    # Сортировка
    if order == "asc":
        query = query.order_by(Comment.created_at.asc())
    else:
        query = query.order_by(Comment.created_at.desc())
    
    comments = query.offset(offset).limit(limit).all()
    return comments

@router.get("/tasks/{task_id}/comments/count")
def get_task_comments_count(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить количество комментариев задачи"""
    task = check_task_access(task_id, current_user, db)
    
    count = db.query(func.count(Comment.id)).filter(Comment.task_id == task_id).scalar()
    return count

@router.post("/tasks/{task_id}/comments", response_model=CommentResponse)
def create_comment(
    task_id: int,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Создать комментарий к задаче"""
    task = check_task_access(task_id, current_user, db)
    
    comment = Comment(
        content=comment_data.content,
        task_id=task_id,
        author_id=current_user.id
    )
    
    db.add(comment)
    db.commit()
    db.refresh(comment)
    
    return comment

@router.patch("/comments/{comment_id}", response_model=CommentResponse)
def update_comment(
    comment_id: int,
    comment_data: CommentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Обновить комментарий"""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Только автор может редактировать комментарий
    if comment.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only author can edit comment")
    
    comment.content = comment_data.content
    db.commit()
    db.refresh(comment)
    
    return comment

@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Удалить комментарий"""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Проверяем права: автор или владелец рабочего пространства может удалить
    task = db.query(Task).filter(Task.id == comment.task_id).first()
    workspace = db.query(Workspace).filter(Workspace.id == task.workspace_id).first()
    
    if comment.author_id != current_user.id and workspace.owner_id != current_user.id:
        raise HTTPException(
            status_code=403, 
            detail="Only author or workspace owner can delete comment"
        )
    
    db.delete(comment)
    db.commit()
    
    return {"message": "Comment deleted successfully"}
