from datetime import date, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
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

from app.database.database import Base


class Paper(Base):
    """Canonical, provider-independent academic work metadata."""

    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(primary_key=True)
    doi: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    abstract: Mapped[str | None] = mapped_column(Text)
    publication_date: Mapped[date | None] = mapped_column(Date)
    publication_type: Mapped[str | None] = mapped_column(String(64))
    canonical_url: Mapped[str | None] = mapped_column(String(2048))
    citation_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    authors = relationship(
        "PaperAuthor",
        back_populates="paper",
        cascade="all, delete-orphan",
        order_by="PaperAuthor.position",
    )
    sources = relationship(
        "PaperSource", back_populates="paper", cascade="all, delete-orphan"
    )
    user_papers = relationship(
        "UserPaper", back_populates="paper", cascade="all, delete-orphan"
    )


class Author(Base):
    __tablename__ = "authors"
    __table_args__ = (UniqueConstraint("orcid", name="uq_authors_orcid"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    orcid: Mapped[str | None] = mapped_column(String(19))

    papers = relationship("PaperAuthor", back_populates="author")


class PaperAuthor(Base):
    __tablename__ = "paper_authors"
    __table_args__ = (
        UniqueConstraint("paper_id", "author_id", name="uq_paper_authors_pair"),
        UniqueConstraint("paper_id", "position", name="uq_paper_authors_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("authors.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    author = relationship("Author", back_populates="papers")
    paper = relationship("Paper", back_populates="authors")


class PaperSource(Base):
    __tablename__ = "paper_sources"
    __table_args__ = (
        UniqueConstraint(
            "provider", "external_id", name="uq_paper_sources_provider_external"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    paper = relationship("Paper", back_populates="sources")


class UserPaper(Base):
    __tablename__ = "user_papers"
    __table_args__ = (
        UniqueConstraint("user_id", "paper_id", name="uq_user_papers_user_paper"),
        UniqueConstraint("legacy_paper_id", name="uq_user_papers_legacy_paper"),
        UniqueConstraint("user_id", "id", name="uq_user_papers_user_id_id"),
        ForeignKeyConstraint(
            ("user_id", "legacy_paper_id"),
            ("research_papers.owner_id", "research_papers.id"),
            name="fk_user_papers_legacy_owner",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "reading_status IN ('unread', 'reading', 'completed')",
            name="ck_user_papers_reading_status",
        ),
        CheckConstraint(
            "reading_progress_percent BETWEEN 0 AND 100",
            name="ck_user_papers_reading_progress_percent",
        ),
        Index("ix_user_papers_user_saved", "user_id", "saved_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    paper_id: Mapped[int | None] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), index=True
    )
    legacy_paper_id: Mapped[int]
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)
    reading_status: Mapped[str] = mapped_column(String(20), server_default="unread")
    reading_progress_percent: Mapped[float] = mapped_column(Float, server_default="0.0")
    paper = relationship("Paper", back_populates="user_papers")
    user = relationship("User", back_populates="saved_papers")
