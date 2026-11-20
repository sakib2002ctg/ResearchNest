"""Explicit team ACLs; sharing never transfers a private library's ownership."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class TeamWorkspace(Base):
    __tablename__ = "team_workspaces"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        UniqueConstraint("id", "owner_id", name="uq_team_workspaces_id_owner"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_team_members_pair"),
        CheckConstraint(
            "role IN ('owner','editor','viewer')", name="ck_team_members_role"
        ),
        CheckConstraint(
            "(role = 'owner' AND owner_user_id IS NOT NULL "
            "AND owner_user_id = user_id) "
            "OR (role <> 'owner' AND owner_user_id IS NULL)",
            name="ck_team_members_owner_identity",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "owner_user_id"],
            ["team_workspaces.id", "team_workspaces.owner_id"],
            name="fk_team_members_owner_identity",
            ondelete="CASCADE",
        ),
        Index(
            "uq_team_members_one_owner",
            "workspace_id",
            unique=True,
            postgresql_where=text("role = 'owner'"),
            sqlite_where=text("role = 'owner'"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("team_workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(10))
    # Non-owner rows keep this NULL. A compound FK makes a forged owner role
    # impossible even outside application services.
    owner_user_id: Mapped[int | None]
    invited_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TeamSharedCollection(Base):
    __tablename__ = "team_shared_collections"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "collection_id", name="uq_team_shared_collection"
        ),
        ForeignKeyConstraint(
            ["shared_by_id", "collection_id"],
            ["collections.user_id", "collections.id"],
            name="fk_team_shared_collection_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "shared_by_id"],
            ["team_members.workspace_id", "team_members.user_id"],
            name="fk_team_shared_collection_member",
            ondelete="CASCADE",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("team_workspaces.id", ondelete="CASCADE"), index=True
    )
    collection_id: Mapped[int] = mapped_column(index=True)
    shared_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    shared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TeamNote(Base):
    __tablename__ = "team_notes"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        Index("ix_team_notes_workspace_created", "workspace_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("team_workspaces.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
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
