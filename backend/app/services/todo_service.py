import uuid
from datetime import datetime

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tag import TodoTag
from app.models.todo import Todo
from app.schemas.todo import TodoCreate


async def create_todo(
    db: AsyncSession, todo_data: TodoCreate, user_id: uuid.UUID
) -> Todo:
    todo = Todo(
        title=todo_data.title,
        description=todo_data.description,
        user_id=user_id,
    )
    db.add(todo)
    await db.flush()
    await db.refresh(todo)
    return todo


async def get_todos(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
    tag_id: uuid.UUID | None = None,
    keyword: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[Todo], int]:
    """Get todos with filtering and pagination for a specific user."""
    filters = [Todo.user_id == user_id]

    # Filter by status
    if status == "completed":
        filters.append(Todo.completed == True)  # noqa: E712
    elif status == "active":
        filters.append(Todo.completed == False)  # noqa: E712

    # Filter by keyword (title search)
    if keyword:
        filters.append(Todo.title.ilike(f"%{keyword}%"))

    # Filter by date range
    if date_from:
        filters.append(Todo.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        filters.append(Todo.created_at <= datetime.fromisoformat(date_to))

    # Filter by tag
    if tag_id:
        filters.append(
            Todo.id.in_(
                select(TodoTag.todo_id).where(TodoTag.tag_id == tag_id)
            )
        )

    query = (
        select(Todo)
        .where(and_(*filters))
        # Order by completed asc (incomplete first), then created_at desc (newest first)
        .order_by(Todo.completed.asc(), Todo.created_at.desc())
        .offset(skip)
        .limit(limit)
        .options(selectinload(Todo.tags))
    )
    result = await db.execute(query)
    todos = list(result.scalars().all())

    count_query = (
        select(func.count())
        .select_from(Todo)
        .where(and_(*filters))
    )
    total = await db.execute(count_query)

    return todos, total.scalar_one()


async def get_todo_by_id(db: AsyncSession, todo_id: uuid.UUID) -> Todo | None:
    result = await db.execute(
        select(Todo)
        .where(Todo.id == todo_id)
        .options(selectinload(Todo.tags))
    )
    return result.scalar_one_or_none()


async def update_todo(db: AsyncSession, todo: Todo, update_data: dict) -> Todo:
    for key, value in update_data.items():
        setattr(todo, key, value)
    await db.flush()
    await db.refresh(todo)
    return todo


async def delete_todo(db: AsyncSession, todo: Todo) -> None:
    await db.delete(todo)
    await db.flush()