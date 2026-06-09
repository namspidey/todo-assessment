import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
import redis
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession


from app.api.deps import get_current_user, get_redis
from app.core.redis import RedisClient
from app.db.session import get_db
from app.models.user import User
from app.schemas.todo import TodoCreate, TodoListResponse, TodoResponse, TodoUpdate, BulkStatusUpdate
from app.services.todo_service import (
    create_todo,
    delete_todo,
    get_todo_by_id,
    get_todos,
    update_todo,
)
from app.services.tag_service import (
    attach_tag_to_todo,
    detach_tag_from_todo,
    get_tag_by_id,
)


router = APIRouter()

CACHE_TTL = 300  # 5 minutes


@router.get("", response_model=TodoListResponse)
async def list_todos(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1),
    status: str | None = Query(None, description="Filter by status: active or completed"),
    tag_id: uuid.UUID | None = Query(None),
    keyword: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Get paginated list of todos with optional filtering."""
    skip = (page - 1) * size

    # Scope cache key by user + all filter params
    cache_key = (
        f"todos:{current_user.id}:page:{page}:size:{size}"
        f":status:{status}:tag:{tag_id}:kw:{keyword}"
        f":from:{date_from}:to:{date_to}"
    )

    # Try to get from cache
    cached = await redis.get(cache_key)
    if cached:
        cached_data = json.loads(cached)
        return TodoListResponse(**cached_data)

    todos, total = await get_todos(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=size,
        status=status,
        tag_id=tag_id,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
    )

    items = [
        TodoResponse(
            id=todo.id,
            title=todo.title,
            description=todo.description,
            completed=todo.completed,
            user_id=todo.user_id,
            created_at=todo.created_at,
            updated_at=todo.updated_at,
            user_email=None,
        )
        for todo in todos
    ]

    response = TodoListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
    )

    # Cache the response
    await redis.set(cache_key, response.model_dump_json(), ex=CACHE_TTL)

    return response


@router.post("", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
async def create_new_todo(
    todo_data: TodoCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Create a new todo item."""
    todo = await create_todo(db, todo_data, current_user.id)
    # Invalidate user's todo list cache after creating a new todo
    await redis.delete(f"todos:{current_user.id}:page:1:size:20")
    return todo


@router.get("/{todo_id}", response_model=TodoResponse)
async def get_todo(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific todo by ID."""
    todo = await get_todo_by_id(db, todo_id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )
    # Ensure the todo belongs to the current user
    if todo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    
    return todo


@router.put("/{todo_id}", response_model=TodoResponse)
async def update_existing_todo(
    todo_id: uuid.UUID,
    todo_data: TodoUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Update a todo item."""
    todo = await get_todo_by_id(db, todo_id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )
    # Ensure the todo belongs to the current user
    if todo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    
    update_data = todo_data.model_dump()

    # Use "is not None" to allow setting completed=False (uncomplete a todo)
    if todo_data.completed is not None:
        todo.completed = todo_data.completed

    # Apply other updates
    if update_data.get("title") is not None:
        todo.title = update_data["title"]
    if "description" in update_data:
        todo.description = update_data["description"]

    updated_todo = await update_todo(db, todo, {})

    # Invalidate user's todo list cache after updating a todo
    await redis.delete(f"todos:{current_user.id}:page:1:size:20")

    return updated_todo


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_todo(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Delete a todo item."""
    todo = await get_todo_by_id(db, todo_id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )
    # Ensure the todo belongs to the current user
    if todo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    
    await delete_todo(db, todo)

    # Invalidate user's todo list cache after deleting a todo
    await redis.delete(f"todos:{current_user.id}:page:1:size:20")

    return None

@router.post("/{todo_id}/tags", status_code=status.HTTP_201_CREATED)
async def attach_tag_to_todo_endpoint(
    todo_id: uuid.UUID,
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Attach a tag to a todo."""
    todo = await get_todo_by_id(db, todo_id)
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    if todo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    tag = await get_tag_by_id(db, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    # Ensure user can only attach their own tags to their own todos
    if tag.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    await attach_tag_to_todo(db, todo, tag)

    # Invalidate cache after tag mapping
    await redis.delete(f"todos:{current_user.id}:page:1:size:20")
    return {"message": "Tag attached successfully"}


@router.delete("/{todo_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_tag_from_todo_endpoint(
    todo_id: uuid.UUID,
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Detach a tag from a todo."""
    todo = await get_todo_by_id(db, todo_id)
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    if todo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    removed = await detach_tag_from_todo(db, todo_id, tag_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not attached to this todo",
        )

    # Invalidate cache after tag removal
    await redis.delete(f"todos:{current_user.id}:page:1:size:20")
    return None


@router.patch("/bulk-status", response_model=list[TodoResponse])
async def bulk_update_status(
    payload: BulkStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Bulk update todo completion status."""
    from sqlalchemy import update as sql_update
    from app.models.todo import Todo as TodoModel

    # Verify all todos belong to current user
    result = await db.execute(
        select(TodoModel).where(
            and_(
                TodoModel.id.in_(payload.todo_ids),
                TodoModel.user_id == current_user.id,
            )
        )
    )
    todos = list(result.scalars().all())

    if len(todos) != len(payload.todo_ids):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Some todos do not belong to you",
        )

    # Bulk update in a transaction
    await db.execute(
        sql_update(TodoModel)
        .where(
            and_(
                TodoModel.id.in_(payload.todo_ids),
                TodoModel.user_id == current_user.id,
            )
        )
        .values(completed=payload.completed)
    )
    await db.flush()

    # Invalidate cache after bulk update
    await redis.delete(f"todos:{current_user.id}:page:1:size:20")

    # Return updated todos
    result = await db.execute(
        select(TodoModel).where(TodoModel.id.in_(payload.todo_ids))
    )
    return list(result.scalars().all())