from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.schemas.user import UserResponse

class CommentBase(BaseModel):
    content: str

class CommentCreate(CommentBase):
    task_id: int

class CommentUpdate(BaseModel):
    content: str

class CommentResponse(CommentBase):
    id: int
    task_id: int
    author_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    author: UserResponse

    class Config:
        from_attributes = True

class CommentsQuery(BaseModel):
    limit: Optional[int] = 50
    offset: Optional[int] = 0
    order: Optional[str] = "desc"
