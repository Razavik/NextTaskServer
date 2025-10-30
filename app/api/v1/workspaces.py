from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database.database import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import (
    WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse,
    WorkspaceUser, WorkspaceMemberResponse, InviteUserRequest
)
from app.core.security import get_current_active_user

router = APIRouter()

@router.get("/", response_model=List[WorkspaceResponse])
def get_workspaces(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить список рабочих пространств пользователя"""
    # Получаем рабочие пространства, где пользователь является владельцем или участником
    owned_workspaces = db.query(Workspace).filter(Workspace.owner_id == current_user.id).all()
    
    member_workspaces = db.query(Workspace).join(WorkspaceMember).filter(
        WorkspaceMember.user_id == current_user.id
    ).all()
    
    # Объединяем и удаляем дубликаты
    all_workspaces = list({w.id: w for w in owned_workspaces + member_workspaces}.values())
    return all_workspaces

@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(
    workspace_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить конкретное рабочее пространство"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Проверяем, имеет ли пользователь доступ к рабочему пространству
    if workspace.owner_id != current_user.id:
        membership = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return workspace

@router.post("/", response_model=WorkspaceResponse)
def create_workspace(
    workspace_data: WorkspaceCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Создать новое рабочее пространство"""
    workspace = Workspace(
        name=workspace_data.name,
        description=workspace_data.description,
        owner_id=current_user.id
    )
    
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    
    # Добавляем владельца как участника с ролью owner
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=current_user.id,
        role="owner"
    )
    db.add(member)
    db.commit()
    
    return workspace

@router.put("/{workspace_id}", response_model=WorkspaceResponse)
def update_workspace(
    workspace_id: int,
    workspace_data: WorkspaceUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Обновить рабочее пространство"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Только владелец может обновлять рабочее пространство
    if workspace.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can update workspace")
    
    for field, value in workspace_data.dict(exclude_unset=True).items():
        setattr(workspace, field, value)
    
    db.commit()
    db.refresh(workspace)
    return workspace

@router.delete("/{workspace_id}")
def delete_workspace(
    workspace_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Удалить рабочее пространство"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Только владелец может удалять рабочее пространство
    if workspace.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can delete workspace")
    
    db.delete(workspace)
    db.commit()
    return {"message": "Workspace deleted successfully"}

@router.get("/{workspace_id}/members", response_model=List[WorkspaceUser])
def get_workspace_members(
    workspace_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить участников рабочего пространства"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Проверяем доступ
    if workspace.owner_id != current_user.id:
        membership = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="Access denied")
    
    members = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id
    ).all()
    
    result = []
    for member in members:
        user = member.user
        result.append(WorkspaceUser(
            id=user.id,
            name=user.name or "",
            email=user.email,
            role=member.role,
            joined_at=member.joined_at,
            avatar=user.avatar,
            position=user.position
        ))
    
    return result

@router.post("/{workspace_id}/email-invites")
def invite_user(
    workspace_id: int,
    invite_data: InviteUserRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Пригласить пользователя по email"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Только владелец может приглашать пользователей
    if workspace.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can invite users")
    
    # Здесь должна быть логика отправки email-приглашения
    # Пока просто возвращаем успешный ответ
    return {"message": "Email invitation sent successfully"}

@router.patch("/{workspace_id}/members/{user_id}/role")
def change_user_role(
    workspace_id: int,
    user_id: int,
    role_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Изменить роль пользователя в рабочем пространстве"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Только владелец может изменять роли
    if workspace.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can change roles")
    
    membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=404, detail="User not found in workspace")
    
    # Нельзя изменить роль владельца
    if membership.role == "owner":
        raise HTTPException(status_code=403, detail="Cannot change owner role")
    
    membership.role = role_data.get("role", membership.role)
    db.commit()
    
    return {"message": "User role updated successfully"}

@router.delete("/{workspace_id}/members/{user_id}")
def remove_user(
    workspace_id: int,
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Удалить пользователя из рабочего пространства"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Только владелец может удалять пользователей
    if workspace.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can remove users")
    
    membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=404, detail="User not found in workspace")
    
    # Нельзя удалить владельца
    if membership.role == "owner":
        raise HTTPException(status_code=403, detail="Cannot remove owner")
    
    db.delete(membership)
    db.commit()
    
    return {"message": "User removed from workspace successfully"}
