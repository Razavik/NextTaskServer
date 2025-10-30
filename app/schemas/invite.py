from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class InviteBase(BaseModel):
    role: str

class InviteCreate(InviteBase):
    workspace_id: int
    email: Optional[str] = None
    expires_hours: Optional[int] = 24

class InviteResponse(BaseModel):
    id: int
    token: str
    workspace_id: int
    inviter_id: int
    invitee_id: Optional[int] = None
    email: Optional[str] = None
    role: str
    status: str
    expires_at: datetime
    created_at: datetime
    accepted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class EmailInviteResponse(BaseModel):
    id: int
    workspace_id: int
    email: str
    role: str
    status: str
    token: str
    expires_at: datetime
    created_at: datetime
    sent_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class InviteLinkItem(BaseModel):
    id: int
    token: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True

class IncomingInvite(BaseModel):
    id: int
    workspace_name: str
    inviter_name: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True
