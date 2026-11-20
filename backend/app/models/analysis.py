"""Private, source-versioned paper intelligence snapshots."""

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


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "user_paper_id",
            "language",
            name="uq_analyses_owner_paper_language",
        ),
        ForeignKeyConstraint(
            ["user_id", "user_paper_id"],
            ["user_papers.user_id", "user_papers.id"],
            name="fk_analyses_paper_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["documents.id", "documents.user_id"],
            name="fk_analyses_document_owner",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("language IN ('en','bn')", name="ck_analyses_language"),
        CheckConstraint("status IN ('completed','failed')", name="ck_analyses_status"),
        CheckConstraint("document_version > 0", name="ck_analyses_document_version"),
        Index("ix_analyses_owner_updated", "user_id", "updated_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    user_paper_id: Mapped[int] = mapped_column(
        ForeignKey("user_papers.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    document_version: Mapped[int] = mapped_column(default=1)
    source_fingerprint: Mapped[str] = mapped_column(String(64))
    request_id: Mapped[str] = mapped_column(String(36))
    language: Mapped[str] = mapped_column(String(2))
    status: Mapped[str] = mapped_column(String(12))
    abstract_summary: Mapped[str] = mapped_column(Text)
    research_problem: Mapped[str] = mapped_column(Text)
    research_objectives: Mapped[list[str]] = mapped_column(JSON)
    methodology: Mapped[str] = mapped_column(Text)
    datasets: Mapped[list[str]] = mapped_column(JSON)
    models_and_algorithms: Mapped[list[str]] = mapped_column(JSON)
    evaluation_metrics: Mapped[list[str]] = mapped_column(JSON)
    key_results: Mapped[str] = mapped_column(Text)
    contributions: Mapped[list[str]] = mapped_column(JSON)
    limitations: Mapped[list[str]] = mapped_column(JSON)
    future_work: Mapped[list[str]] = mapped_column(JSON)
    strengths: Mapped[list[str]] = mapped_column(JSON)
    weaknesses: Mapped[list[str]] = mapped_column(JSON)
    field_statuses: Mapped[dict[str, str]] = mapped_column(JSON)
    evidence_links: Mapped[list[dict]] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    provider_used: Mapped[str] = mapped_column(String(32))
    model_used: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PaperComparison(Base):
    __tablename__ = "paper_comparisons"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_paper_comparisons_id_owner"),
        UniqueConstraint(
            "user_id", "request_id", name="uq_paper_comparisons_owner_request"
        ),
        CheckConstraint(
            "language IN ('en','bn')", name="ck_paper_comparisons_language"
        ),
        Index("ix_paper_comparisons_owner_created", "user_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    user_paper_ids: Mapped[list[int]] = mapped_column(JSON)
    request_id: Mapped[str] = mapped_column(String(36))
    language: Mapped[str] = mapped_column(String(2))
    comparison_matrix: Mapped[list[dict]] = mapped_column(JSON)
    literature_synthesis: Mapped[str] = mapped_column(Text)
    research_gaps: Mapped[list[dict]] = mapped_column(JSON)
    evidence_links: Mapped[list[dict]] = mapped_column(JSON)
    source_versions: Mapped[list[dict]] = mapped_column(JSON)
    provider_used: Mapped[str] = mapped_column(String(32))
    model_used: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ComparisonPaper(Base):
    """Enforce same-owner membership independently of the JSON display snapshot."""

    __tablename__ = "comparison_papers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["comparison_id", "user_id"],
            ["paper_comparisons.id", "paper_comparisons.user_id"],
            name="fk_comparison_papers_comparison_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["user_id", "user_paper_id"],
            ["user_papers.user_id", "user_papers.id"],
            name="fk_comparison_papers_paper_owner",
            ondelete="CASCADE",
        ),
        Index("ix_comparison_papers_owner_paper", "user_id", "user_paper_id"),
    )
    user_id: Mapped[int] = mapped_column(primary_key=True)
    comparison_id: Mapped[int] = mapped_column(primary_key=True)
    user_paper_id: Mapped[int] = mapped_column(primary_key=True)
