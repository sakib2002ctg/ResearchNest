"""Add the private paper workspace and preserve the existing library."""

import sqlalchemy as sa

from alembic import context, op

revision = "d429e3a5b6c1"
down_revision = "c83a2f1a4d71"
branch_labels = None
depends_on = None


def _timestamp(name: str) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _owner_reference(
    table: str, target: str, column: str, key: str
) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ("user_id", column),
        (f"{target}.user_id", f"{target}.id"),
        name=f"fk_{table}_{key}_owner",
        ondelete="CASCADE",
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_research_papers_owner_id_id", "research_papers", ["owner_id", "id"]
    )
    op.drop_constraint(
        "user_papers_legacy_paper_id_fkey", "user_papers", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_user_papers_legacy_owner",
        "user_papers",
        "research_papers",
        ["user_id", "legacy_paper_id"],
        ["owner_id", "id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_user_papers_user_id_id", "user_papers", ["user_id", "id"]
    )
    op.alter_column(
        "user_papers", "paper_id", existing_type=sa.Integer(), nullable=True
    )
    op.add_column(
        "user_papers",
        sa.Column(
            "reading_status", sa.String(20), server_default="unread", nullable=False
        ),
    )
    op.add_column(
        "user_papers",
        sa.Column(
            "reading_progress_percent", sa.Float(), server_default="0.0", nullable=False
        ),
    )
    op.create_check_constraint(
        "ck_user_papers_reading_status",
        "user_papers",
        "reading_status IN ('unread', 'reading', 'completed')",
    )
    op.create_check_constraint(
        "ck_user_papers_reading_progress_percent",
        "user_papers",
        "reading_progress_percent BETWEEN 0 AND 100",
    )
    op.execute(
        "INSERT INTO user_papers (user_id, paper_id, legacy_paper_id, saved_at) "
        "SELECT owner_id, NULL, id, created_at FROM research_papers "
        "ON CONFLICT (legacy_paper_id) DO NOTHING"
    )

    op.create_table(
        "collections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.UniqueConstraint("user_id", "id", name="uq_collections_user_id_id"),
        sa.UniqueConstraint("user_id", "name", name="uq_collections_user_name"),
    )
    op.create_table(
        "collection_papers",
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("collection_id", sa.Integer(), primary_key=True),
        sa.Column("user_paper_id", sa.Integer(), primary_key=True),
        _timestamp("created_at"),
        _owner_reference(
            "collection_papers", "collections", "collection_id", "collection"
        ),
        _owner_reference(
            "collection_papers", "user_papers", "user_paper_id", "user_paper"
        ),
    )
    op.create_index(
        "ix_collection_papers_owner_paper",
        "collection_papers",
        ["user_id", "user_paper_id"],
    )
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(7), nullable=True),
        sa.UniqueConstraint("user_id", "id", name="uq_tags_user_id_id"),
        sa.UniqueConstraint("user_id", "name", name="uq_tags_user_name"),
    )
    op.create_table(
        "paper_tags",
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("tag_id", sa.Integer(), primary_key=True),
        sa.Column("user_paper_id", sa.Integer(), primary_key=True),
        _timestamp("created_at"),
        _owner_reference("paper_tags", "tags", "tag_id", "tag"),
        _owner_reference("paper_tags", "user_papers", "user_paper_id", "user_paper"),
    )
    op.create_index(
        "ix_paper_tags_owner_paper", "paper_tags", ["user_id", "user_paper_id"]
    )
    op.create_table(
        "annotations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey(
                "users.id", name="fk_annotations_user_id_users", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("user_paper_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        _owner_reference("annotations", "user_papers", "user_paper_id", "user_paper"),
        sa.CheckConstraint("type IN ('note', 'highlight')", name="ck_annotations_type"),
        sa.CheckConstraint("page_number > 0", name="ck_annotations_page_number"),
    )
    op.create_index(
        "ix_annotations_owner_paper", "annotations", ["user_id", "user_paper_id"]
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("user_paper_id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(80), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        _timestamp("created_at"),
        _owner_reference("documents", "user_papers", "user_paper_id", "user_paper"),
        sa.UniqueConstraint("user_paper_id", name="uq_documents_user_paper"),
        sa.UniqueConstraint("storage_key", name="uq_documents_storage_key"),
        sa.CheckConstraint("size_bytes > 0", name="ck_documents_size_bytes"),
        sa.CheckConstraint("page_count > 0", name="ck_documents_page_count"),
    )
    op.create_index(
        "ix_documents_owner_paper", "documents", ["user_id", "user_paper_id"]
    )
    op.create_table(
        "pdf_deletions",
        sa.Column("storage_key", sa.String(80), primary_key=True),
        _timestamp("created_at"),
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        has_documents = (
            op.get_bind()
            .execute(
                sa.text(
                    "SELECT EXISTS (SELECT 1 FROM documents) "
                    "OR EXISTS (SELECT 1 FROM pdf_deletions)"
                )
            )
            .scalar_one()
        )
        if has_documents:
            raise RuntimeError(
                "Export or purge stored PDFs and drain the deletion queue before "
                "downgrading the private paper workspace."
            )
    op.drop_table("pdf_deletions")
    op.drop_table("documents")
    op.drop_table("annotations")
    op.drop_table("paper_tags")
    op.drop_table("tags")
    op.drop_table("collection_papers")
    op.drop_table("collections")
    op.execute("DELETE FROM user_papers WHERE paper_id IS NULL")
    op.drop_constraint(
        "ck_user_papers_reading_progress_percent", "user_papers", type_="check"
    )
    op.drop_constraint("ck_user_papers_reading_status", "user_papers", type_="check")
    op.drop_column("user_papers", "reading_progress_percent")
    op.drop_column("user_papers", "reading_status")
    op.alter_column(
        "user_papers", "paper_id", existing_type=sa.Integer(), nullable=False
    )
    op.drop_constraint("uq_user_papers_user_id_id", "user_papers", type_="unique")
    op.drop_constraint("fk_user_papers_legacy_owner", "user_papers", type_="foreignkey")
    op.create_foreign_key(
        "user_papers_legacy_paper_id_fkey",
        "user_papers",
        "research_papers",
        ["legacy_paper_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "uq_research_papers_owner_id_id", "research_papers", type_="unique"
    )
