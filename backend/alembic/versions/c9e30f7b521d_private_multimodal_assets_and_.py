"""private multimodal assets and extraction jobs

Revision ID: c9e30f7b521d
Revises: b8d29e6a410c
Create Date: 2026-11-20 03:15:31.288069

"""

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c9e30f7b521d"
down_revision: Union[str, Sequence[str], None] = "b8d29e6a410c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("ck_ai_usage_feature", "ai_usage", type_="check")
    op.create_check_constraint(
        "ck_ai_usage_feature",
        "ai_usage",
        "feature IN ('rag_chat','summary','analysis','writing','multimodal')",
    )
    op.create_table(
        "asset_deletions",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", "storage_key"),
    )
    op.create_table(
        "asset_extraction_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed')",
            name="ck_asset_jobs_status",
        ),
        sa.CheckConstraint(
            "generation > 0 AND document_version > 0 AND attempts >= 0",
            name="ck_asset_jobs_counts",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["documents.id", "documents.user_id"],
            name="fk_asset_jobs_document_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_asset_jobs_document"),
    )
    op.create_index(
        "ix_asset_jobs_owner_status",
        "asset_extraction_jobs",
        ["user_id", "status", "created_at"],
        unique=False,
    )
    op.create_table(
        "document_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("extraction_generation", sa.Integer(), nullable=False),
        sa.Column("asset_type", sa.String(length=12), nullable=False),
        sa.Column("asset_label", sa.String(length=200), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("extracted_text_or_latex", sa.Text(), nullable=True),
        sa.Column("structured_data", sa.JSON(), nullable=True),
        sa.Column("storage_key", sa.String(length=80), nullable=True),
        sa.Column("image_size_bytes", sa.Integer(), nullable=True),
        sa.Column("linked_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("ai_explanation", sa.Text(), nullable=True),
        sa.Column("explanations", sa.JSON(), nullable=False),
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
            "asset_type IN ('figure','chart','diagram','table','equation')",
            name="ck_document_assets_type",
        ),
        sa.CheckConstraint(
            "page_number > 0 AND document_version > 0",
            name="ck_document_assets_version_page",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["documents.id", "documents.user_id"],
            name="fk_document_assets_document_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "user_id", name="uq_document_assets_id_owner"),
        sa.UniqueConstraint("storage_key", name="uq_document_assets_storage"),
    )
    op.create_index(
        op.f("ix_document_assets_document_id"),
        "document_assets",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_assets_owner_document_page",
        "document_assets",
        ["user_id", "document_id", "page_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_assets_user_id"), "document_assets", ["user_id"], unique=False
    )
    op.create_table(
        "asset_chunk_links",
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id", "user_id"],
            ["document_assets.id", "document_assets.user_id"],
            name="fk_asset_chunk_links_asset_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id", "user_id"],
            ["document_chunks.id", "document_chunks.user_id"],
            name="fk_asset_chunk_links_chunk_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("asset_id", "chunk_id", "user_id"),
    )
    op.execute("""CREATE FUNCTION queue_document_asset_deletion() RETURNS trigger AS $$
    BEGIN
        IF OLD.storage_key IS NOT NULL THEN
            INSERT INTO asset_deletions(user_id, storage_key) VALUES(OLD.user_id, OLD.storage_key)
            ON CONFLICT DO NOTHING;
        END IF;
        RETURN OLD;
    END;
    $$ LANGUAGE plpgsql""")
    op.execute(
        """CREATE TRIGGER document_asset_delete_queue AFTER DELETE ON document_assets
        FOR EACH ROW EXECUTE FUNCTION queue_document_asset_deletion()"""
    )


def downgrade() -> None:
    """Downgrade schema."""
    if (
        not context.is_offline_mode()
        and op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM document_assets) OR EXISTS (SELECT 1 FROM asset_deletions) "
                "OR EXISTS (SELECT 1 FROM ai_usage WHERE feature='multimodal')"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError(
            "Purge assets, pending cleanup and multimodal usage before downgrade."
        )
    op.execute("DROP TRIGGER document_asset_delete_queue ON document_assets")
    op.execute("DROP FUNCTION queue_document_asset_deletion()")
    op.drop_constraint("ck_ai_usage_feature", "ai_usage", type_="check")
    op.create_check_constraint(
        "ck_ai_usage_feature",
        "ai_usage",
        "feature IN ('rag_chat','summary','analysis','writing')",
    )
    op.drop_table("asset_chunk_links")
    op.drop_index(op.f("ix_document_assets_user_id"), table_name="document_assets")
    op.drop_index(
        "ix_document_assets_owner_document_page", table_name="document_assets"
    )
    op.drop_index(op.f("ix_document_assets_document_id"), table_name="document_assets")
    op.drop_table("document_assets")
    op.drop_index("ix_asset_jobs_owner_status", table_name="asset_extraction_jobs")
    op.drop_table("asset_extraction_jobs")
    op.drop_table("asset_deletions")
