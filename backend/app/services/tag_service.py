import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag, TodoTag
from app.models.todo import Todo
from app.schemas.tag import TagCreate, TagUpdate


async def get_tags(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> tuple[list[Tag], int]:
    """Get all tags for a specific user."""
    query = select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)
    result = await db.execute(query)
    tags = list(result.scalars().all())

    count_query = select(func.count()).select_from(Tag).where(Tag.user_id == user_id)
    total = await db.execute(count_query)

    return tags, total.scalar_one()


async def get_tag_by_id(
    db: AsyncSession,
    tag_id: uuid.UUID,
) -> Tag | None:
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    return result.scalar_one_or_none()


async def get_tag_by_name(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
) -> Tag | None:
    """Get tag by name (case-insensitive) for a specific user."""
    result = await db.execute(
        select(Tag).where(
            Tag.user_id == user_id,
            func.lower(Tag.name) == name.lower(),
        )
    )
    return result.scalar_one_or_none()


async def create_tag(
    db: AsyncSession,
    tag_data: TagCreate,
    user_id: uuid.UUID,
) -> Tag:
    tag = Tag(
        name=tag_data.name,
        color=tag_data.color,
        user_id=user_id,
    )
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    return tag


async def update_tag(
    db: AsyncSession,
    tag: Tag,
    tag_data: TagUpdate,
) -> Tag:
    if tag_data.name is not None:
        tag.name = tag_data.name
    if tag_data.color is not None:
        tag.color = tag_data.color
    await db.flush()
    await db.refresh(tag)
    return tag


async def delete_tag(db: AsyncSession, tag: Tag) -> None:
    """Delete tag and its todo-tag relations (cascade)."""
    await db.delete(tag)
    await db.flush()


async def attach_tag_to_todo(
    db: AsyncSession,
    todo: Todo,
    tag: Tag,
) -> None:
    """Attach a tag to a todo."""
    # Check if already attached
    existing = await db.execute(
        select(TodoTag).where(
            TodoTag.todo_id == todo.id,
            TodoTag.tag_id == tag.id,
        )
    )
    if existing.scalar_one_or_none():
        return

    todo_tag = TodoTag(todo_id=todo.id, tag_id=tag.id)
    db.add(todo_tag)
    await db.flush()


async def detach_tag_from_todo(
    db: AsyncSession,
    todo_id: uuid.UUID,
    tag_id: uuid.UUID,
) -> bool:
    """Detach a tag from a todo. Returns False if not found."""
    result = await db.execute(
        select(TodoTag).where(
            TodoTag.todo_id == todo_id,
            TodoTag.tag_id == tag_id,
        )
    )
    todo_tag = result.scalar_one_or_none()
    if not todo_tag:
        return False
    await db.delete(todo_tag)
    await db.flush()
    return True