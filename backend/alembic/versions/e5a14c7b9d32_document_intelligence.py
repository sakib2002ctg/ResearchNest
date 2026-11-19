"""Add the document intelligence index and versioned processing jobs."""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import context, op
from app.core.config import settings

revision = "e5a14c7b9d32"
down_revision = "d429e3a5b6c1"
branch_labels = None
depends_on = None

VECTOR_DIMENSIONS = 384


def _timestamp(name: str) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _owner_reference(table: str, target: str, column: str, key: str):
    return sa.ForeignKeyConstraint(
        (column, "user_id"),
        (f"{target}.id", f"{target}.user_id"),
        name=f"fk_{table}_{key}_owner",
        ondelete="CASCADE",
    )


def upgrade() -> None:
    if settings.PGVECTOR_ENABLED:
        # The pgvector-backed deployment profile provisions this extension.
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        vector_column_type = Vector(VECTOR_DIMENSIONS)
    else:
        # The disabled profile retains portable JSON vectors on stock PG/SQLite.
        vector_column_type = sa.JSON()

    op.add_column(
        "documents",
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
    )
    op.add_column("documents", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column("documents", _timestamp("updated_at"))
    op.create_check_constraint(
        "ck_documents_intelligence_status",
        "documents",
        "status IN ('pending', 'processing', 'completed', 'failed')",
    )
    op.create_check_constraint(
        "ck_documents_intelligence_version", "documents", "version > 0"
    )
    op.create_unique_constraint(
        "uq_documents_id_user_id", "documents", ["id", "user_id"]
    )
    op.create_foreign_key(
        "fk_documents_user",
        "documents",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_documents_intelligence_owner_status", "documents", ["user_id", "status"]
    )

    op.create_table(
        "document_pages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("document_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("ocr_used", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("section_heading", sa.Text(), nullable=True),
        _owner_reference("document_pages", "documents", "document_id", "document"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_document_pages_user", ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "document_id",
            "document_version",
            "page_number",
            name="uq_document_pages_version_page",
        ),
        sa.CheckConstraint("page_number > 0", name="ck_document_pages_page_number"),
        sa.CheckConstraint("document_version > 0", name="ck_document_pages_version"),
    )
    op.create_index(
        "ix_document_pages_document_page",
        "document_pages",
        ["document_id", "page_number"],
    )
    op.create_index(
        "ix_document_pages_owner", "document_pages", ["user_id", "document_id"]
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("document_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("section_heading", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        _owner_reference("document_chunks", "documents", "document_id", "document"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_document_chunks_user",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "document_id",
            "document_version",
            "page_number",
            "chunk_index",
            name="uq_document_chunks_version_page_index",
        ),
        sa.UniqueConstraint("id", "user_id", name="uq_document_chunks_id_user_id"),
        sa.CheckConstraint("document_version > 0", name="ck_document_chunks_version"),
        sa.CheckConstraint("page_number > 0", name="ck_document_chunks_page_number"),
        sa.CheckConstraint("chunk_index >= 0", name="ck_document_chunks_index"),
        sa.CheckConstraint("token_count >= 0", name="ck_document_chunks_tokens"),
    )
    op.create_index(
        "ix_document_chunks_owner_document",
        "document_chunks",
        ["user_id", "document_id"],
    )
    op.create_index(
        "ix_document_chunks_owner_page",
        "document_chunks",
        ["user_id", "document_id", "page_number"],
    )

    op.create_table(
        "embeddings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chunk_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("document_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("vector_json", sa.JSON(), nullable=False),
        sa.Column("vector_pg", vector_column_type, nullable=True),
        sa.ForeignKeyConstraint(
            ["chunk_id", "user_id"],
            ["document_chunks.id", "document_chunks.user_id"],
            name="fk_embeddings_chunk_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_embeddings_user", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("chunk_id", name="uq_embeddings_chunk"),
        sa.CheckConstraint("document_version > 0", name="ck_embeddings_version"),
    )
    op.create_index("ix_embeddings_owner", "embeddings", ["user_id", "model_name"])
    if settings.PGVECTOR_ENABLED:
        op.create_index(
            "ix_embeddings_vector_hnsw",
            "embeddings",
            ["vector_pg"],
            postgresql_using="hnsw",
            postgresql_ops={"vector_pg": "vector_cosine_ops"},
        )

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("document_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "job_type",
            sa.String(64),
            server_default="pdf_extract_and_index",
            nullable=False,
        ),
        sa.Column("status", sa.String(16), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        _timestamp("created_at"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        _owner_reference("processing_jobs", "documents", "document_id", "document"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_processing_jobs_user",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "document_id",
            "document_version",
            "job_type",
            name="uq_processing_jobs_document_version_type",
        ),
        sa.CheckConstraint(
            "job_type IN ('pdf_extract_and_index')", name="ck_processing_jobs_type"
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_processing_jobs_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_processing_jobs_attempts"),
        sa.CheckConstraint("document_version > 0", name="ck_processing_jobs_version"),
    )
    op.create_index(
        "ix_processing_jobs_owner_status",
        "processing_jobs",
        ["user_id", "status", "created_at"],
    )

    # Existing Phase 04 uploads are placed in the queue exactly once.
    op.execute(
        "INSERT INTO processing_jobs "
        "(document_id, user_id, document_version, job_type, status, attempts) "
        "SELECT id, user_id, version, 'pdf_extract_and_index', 'queued', 0 "
        "FROM documents"
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        has_rows = (
            op.get_bind()
            .execute(
                sa.text(
                    "SELECT EXISTS (SELECT 1 FROM documents) "
                    "OR EXISTS (SELECT 1 FROM document_pages) "
                    "OR EXISTS (SELECT 1 FROM document_chunks) "
                    "OR EXISTS (SELECT 1 FROM embeddings) "
                    "OR EXISTS (SELECT 1 FROM processing_jobs)"
                )
            )
            .scalar_one()
        )
        if has_rows:
            raise RuntimeError(
                "Export or purge documents and processing jobs before downgrade."
            )

    op.drop_table("processing_jobs")
    if settings.PGVECTOR_ENABLED:
        op.drop_index("ix_embeddings_vector_hnsw", table_name="embeddings")
    op.drop_index("ix_embeddings_owner", table_name="embeddings")
    op.drop_table("embeddings")
    op.drop_index("ix_document_chunks_owner_page", table_name="document_chunks")
    op.drop_index("ix_document_chunks_owner_document", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_document_pages_owner", table_name="document_pages")
    op.drop_index("ix_document_pages_document_page", table_name="document_pages")
    op.drop_table("document_pages")
    op.drop_index("ix_documents_intelligence_owner_status", table_name="documents")
    op.drop_constraint("uq_documents_id_user_id", "documents", type_="unique")
    op.drop_constraint("fk_documents_user", "documents", type_="foreignkey")
    op.drop_constraint("ck_documents_intelligence_version", "documents", type_="check")
    op.drop_constraint("ck_documents_intelligence_status", "documents", type_="check")
    op.drop_column("documents", "updated_at")
    op.drop_column("documents", "version")
    op.drop_column("documents", "error_message")
    op.drop_column("documents", "status")
