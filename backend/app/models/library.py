from datetime import datetime

from sqlalchemy import (
    BigInteger,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database.database import Base


class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_collections_user_id_id"),
        UniqueConstraint("user_id", "name", name="uq_collections_user_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CollectionPaper(Base):
    __tablename__ = "collection_papers"
    __table_args__ = (
        ForeignKeyConstraint(
            ("user_id", "collection_id"),
            ("collections.user_id", "collections.id"),
            name="fk_collection_papers_collection_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ("user_id", "user_paper_id"),
            ("user_papers.user_id", "user_papers.id"),
            name="fk_collection_papers_user_paper_owner",
            ondelete="CASCADE",
        ),
        Index("ix_collection_papers_owner_paper", "user_id", "user_paper_id"),
    )

    user_id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int] = mapped_column(primary_key=True)
    user_paper_id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_tags_user_id_id"),
        UniqueConstraint("user_id", "name", name="uq_tags_user_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    color: Mapped[str | None] = mapped_column(String(7))


class PaperTag(Base):
    __tablename__ = "paper_tags"
    __table_args__ = (
        ForeignKeyConstraint(
            ("user_id", "tag_id"),
            ("tags.user_id", "tags.id"),
            name="fk_paper_tags_tag_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ("user_id", "user_paper_id"),
            ("user_papers.user_id", "user_papers.id"),
            name="fk_paper_tags_user_paper_owner",
            ondelete="CASCADE",
        ),
        Index("ix_paper_tags_owner_paper", "user_id", "user_paper_id"),
    )

    user_id: Mapped[int] = mapped_column(primary_key=True)
    tag_id: Mapped[int] = mapped_column(primary_key=True)
    user_paper_id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Annotation(Base):
    __tablename__ = "annotations"
    __table_args__ = (
        ForeignKeyConstraint(
            ("user_id", "user_paper_id"),
            ("user_papers.user_id", "user_papers.id"),
            name="fk_annotations_user_paper_owner",
            ondelete="CASCADE",
        ),
        CheckConstraint("type IN ('note', 'highlight')", name="ck_annotations_type"),
        CheckConstraint("page_number > 0", name="ck_annotations_page_number"),
        Index("ix_annotations_owner_paper", "user_id", "user_paper_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_annotations_user_id_users", ondelete="CASCADE")
    )
    user_paper_id: Mapped[int]
    type: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None]
    color: Mapped[str | None] = mapped_column(String(7))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ("user_id", "user_paper_id"),
            ("user_papers.user_id", "user_papers.id"),
            name="fk_documents_user_paper_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint("user_paper_id", name="uq_documents_user_paper"),
        UniqueConstraint("storage_key", name="uq_documents_storage_key"),
        UniqueConstraint("id", "user_id", name="uq_documents_id_user_id"),
        CheckConstraint("size_bytes > 0", name="ck_documents_size_bytes"),
        CheckConstraint("page_count > 0", name="ck_documents_page_count"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_documents_intelligence_status",
        ),
        CheckConstraint("version > 0", name="ck_documents_intelligence_version"),
        Index("ix_documents_owner_paper", "user_id", "user_paper_id"),
        Index("ix_documents_intelligence_owner_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_documents_user", ondelete="CASCADE")
    )
    user_paper_id: Mapped[int]
    storage_key: Mapped[str] = mapped_column(String(80))
    original_filename: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Phase 04 called this physical field sha256. Keep the old column and API
    # compatibility while exposing the Phase 05 file_hash vocabulary.
    file_hash = synonym("sha256")
    pages = relationship(
        "DocumentPage", back_populates="document", cascade="all, delete-orphan"
    )
    chunks = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )
    processing_jobs = relationship(
        "ProcessingJob", back_populates="document", cascade="all, delete-orphan"
    )


class PDFDeletion(Base):
    __tablename__ = "pdf_deletions"

    storage_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
