"""Private conversations, owner-bound evidence and durable generation accounting."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class Conversation(Base):
    __tablename__ = "conversations"
    # Nullable resource IDs use SET NULL independently of the immutable owner.
    # Deferral validates owner pairs after those referential actions have run.
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_conversations_id_owner"),
        ForeignKeyConstraint(
            ["user_id", "scope_collection_id"],
            ["collections.user_id", "collections.id"],
            name="fk_conversations_collection_owner",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "scope_type IN ('single_paper','selected_papers','collection')",
            name="ck_conversations_scope",
        ),
        CheckConstraint("language IN ('en','bn')", name="ck_conversations_language"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    scope_type: Mapped[str] = mapped_column(String(20))
    scope_paper_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    scope_collection_id: Mapped[int | None] = mapped_column(
        ForeignKey("collections.id", ondelete="SET NULL")
    )
    language: Mapped[str] = mapped_column(String(2), default="en", server_default="en")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "user_id"],
            ["conversations.id", "conversations.user_id"],
            name="fk_messages_conversation_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "user_id", name="uq_messages_id_owner"),
        UniqueConstraint(
            "user_id", "request_id", "role", name="uq_messages_request_role"
        ),
        CheckConstraint("role IN ('user','assistant')", name="ck_messages_role"),
        CheckConstraint(
            "evidence_status IN "
            "('supported','partial_interpretation','insufficient_evidence')",
            name="ck_messages_evidence",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    request_id: Mapped[str] = mapped_column(String(36))
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    evidence_status: Mapped[str] = mapped_column(
        String(24), default="insufficient_evidence"
    )
    interpretation: Mapped[str] = mapped_column(Text, default="", server_default="")
    missing_information: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    follow_up_questions: Mapped[list[str]] = mapped_column(JSON, default=list)
    model_used: Mapped[str | None] = mapped_column(String(128))
    provider_used: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MessageCitation(Base):
    __tablename__ = "message_citations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["message_id", "user_id"],
            ["messages.id", "messages.user_id"],
            name="fk_citations_message_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["user_id", "user_paper_id"],
            ["user_papers.user_id", "user_papers.id"],
            name="fk_citations_paper_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["documents.id", "documents.user_id"],
            name="fk_citations_document_owner",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["chunk_id", "user_id"],
            ["document_chunks.id", "document_chunks.user_id"],
            name="fk_citations_chunk_owner",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("page_number > 0", name="ck_citations_page"),
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="ck_citations_relevance",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    user_paper_id: Mapped[int] = mapped_column(
        ForeignKey("user_papers.id", ondelete="CASCADE")
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL")
    )
    paper_title: Mapped[str] = mapped_column(String(255))
    page_number: Mapped[int] = mapped_column(Integer)
    section_heading: Mapped[str | None] = mapped_column(Text)
    quoted_snippet: Mapped[str] = mapped_column(Text)
    relevance_score: Mapped[float] = mapped_column(Float)


class AIUsage(Base):
    __tablename__ = "ai_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id", name="uq_ai_usage_owner_request"),
        CheckConstraint(
            "feature IN ('rag_chat','summary','analysis','writing','multimodal')",
            name="ck_ai_usage_feature",
        ),
        CheckConstraint(
            "status IN ('pending','completed','failed')", name="ck_ai_usage_status"
        ),
        CheckConstraint(
            "prompt_tokens >= 0 AND completion_tokens >= 0 AND reserved_tokens >= 0",
            name="ck_ai_usage_tokens",
        ),
        Index("ix_ai_usage_owner_created", "user_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    request_id: Mapped[str] = mapped_column(String(36))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    feature: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(32))
    model_name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(12), default="pending")
    reserved_tokens: Mapped[int] = mapped_column(Integer)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
