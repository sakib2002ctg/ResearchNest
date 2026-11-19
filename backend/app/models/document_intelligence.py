"""Versioned, tenant-scoped document intelligence records."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.database.database import Base
from app.models.library import Document

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # portable SQLite-only install without the optional pgvector extra
    Vector = None

_VECTOR = (
    Vector(384).with_variant(JSON(), "sqlite")
    if settings.PGVECTOR_ENABLED and Vector is not None
    else JSON()
)


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (
        ForeignKeyConstraint(
            ("document_id", "user_id"),
            ("documents.id", "documents.user_id"),
            name="fk_document_pages_document_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "document_id",
            "document_version",
            "page_number",
            name="uq_document_pages_version_page",
        ),
        CheckConstraint("page_number > 0", name="ck_document_pages_page_number"),
        CheckConstraint("document_version > 0", name="ck_document_pages_version"),
        Index("ix_document_pages_document_page", "document_id", "page_number"),
        Index("ix_document_pages_owner", "user_id", "document_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ocr_used: Mapped[bool] = mapped_column(
        default=False, server_default="false", nullable=False
    )
    section_heading: Mapped[str | None] = mapped_column(Text)
    document: Mapped[Document] = relationship(back_populates="pages")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ("document_id", "user_id"),
            ("documents.id", "documents.user_id"),
            name="fk_document_chunks_document_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "document_id",
            "document_version",
            "page_number",
            "chunk_index",
            name="uq_document_chunks_version_page_index",
        ),
        UniqueConstraint("id", "user_id", name="uq_document_chunks_id_user_id"),
        CheckConstraint("page_number > 0", name="ck_document_chunks_page_number"),
        CheckConstraint("chunk_index >= 0", name="ck_document_chunks_index"),
        CheckConstraint("document_version > 0", name="ck_document_chunks_version"),
        CheckConstraint("token_count >= 0", name="ck_document_chunks_tokens"),
        Index("ix_document_chunks_owner_document", "user_id", "document_id"),
        Index(
            "ix_document_chunks_owner_page",
            "user_id",
            "document_id",
            "page_number",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_heading: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    document: Mapped[Document] = relationship(back_populates="chunks")
    embedding: Mapped["Embedding | None"] = relationship(
        back_populates="chunk", uselist=False, cascade="all, delete-orphan"
    )


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        ForeignKeyConstraint(
            ("chunk_id", "user_id"),
            ("document_chunks.id", "document_chunks.user_id"),
            name="fk_embeddings_chunk_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint("chunk_id", name="uq_embeddings_chunk"),
        CheckConstraint("document_version > 0", name="ck_embeddings_version"),
        Index("ix_embeddings_owner", "user_id", "model_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chunk_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    vector_json: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    vector_pg: Mapped[list[float] | None] = mapped_column(_VECTOR)
    chunk: Mapped[DocumentChunk] = relationship(back_populates="embedding")


if settings.PGVECTOR_ENABLED and Vector is not None:
    Index(
        "ix_embeddings_vector_hnsw",
        Embedding.vector_pg,
        postgresql_using="hnsw",
        postgresql_ops={"vector_pg": "vector_cosine_ops"},
    ).ddl_if(dialect="postgresql")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ("document_id", "user_id"),
            ("documents.id", "documents.user_id"),
            name="fk_processing_jobs_document_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "document_id",
            "document_version",
            "job_type",
            name="uq_processing_jobs_document_version_type",
        ),
        CheckConstraint(
            "job_type IN ('pdf_extract_and_index')",
            name="ck_processing_jobs_type",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_processing_jobs_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_processing_jobs_attempts"),
        CheckConstraint("document_version > 0", name="ck_processing_jobs_version"),
        Index("ix_processing_jobs_owner_status", "user_id", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    job_type: Mapped[str] = mapped_column(
        String(64),
        default="pdf_extract_and_index",
        server_default="pdf_extract_and_index",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16), default="queued", server_default="queued", nullable=False
    )
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    document: Mapped[Document] = relationship(back_populates="processing_jobs")
