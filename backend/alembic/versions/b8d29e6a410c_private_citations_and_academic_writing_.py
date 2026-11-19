"""private citations and academic writing studio

Revision ID: b8d29e6a410c
Revises: a7c14e5f902b
Create Date: 2026-11-20 01:57:33.148629

"""

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b8d29e6a410c"
down_revision: Union[str, Sequence[str], None] = "a7c14e5f902b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("ck_ai_usage_feature", "ai_usage", type_="check")
    op.create_check_constraint(
        "ck_ai_usage_feature",
        "ai_usage",
        "feature IN ('rag_chat','summary','analysis','writing')",
    )
    op.create_table(
        "writing_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("doc_type", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("outline", sa.JSON(), nullable=False),
        sa.Column("content_markdown", sa.Text(), server_default="", nullable=False),
        sa.Column("cited_citation_ids", sa.JSON(), nullable=False),
        sa.Column("ai_suggestions_log", sa.JSON(), nullable=False),
        sa.Column("word_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
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
        sa.CheckConstraint(
            "doc_type IN ('research_paper','research_proposal','thesis','literature_review')",
            name="ck_writing_documents_type",
        ),
        sa.CheckConstraint(
            "language IN ('en','bn')", name="ck_writing_documents_language"
        ),
        sa.CheckConstraint(
            "word_count >= 0 AND revision >= 1", name="ck_writing_documents_counts"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "user_id", name="uq_writing_documents_id_owner"),
    )
    op.create_index(
        "ix_writing_documents_owner_updated",
        "writing_documents",
        ["user_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_writing_documents_user_id"),
        "writing_documents",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "writing_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("writing_document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("outline", sa.JSON(), nullable=False),
        sa.Column("cited_citation_ids", sa.JSON(), nullable=False),
        sa.Column("change_summary", sa.String(length=300), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("version_number > 0", name="ck_writing_versions_number"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["writing_document_id", "user_id"],
            ["writing_documents.id", "writing_documents.user_id"],
            name="fk_writing_versions_document_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["writing_document_id"], ["writing_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "writing_document_id", "version_number", name="uq_writing_versions_number"
        ),
    )
    op.create_index(
        op.f("ix_writing_versions_user_id"),
        "writing_versions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_writing_versions_writing_document_id"),
        "writing_versions",
        ["writing_document_id"],
        unique=False,
    )
    op.create_table(
        "citations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("user_paper_id", sa.Integer(), nullable=True),
        sa.Column("cite_key", sa.String(length=100), nullable=False),
        sa.Column("identity_key", sa.String(length=64), nullable=False),
        sa.Column("title_year_key", sa.String(length=64), nullable=False),
        sa.Column("entry_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("venue", sa.String(length=500), nullable=True),
        sa.Column("volume", sa.String(length=100), nullable=True),
        sa.Column("issue", sa.String(length=100), nullable=True),
        sa.Column("pages", sa.String(length=100), nullable=True),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("publisher", sa.String(length=500), nullable=True),
        sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False),
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
        sa.CheckConstraint(
            "entry_type IN ('article','inproceedings','book','misc','preprint')",
            name="ck_citations_entry_type",
        ),
        sa.CheckConstraint(
            "year IS NULL OR (year >= 1000 AND year <= 2200)", name="ck_citations_year"
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "user_paper_id"],
            ["user_papers.user_id", "user_papers.id"],
            name="fk_citations_library_owner",
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["user_paper_id"], ["user_papers.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "user_id", name="uq_citations_id_owner"),
        sa.UniqueConstraint("user_id", "cite_key", name="uq_citations_owner_key"),
        sa.UniqueConstraint(
            "user_id", "identity_key", name="uq_citations_owner_identity"
        ),
    )
    op.create_index(
        "ix_citations_owner_title_year",
        "citations",
        ["user_id", "title_year_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_citations_user_id"), "citations", ["user_id"], unique=False
    )
    op.create_table(
        "writing_citations",
        sa.Column("writing_document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("citation_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["citation_id", "user_id"],
            ["citations.id", "citations.user_id"],
            name="fk_writing_citations_reference_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["writing_document_id", "user_id"],
            ["writing_documents.id", "writing_documents.user_id"],
            name="fk_writing_citations_document_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("writing_document_id", "user_id", "citation_id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    if (
        not context.is_offline_mode()
        and op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM writing_documents) OR EXISTS (SELECT 1 FROM citations) "
                "OR EXISTS (SELECT 1 FROM ai_usage WHERE feature='writing')"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError("Export or purge writing and citations before downgrade.")
    op.drop_constraint("ck_ai_usage_feature", "ai_usage", type_="check")
    op.create_check_constraint(
        "ck_ai_usage_feature",
        "ai_usage",
        "feature IN ('rag_chat','summary','analysis')",
    )
    op.drop_table("writing_citations")
    op.drop_index(op.f("ix_citations_user_id"), table_name="citations")
    op.drop_index("ix_citations_owner_title_year", table_name="citations")
    op.drop_table("citations")
    op.drop_index(
        op.f("ix_writing_versions_writing_document_id"), table_name="writing_versions"
    )
    op.drop_index(op.f("ix_writing_versions_user_id"), table_name="writing_versions")
    op.drop_table("writing_versions")
    op.drop_index(op.f("ix_writing_documents_user_id"), table_name="writing_documents")
    op.drop_index("ix_writing_documents_owner_updated", table_name="writing_documents")
    op.drop_table("writing_documents")
    # ### end Alembic commands ###
