"""Private references, authored drafts, and immutable numbered snapshots."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
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


class Citation(Base):
    __tablename__ = "citations"
    __table_args__ = (
        UniqueConstraint("user_id", "cite_key", name="uq_citations_owner_key"),
        UniqueConstraint("user_id", "identity_key", name="uq_citations_owner_identity"),
        UniqueConstraint("id", "user_id", name="uq_citations_id_owner"),
        ForeignKeyConstraint(
            ["user_id", "user_paper_id"],
            ["user_papers.user_id", "user_papers.id"],
            name="fk_citations_library_owner",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "entry_type IN ('article','inproceedings','book','misc','preprint')",
            name="ck_citations_entry_type",
        ),
        CheckConstraint(
            "year IS NULL OR (year >= 1000 AND year <= 2200)", name="ck_citations_year"
        ),
        Index("ix_citations_owner_title_year", "user_id", "title_year_key"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    user_paper_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_papers.id", ondelete="SET NULL")
    )
    cite_key: Mapped[str] = mapped_column(String(100))
    identity_key: Mapped[str] = mapped_column(String(64))
    title_year_key: Mapped[str] = mapped_column(String(64))
    entry_type: Mapped[str] = mapped_column(String(20), default="article")
    title: Mapped[str] = mapped_column(String(1000))
    authors: Mapped[list[str]] = mapped_column(JSON)
    year: Mapped[int | None]
    venue: Mapped[str | None] = mapped_column(String(500))
    volume: Mapped[str | None] = mapped_column(String(100))
    issue: Mapped[str | None] = mapped_column(String(100))
    pages: Mapped[str | None] = mapped_column(String(100))
    doi: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(2048))
    publisher: Mapped[str | None] = mapped_column(String(500))
    is_verified: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WritingDocument(Base):
    __tablename__ = "writing_documents"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_writing_documents_id_owner"),
        CheckConstraint(
            "doc_type IN "
            "('research_paper','research_proposal','thesis','literature_review')",
            name="ck_writing_documents_type",
        ),
        CheckConstraint(
            "language IN ('en','bn')", name="ck_writing_documents_language"
        ),
        CheckConstraint(
            "word_count >= 0 AND revision >= 1", name="ck_writing_documents_counts"
        ),
        Index("ix_writing_documents_owner_updated", "user_id", "updated_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    doc_type: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(300))
    language: Mapped[str] = mapped_column(String(2), default="en")
    outline: Mapped[list[str]] = mapped_column(JSON)
    content_markdown: Mapped[str] = mapped_column(Text, default="", server_default="")
    cited_citation_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    ai_suggestions_log: Mapped[list[dict]] = mapped_column(JSON, default=list)
    word_count: Mapped[int] = mapped_column(default=0, server_default="0")
    revision: Mapped[int] = mapped_column(default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WritingVersion(Base):
    __tablename__ = "writing_versions"
    __table_args__ = (
        UniqueConstraint(
            "writing_document_id", "version_number", name="uq_writing_versions_number"
        ),
        ForeignKeyConstraint(
            ["writing_document_id", "user_id"],
            ["writing_documents.id", "writing_documents.user_id"],
            name="fk_writing_versions_document_owner",
            ondelete="CASCADE",
        ),
        CheckConstraint("version_number > 0", name="ck_writing_versions_number"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    writing_document_id: Mapped[int] = mapped_column(
        ForeignKey("writing_documents.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int]
    title: Mapped[str] = mapped_column(String(300))
    content_markdown: Mapped[str] = mapped_column(Text)
    outline: Mapped[list[str]] = mapped_column(JSON)
    cited_citation_ids: Mapped[list[int]] = mapped_column(JSON)
    change_summary: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WritingCitation(Base):
    __tablename__ = "writing_citations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["writing_document_id", "user_id"],
            ["writing_documents.id", "writing_documents.user_id"],
            name="fk_writing_citations_document_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["citation_id", "user_id"],
            ["citations.id", "citations.user_id"],
            name="fk_writing_citations_reference_owner",
            ondelete="CASCADE",
        ),
    )
    writing_document_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(primary_key=True)
    citation_id: Mapped[int] = mapped_column(primary_key=True)
