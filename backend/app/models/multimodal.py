"""Owner/version-scoped visual assets, durable extraction and cleanup records."""

from datetime import datetime

from sqlalchemy import (
    DDL,
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class DocumentAsset(Base):
    __tablename__ = "document_assets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["documents.id", "documents.user_id"],
            name="fk_document_assets_document_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "user_id", name="uq_document_assets_id_owner"),
        UniqueConstraint("storage_key", name="uq_document_assets_storage"),
        CheckConstraint(
            "asset_type IN ('figure','chart','diagram','table','equation')",
            name="ck_document_assets_type",
        ),
        CheckConstraint(
            "page_number > 0 AND document_version > 0",
            name="ck_document_assets_version_page",
        ),
        Index(
            "ix_document_assets_owner_document_page",
            "user_id",
            "document_id",
            "page_number",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    document_version: Mapped[int]
    extraction_generation: Mapped[int]
    asset_type: Mapped[str] = mapped_column(String(12))
    asset_label: Mapped[str | None] = mapped_column(String(200))
    page_number: Mapped[int]
    caption: Mapped[str | None] = mapped_column(Text)
    extracted_text_or_latex: Mapped[str | None] = mapped_column(Text)
    structured_data: Mapped[dict | None] = mapped_column(JSON)
    storage_key: Mapped[str | None] = mapped_column(String(80))
    image_size_bytes: Mapped[int | None]
    linked_chunk_ids: Mapped[list[int]] = mapped_column(JSON)
    ai_explanation: Mapped[str | None] = mapped_column(Text)
    explanations: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AssetChunkLink(Base):
    __tablename__ = "asset_chunk_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["asset_id", "user_id"],
            ["document_assets.id", "document_assets.user_id"],
            name="fk_asset_chunk_links_asset_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["chunk_id", "user_id"],
            ["document_chunks.id", "document_chunks.user_id"],
            name="fk_asset_chunk_links_chunk_owner",
            ondelete="CASCADE",
        ),
    )
    asset_id: Mapped[int] = mapped_column(primary_key=True)
    chunk_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(primary_key=True)


class AssetExtractionJob(Base):
    __tablename__ = "asset_extraction_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["documents.id", "documents.user_id"],
            name="fk_asset_jobs_document_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint("document_id", name="uq_asset_jobs_document"),
        CheckConstraint(
            "status IN ('queued','running','completed','failed')",
            name="ck_asset_jobs_status",
        ),
        CheckConstraint(
            "generation > 0 AND document_version > 0 AND attempts >= 0",
            name="ck_asset_jobs_counts",
        ),
        Index("ix_asset_jobs_owner_status", "user_id", "status", "created_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    document_version: Mapped[int]
    generation: Mapped[int] = mapped_column(default=1)
    attempts: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(12), default="queued")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssetDeletion(Base):
    __tablename__ = "asset_deletions"
    user_id: Mapped[int] = mapped_column(primary_key=True)
    storage_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# SQLite isolated tests mirror the production PostgreSQL deletion outbox trigger.
event.listen(
    Base.metadata,
    "after_create",
    DDL("""
CREATE TRIGGER IF NOT EXISTS document_asset_delete_queue AFTER DELETE ON document_assets
WHEN OLD.storage_key IS NOT NULL BEGIN
INSERT OR IGNORE INTO asset_deletions (user_id, storage_key)
VALUES (OLD.user_id, OLD.storage_key);
END
""").execute_if(dialect="sqlite"),
)
