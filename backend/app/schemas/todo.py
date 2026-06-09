import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class TodoUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    completed: bool | None = None


class TagInTodo(BaseModel):
    """Minimal tag info embedded in todo response."""
    id: uuid.UUID
    name: str
    color: str | None

    model_config = {"from_attributes": True}


class TodoResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    completed: bool
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    user_email: str | None = None
    tags: list[TagInTodo] = []

    model_config = {"from_attributes": True}


class TodoListResponse(BaseModel):
    items: list[TodoResponse]
    total: int
    page: int
    size: int


class BulkStatusUpdate(BaseModel):
    """Payload for bulk updating todo status."""
    todo_ids: list[uuid.UUID] = Field(..., min_length=1)
    completed: bool