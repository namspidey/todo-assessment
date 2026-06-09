import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.todo import Todo


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    color: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Case-insensitive unique tag name per user (enforced at DB level)
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_tag_user_name"),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="tags")
    todos: Mapped[list["Todo"]] = relationship(
        "Todo",
        secondary="todo_tags",
        back_populates="tags",
    )

    def __repr__(self) -> str:
        return f"<Tag {self.name}>"


class TodoTag(Base):
    __tablename__ = "todo_tags"

    todo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("todos.id"),
        primary_key=True,
        index=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tags.id"),
        primary_key=True,
        index=True,
    )