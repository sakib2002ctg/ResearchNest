"""private paper analyses and comparisons

Revision ID: a7c14e5f902b
Revises: f6b92d04a173
Create Date: 2026-11-20 01:08:50.850115

"""

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a7c14e5f902b"
down_revision: Union[str, Sequence[str], None] = "f6b92d04a173"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Additive owner-scoped records; all preexisting tables remain unchanged.
    op.create_table(
        "paper_comparisons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("user_paper_ids", sa.JSON(), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("comparison_matrix", sa.JSON(), nullable=False),
        sa.Column("literature_synthesis", sa.Text(), nullable=False),
        sa.Column("research_gaps", sa.JSON(), nullable=False),
        sa.Column("evidence_links", sa.JSON(), nullable=False),
        sa.Column("source_versions", sa.JSON(), nullable=False),
        sa.Column("provider_used", sa.String(length=32), nullable=False),
        sa.Column("model_used", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "language IN ('en','bn')", name="ck_paper_comparisons_language"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "user_id", name="uq_paper_comparisons_id_owner"),
        sa.UniqueConstraint(
            "user_id", "request_id", name="uq_paper_comparisons_owner_request"
        ),
    )
    op.create_index(
        "ix_paper_comparisons_owner_created",
        "paper_comparisons",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_paper_comparisons_user_id"),
        "paper_comparisons",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "comparison_papers",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("comparison_id", sa.Integer(), nullable=False),
        sa.Column("user_paper_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["comparison_id", "user_id"],
            ["paper_comparisons.id", "paper_comparisons.user_id"],
            name="fk_comparison_papers_comparison_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "user_paper_id"],
            ["user_papers.user_id", "user_papers.id"],
            name="fk_comparison_papers_paper_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "comparison_id", "user_paper_id"),
    )
    op.create_index(
        "ix_comparison_papers_owner_paper",
        "comparison_papers",
        ["user_id", "user_paper_id"],
        unique=False,
    )
    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("user_paper_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("abstract_summary", sa.Text(), nullable=False),
        sa.Column("research_problem", sa.Text(), nullable=False),
        sa.Column("research_objectives", sa.JSON(), nullable=False),
        sa.Column("methodology", sa.Text(), nullable=False),
        sa.Column("datasets", sa.JSON(), nullable=False),
        sa.Column("models_and_algorithms", sa.JSON(), nullable=False),
        sa.Column("evaluation_metrics", sa.JSON(), nullable=False),
        sa.Column("key_results", sa.Text(), nullable=False),
        sa.Column("contributions", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("future_work", sa.JSON(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("weaknesses", sa.JSON(), nullable=False),
        sa.Column("field_statuses", sa.JSON(), nullable=False),
        sa.Column("evidence_links", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider_used", sa.String(length=32), nullable=False),
        sa.Column("model_used", sa.String(length=128), nullable=False),
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
        sa.CheckConstraint("language IN ('en','bn')", name="ck_analyses_language"),
        sa.CheckConstraint(
            "status IN ('completed','failed')", name="ck_analyses_status"
        ),
        sa.CheckConstraint("document_version > 0", name="ck_analyses_document_version"),
        sa.ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["documents.id", "documents.user_id"],
            name="fk_analyses_document_owner",
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["user_id", "user_paper_id"],
            ["user_papers.user_id", "user_papers.id"],
            name="fk_analyses_paper_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["user_paper_id"], ["user_papers.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "user_paper_id",
            "language",
            name="uq_analyses_owner_paper_language",
        ),
    )
    op.create_index(
        "ix_analyses_owner_updated", "analyses", ["user_id", "updated_at"], unique=False
    )
    op.create_index(op.f("ix_analyses_user_id"), "analyses", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_analyses_user_paper_id"), "analyses", ["user_paper_id"], unique=False
    )


def downgrade() -> None:
    """Refuse to silently discard saved private intelligence."""
    if (
        not context.is_offline_mode()
        and op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM analyses) "
                "OR EXISTS (SELECT 1 FROM paper_comparisons)"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError("Export or purge paper intelligence before downgrade.")
    op.drop_index(op.f("ix_analyses_user_paper_id"), table_name="analyses")
    op.drop_index(op.f("ix_analyses_user_id"), table_name="analyses")
    op.drop_index("ix_analyses_owner_updated", table_name="analyses")
    op.drop_table("analyses")
    op.drop_index("ix_comparison_papers_owner_paper", table_name="comparison_papers")
    op.drop_table("comparison_papers")
    op.drop_index(op.f("ix_paper_comparisons_user_id"), table_name="paper_comparisons")
    op.drop_index("ix_paper_comparisons_owner_created", table_name="paper_comparisons")
    op.drop_table("paper_comparisons")
