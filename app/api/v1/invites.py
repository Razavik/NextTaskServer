from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import uuid
from typing import List, Optional

from app.database.database import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.models.invite import Invite, EmailInvite
from app.schemas.invite import (
    InviteCreate, InviteResponse, EmailInviteResponse,
    InviteLinkItem, IncomingInvite
)
from app.core.security import get_current_active_user

router = APIRouter()

def generate_invite_token() -> str:
    """Генерирует уникальный токен приглашения"""
    return secrets.token_urlsafe(32)

@router.post("/workspaces/{workspace_id}/invites")
def create_workspace_invite(
    workspace_id: int,
    expires_hours: int = Query(24, ge=1, le=168),  # от 1 часа до 7 дней
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Создать приглашение по ссылке для рабочего пространства"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Только владелец может создавать приглашения
    if workspace.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can create invites")
    
    # Генерируем токен и создаем приглашение
    token = generate_invite_token()
    expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
    
    invite = Invite(
        token=token,
        workspace_id=workspace_id,
        inviter_id=current_user.id,
        role="reader",  # роль по умолчанию
        expires_at=expires_at
    )
    
    db.add(invite)
    db.commit()
    db.refresh(invite)
    
    return {
        "invite_url": f"http://localhost:5173/invite/{token}",
        "invite_token": token,
        "workspace_id": workspace_id,
        "expires_at": expires_at.isoformat()
    }

@router.get("/workspaces/{workspace_id}/invites", response_model=List[InviteLinkItem])
def get_workspace_invites(
    workspace_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить список приглашений рабочего пространства"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Только владелец может просматривать приглашения
    if workspace.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can view invites")
    
    invites = db.query(Invite).filter(Invite.workspace_id == workspace_id).all()
    return invites

@router.delete("/invites/revoke/{token}")
def revoke_invite(
    token: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Отозвать приглашение"""
    invite = db.query(Invite).filter(Invite.token == token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    # Только владелец рабочего пространства может отозвать приглашение
    workspace = db.query(Workspace).filter(Workspace.id == invite.workspace_id).first()
    if workspace.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only workspace owner can revoke invite")
    
    invite.status = "expired"
    db.commit()
    
    return {"message": "Invite revoked successfully"}

@router.post("/invites/join/{token}")
def accept_invite(
    token: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Принять приглашение"""
    invite = db.query(Invite).filter(
        Invite.token == token,
        Invite.status == "pending"
    ).first()
    
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or expired")
    
    if invite.expires_at < datetime.utcnow():
        invite.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="Invite has expired")
    
    # Проверяем, не является ли пользователь уже участником
    existing_membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == invite.workspace_id,
        WorkspaceMember.user_id == current_user.id
    ).first()
    
    if existing_membership:
        raise HTTPException(status_code=400, detail="User is already a member of this workspace")
    
    # Добавляем пользователя в рабочее пространство
    member = WorkspaceMember(
        workspace_id=invite.workspace_id,
        user_id=current_user.id,
        role=invite.role
    )
    
    db.add(member)
    
    # Обновляем статус приглашения
    invite.status = "accepted"
    invite.invitee_id = current_user.id
    invite.accepted_at = datetime.utcnow()
    
    db.commit()
    
    return {"workspace_id": invite.workspace_id}

@router.get("/invites/validate/{token}")
def validate_invite(
    token: str,
    db: Session = Depends(get_db)
):
    """Валидировать приглашение"""
    invite = db.query(Invite).filter(Invite.token == token).first()
    
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    if invite.status != "pending":
        raise HTTPException(status_code=400, detail="Invite is not active")
    
    if invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invite has expired")
    
    workspace = db.query(Workspace).filter(Workspace.id == invite.workspace_id).first()
    inviter = db.query(User).filter(User.id == invite.inviter_id).first()
    
    return {
        "workspace_id": workspace.id,
        "workspace_name": workspace.name,
        "inviter_name": inviter.name or inviter.email,
        "role": invite.role
    }

@router.get("/me/invites", response_model=List[IncomingInvite])
def get_my_invites(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить входящие приглашения текущего пользователя"""
    # Ищем email-приглашения для пользователя
    email_invites = db.query(EmailInvite).filter(
        EmailInvite.email == current_user.email,
        EmailInvite.status == "pending"
    ).all()
    
    result = []
    for email_invite in email_invites:
        workspace = db.query(Workspace).filter(Workspace.id == email_invite.workspace_id).first()
        # Здесь нужно получить информацию о приглашающем (можно добавить поле в EmailInvite)
        
        result.append(IncomingInvite(
            id=email_invite.id,
            workspace_name=workspace.name,
            inviter_name="Workspace Owner",  # временно
            role=email_invite.role,
            created_at=email_invite.created_at
        ))
    
    return result

@router.post("/invites/{invite_id}/decline")
def decline_invite(
    invite_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Отклонить приглашение"""
    email_invite = db.query(EmailInvite).filter(EmailInvite.id == invite_id).first()
    
    if not email_invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    if email_invite.email != current_user.email:
        raise HTTPException(status_code=403, detail="This invite is not for you")
    
    email_invite.status = "declined"
    db.commit()
    
    return {"message": "Invite declined successfully"}

@router.get("/workspaces/{workspace_id}/email-invites", response_model=List[EmailInviteResponse])
def get_workspace_email_invites(
    workspace_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить email-приглашения рабочего пространства"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Только владелец может просматривать email-приглашения
    if workspace.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can view email invites")
    
    email_invites = db.query(EmailInvite).filter(
        EmailInvite.workspace_id == workspace_id
    ).all()
    
    return email_invites
