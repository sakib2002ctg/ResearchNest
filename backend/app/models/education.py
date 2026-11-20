"""Private progress through the curated research education catalog."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class LearningProgress(Base):
    __tablename__ = "learning_progress"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        UniqueConstraint(
            "user_id", "guide_slug", name="uq_learning_progress_owner_guide"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    guide_slug: Mapped[str] = mapped_column(String(100), index=True)
    completed_step_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_completed: Mapped[bool] = mapped_column(default=False, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
