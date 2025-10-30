from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class MessageBase(BaseModel):
    content: str

class MessageCreate(MessageBase):
    receiver_id: int

class MessageResponse(MessageBase):
    id: int
    sender_id: int
    receiver_id: int
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class WorkspaceMessageBase(BaseModel):
    content: str

class WorkspaceMessageCreate(WorkspaceMessageBase):
    pass

class WorkspaceMessageResponse(WorkspaceMessageBase):
    id: int
    workspace_id: int
    sender_id: int
    created_at: datetime
    sender: Optional[dict] = None

    class Config:
        from_attributes = True

class RecentChat(BaseModel):
    id: str
    type: str  # "personal" или "workspace"
    userId: Optional[int] = None
    workspaceId: Optional[int] = None
    name: str
    avatar: Optional[str] = None
    lastActivityAt: Optional[datetime] = None
