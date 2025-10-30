from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Set
import json
import asyncio
from datetime import datetime

from app.database.database import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.models.message import Message, WorkspaceMessage
from app.schemas.message import MessageResponse, WorkspaceMessageResponse, RecentChat
from app.core.security import get_current_active_user, verify_token

router = APIRouter()

# Хранилище активных WebSocket соединений
class ConnectionManager:
    def __init__(self):
        self.personal_connections: Dict[int, WebSocket] = {}  # user_id -> websocket
        self.workspace_connections: Dict[int, Dict[int, WebSocket]] = {}  # workspace_id -> {user_id -> websocket}
    
    async def connect_personal(self, user_id: int, websocket: WebSocket):
        """Подключить личный чат"""
        self.personal_connections[user_id] = websocket
    
    async def disconnect_personal(self, user_id: int):
        """Отключить личный чат"""
        if user_id in self.personal_connections:
            del self.personal_connections[user_id]
    
    async def connect_workspace(self, workspace_id: int, user_id: int, websocket: WebSocket):
        """Подключить к групповому чату"""
        if workspace_id not in self.workspace_connections:
            self.workspace_connections[workspace_id] = {}
        self.workspace_connections[workspace_id][user_id] = websocket
    
    async def disconnect_workspace(self, workspace_id: int, user_id: int):
        """Отключить от группового чата"""
        if workspace_id in self.workspace_connections:
            if user_id in self.workspace_connections[workspace_id]:
                del self.workspace_connections[workspace_id][user_id]
            if not self.workspace_connections[workspace_id]:
                del self.workspace_connections[workspace_id]
    
    async def send_personal_message(self, message: dict, receiver_id: int):
        """Отправить личное сообщение"""
        if receiver_id in self.personal_connections:
            websocket = self.personal_connections[receiver_id]
            try:
                await websocket.send_text(json.dumps(message))
            except:
                # Соединение закрыто, удаляем
                await self.disconnect_personal(receiver_id)
    
    async def broadcast_to_workspace(self, message: dict, workspace_id: int, sender_id: int):
        """Отправить сообщение всем в рабочем пространстве, кроме отправителя"""
        if workspace_id in self.workspace_connections:
            for user_id, websocket in self.workspace_connections[workspace_id].items():
                if user_id != sender_id:  # Не отправляем отправителю
                    try:
                        await websocket.send_text(json.dumps(message))
                    except:
                        # Соединение закрыто, удаляем
                        await self.disconnect_workspace(workspace_id, user_id)

manager = ConnectionManager()

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

@router.websocket("/ws")
async def websocket_personal_chat(websocket: WebSocket, token: str = Query(...)):
    """WebSocket для личного чата"""
    await websocket.accept()
    
    try:
        # Проверяем токен
        email = verify_token(token)
        if not email:
            await websocket.close(code=1008, reason="Invalid token")
            return
        
        # Получаем пользователя
        from app.database.database import SessionLocal
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                await websocket.close(code=1008, reason="User not found")
                return
            
            # Подключаем пользователя
            await manager.connect_personal(user.id, websocket)
            
            try:
                while True:
                    data = await websocket.receive_text()
                    message_data = json.loads(data)
                    
                    # Сохраняем сообщение в базу данных
                    message = Message(
                        content=message_data["content"],
                        sender_id=user.id,
                        receiver_id=message_data["receiver_id"]
                    )
                    db.add(message)
                    db.commit()
                    db.refresh(message)
                    
                    # Формируем ответ
                    response = {
                        "id": message.id,
                        "content": message.content,
                        "sender_id": message.sender_id,
                        "receiver_id": message.receiver_id,
                        "is_read": message.is_read,
                        "created_at": message.created_at.isoformat(),
                        "sender": {
                            "id": user.id,
                            "name": user.name,
                            "email": user.email,
                            "avatar": user.avatar
                        }
                    }
                    
                    # Отправляем получателю
                    await manager.send_personal_message(response, message.receiver_id)
                    
            except WebSocketDisconnect:
                pass
            finally:
                await manager.disconnect_personal(user.id)
                
        finally:
            db.close()
            
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))

@router.websocket("/ws/{workspace_id}")
async def websocket_workspace_chat(websocket: WebSocket, workspace_id: int, token: str = Query(...)):
    """WebSocket для группового чата рабочего пространства"""
    await websocket.accept()
    
    try:
        # Проверяем токен
        email = verify_token(token)
        if not email:
            await websocket.close(code=1008, reason="Invalid token")
            return
        
        # Получаем пользователя и проверяем доступ
        from app.database.database import SessionLocal
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                await websocket.close(code=1008, reason="User not found")
                return
            
            # Проверяем доступ к рабочему пространству
            workspace = check_workspace_access(workspace_id, user, db)
            
            # Подключаем пользователя к чату
            await manager.connect_workspace(workspace_id, user.id, websocket)
            
            try:
                while True:
                    data = await websocket.receive_text()
                    message_data = json.loads(data)
                    
                    # Сохраняем сообщение в базу данных
                    message = WorkspaceMessage(
                        content=message_data["content"],
                        workspace_id=workspace_id,
                        sender_id=user.id
                    )
                    db.add(message)
                    db.commit()
                    db.refresh(message)
                    
                    # Формируем ответ
                    response = {
                        "id": message.id,
                        "content": message.content,
                        "workspace_id": message.workspace_id,
                        "sender_id": message.sender_id,
                        "created_at": message.created_at.isoformat(),
                        "sender": {
                            "id": user.id,
                            "name": user.name,
                            "email": user.email,
                            "avatar": user.avatar
                        }
                    }
                    
                    # Отправляем всем участникам рабочего пространства
                    await manager.broadcast_to_workspace(response, workspace_id, user.id)
                    
            except WebSocketDisconnect:
                pass
            finally:
                await manager.disconnect_workspace(workspace_id, user.id)
                
        finally:
            db.close()
            
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))

@router.get("/messages/{user_id}", response_model=List[MessageResponse])
def get_chat_history(
    user_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить историю личных сообщений с пользователем"""
    messages = db.query(Message).filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.desc()).offset(offset).limit(limit).all()
    
    return messages

@router.patch("/messages/{message_id}/read", response_model=MessageResponse)
def mark_message_as_read(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Отметить сообщение как прочитанное"""
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Только получатель может отметить сообщение как прочитанное
    if message.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only receiver can mark message as read")
    
    message.is_read = True
    message.read_at = datetime.utcnow()
    db.commit()
    db.refresh(message)
    
    return message

@router.get("/unread-count")
def get_unread_count(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить количество непрочитанных сообщений"""
    count = db.query(Message).filter(
        Message.receiver_id == current_user.id,
        Message.is_read == False
    ).count()
    
    return count

@router.get("/messages/workspace/{workspace_id}", response_model=List[WorkspaceMessageResponse])
def get_workspace_chat_history(
    workspace_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить историю группового чата"""
    # Проверяем доступ
    workspace = check_workspace_access(workspace_id, current_user, db)
    
    messages = db.query(WorkspaceMessage).filter(
        WorkspaceMessage.workspace_id == workspace_id
    ).order_by(WorkspaceMessage.created_at.desc()).offset(offset).limit(limit).all()
    
    return messages

@router.get("/recent", response_model=List[RecentChat])
def get_recent_chats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить список недавних чатов"""
    recent_chats = []
    
    # Получаем недавние личные сообщения
    personal_messages = db.query(Message).filter(
        (Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id)
    ).order_by(Message.created_at.desc()).limit(10).all()
    
    for msg in personal_messages:
        other_user_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        other_user = db.query(User).filter(User.id == other_user_id).first()
        
        if other_user:
            recent_chats.append(RecentChat(
                id=f"personal_{other_user_id}",
                type="personal",
                userId=other_user_id,
                name=other_user.name or other_user.email,
                avatar=other_user.avatar,
                lastActivityAt=msg.created_at
            ))
    
    # Получаем рабочие пространства пользователя
    user_workspaces = db.query(Workspace).filter(Workspace.owner_id == current_user.id).all()
    member_workspaces = db.query(Workspace).join(WorkspaceMember).filter(
        WorkspaceMember.user_id == current_user.id
    ).all()
    
    all_workspaces = list({w.id: w for w in user_workspaces + member_workspaces}.values())
    
    for workspace in all_workspaces:
        recent_chats.append(RecentChat(
            id=f"workspace_{workspace.id}",
            type="workspace",
            workspaceId=workspace.id,
            name=workspace.name,
            lastActivityAt=None  # Можно добавить последнее сообщение из группового чата
        ))
    
    # Сортируем по времени активности
    recent_chats.sort(key=lambda x: x.lastActivityAt or datetime.min, reverse=True)
    
    return recent_chats[:20]  # Ограничиваем количество
