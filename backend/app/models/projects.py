"""Private research workspaces and owner-bound project associations."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class ResearchProject(Base):
    __tablename__ = "research_projects"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_research_projects_id_owner"),
        ForeignKeyConstraint(
            ["user_id", "collection_id"],
            ["collections.user_id", "collections.id"],
            name="fk_research_projects_collection_owner",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "status IN ('planning','active','review','completed','archived')",
            name="ck_research_projects_status",
        ),
        CheckConstraint(
            "progress_percent BETWEEN 0 AND 100 AND revision >= 1",
            name="ck_research_projects_progress_revision",
        ),
        Index("ix_research_projects_owner_updated", "user_id", "updated_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    objectives: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(
        String(16), default="planning", server_default="planning"
    )
    progress_percent: Mapped[float] = mapped_column(
        Float, default=0, server_default="0"
    )
    revision: Mapped[int] = mapped_column(default=1, server_default="1")
    target_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collection_id: Mapped[int | None] = mapped_column(
        ForeignKey("collections.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProjectPaper(Base):
    __tablename__ = "project_papers"
    __table_args__ = (
        UniqueConstraint("project_id", "user_paper_id", name="uq_project_papers_pair"),
        ForeignKeyConstraint(
            ["project_id", "user_id"],
            ["research_projects.id", "research_projects.user_id"],
            name="fk_project_papers_project_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["user_id", "user_paper_id"],
            ["user_papers.user_id", "user_papers.id"],
            name="fk_project_papers_paper_owner",
            ondelete="CASCADE",
        ),
        Index("ix_project_papers_owner_project", "user_id", "project_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    project_id: Mapped[int] = mapped_column(index=True)
    user_paper_id: Mapped[int] = mapped_column(index=True)
    role_in_project: Mapped[str | None] = mapped_column(String(100))
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ResearchNote(Base):
    __tablename__ = "research_notes"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "user_id"],
            ["research_projects.id", "research_projects.user_id"],
            name="fk_research_notes_project_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["user_id", "user_paper_id"],
            ["user_papers.user_id", "user_papers.id"],
            name="fk_research_notes_paper_owner",
            deferrable=True,
            initially="DEFERRED",
        ),
        Index("ix_research_notes_owner_project", "user_id", "project_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    project_id: Mapped[int] = mapped_column(index=True)
    user_paper_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_papers.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProjectTask(Base):
    __tablename__ = "project_tasks"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "user_id"],
            ["research_projects.id", "research_projects.user_id"],
            name="fk_project_tasks_project_owner",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('todo','in_progress','done')", name="ck_project_tasks_status"
        ),
        CheckConstraint(
            "(status = 'done' AND completed_at IS NOT NULL) OR "
            "(status <> 'done' AND completed_at IS NULL)",
            name="ck_project_tasks_completion",
        ),
        Index("ix_project_tasks_owner_project", "user_id", "project_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    project_id: Mapped[int] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    is_milestone: Mapped[bool] = mapped_column(default=False, server_default="false")
    status: Mapped[str] = mapped_column(
        String(16), default="todo", server_default="todo"
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
