"""private AI conversations and usage quotas

Revision ID: f6b92d04a173
Revises: e5a14c7b9d32
Create Date: 2026-11-20 00:15:52.514883

"""

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f6b92d04a173"
down_revision: Union[str, Sequence[str], None] = "e5a14c7b9d32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Deferred owner constraints let single-column SET NULL actions run first.
    # All owner pairs are still validated before the transaction can commit.
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_paper_ids", sa.JSON(), nullable=False),
        sa.Column("scope_collection_id", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(length=2), server_default="en", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("language IN ('en','bn')", name="ck_conversations_language"),
        sa.CheckConstraint(
            "scope_type IN ('single_paper','selected_papers','collection')",
            name="ck_conversations_scope",
        ),
        sa.ForeignKeyConstraint(
            ["scope_collection_id"], ["collections.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "scope_collection_id"],
            ["collections.user_id", "collections.id"],
            name="fk_conversations_collection_owner",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "user_id", name="uq_conversations_id_owner"),
    )
    op.create_index(
        op.f("ix_conversations_user_id"), "conversations", ["user_id"], unique=False
    )
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("feature", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "feature IN ('rag_chat','summary','analysis')", name="ck_ai_usage_feature"
        ),
        sa.CheckConstraint(
            "status IN ('pending','completed','failed')", name="ck_ai_usage_status"
        ),
        sa.CheckConstraint(
            "prompt_tokens >= 0 AND completion_tokens >= 0 AND reserved_tokens >= 0",
            name="ck_ai_usage_tokens",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "request_id", name="uq_ai_usage_owner_request"),
    )
    op.create_index(
        op.f("ix_ai_usage_created_at"), "ai_usage", ["created_at"], unique=False
    )
    op.create_index(
        "ix_ai_usage_owner_created", "ai_usage", ["user_id", "created_at"], unique=False
    )
    op.create_index(op.f("ix_ai_usage_user_id"), "ai_usage", ["user_id"], unique=False)
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("evidence_status", sa.String(length=24), nullable=False),
        sa.Column("interpretation", sa.Text(), server_default="", nullable=False),
        sa.Column("missing_information", sa.Text(), server_default="", nullable=False),
        sa.Column("follow_up_questions", sa.JSON(), nullable=False),
        sa.Column("model_used", sa.String(length=128), nullable=True),
        sa.Column("provider_used", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "evidence_status IN ('supported','partial_interpretation','insufficient_evidence')",
            name="ck_messages_evidence",
        ),
        sa.CheckConstraint("role IN ('user','assistant')", name="ck_messages_role"),
        sa.ForeignKeyConstraint(
            ["conversation_id", "user_id"],
            ["conversations.id", "conversations.user_id"],
            name="fk_messages_conversation_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "user_id", name="uq_messages_id_owner"),
        sa.UniqueConstraint(
            "user_id", "request_id", "role", name="uq_messages_request_role"
        ),
    )
    op.create_index(
        op.f("ix_messages_conversation_id"),
        "messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(op.f("ix_messages_user_id"), "messages", ["user_id"], unique=False)
    op.create_table(
        "message_citations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("user_paper_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("chunk_id", sa.Integer(), nullable=True),
        sa.Column("paper_title", sa.String(length=255), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("section_heading", sa.Text(), nullable=True),
        sa.Column("quoted_snippet", sa.Text(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.CheckConstraint("page_number > 0", name="ck_citations_page"),
        sa.CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="ck_citations_relevance",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id", "user_id"],
            ["document_chunks.id", "document_chunks.user_id"],
            name="fk_citations_chunk_owner",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["document_chunks.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["documents.id", "documents.user_id"],
            name="fk_citations_document_owner",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["message_id", "user_id"],
            ["messages.id", "messages.user_id"],
            name="fk_citations_message_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["user_id", "user_paper_id"],
            ["user_papers.user_id", "user_papers.id"],
            name="fk_citations_paper_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["user_paper_id"], ["user_papers.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_message_citations_message_id"),
        "message_citations",
        ["message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_message_citations_user_id"),
        "message_citations",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade an empty workspace; do not silently discard private chat history."""
    if (
        not context.is_offline_mode()
        and op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM conversations) "
                "OR EXISTS (SELECT 1 FROM messages) "
                "OR EXISTS (SELECT 1 FROM message_citations) "
                "OR EXISTS (SELECT 1 FROM ai_usage)"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError(
            "Export or purge AI conversations and usage before downgrade."
        )
    op.drop_index(op.f("ix_message_citations_user_id"), table_name="message_citations")
    op.drop_index(
        op.f("ix_message_citations_message_id"), table_name="message_citations"
    )
    op.drop_table("message_citations")
    op.drop_index(op.f("ix_messages_user_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_conversation_id"), table_name="messages")
    op.drop_table("messages")
    op.drop_index(op.f("ix_ai_usage_user_id"), table_name="ai_usage")
    op.drop_index("ix_ai_usage_owner_created", table_name="ai_usage")
    op.drop_index(op.f("ix_ai_usage_created_at"), table_name="ai_usage")
    op.drop_table("ai_usage")
    op.drop_index(op.f("ix_conversations_user_id"), table_name="conversations")
    op.drop_table("conversations")
