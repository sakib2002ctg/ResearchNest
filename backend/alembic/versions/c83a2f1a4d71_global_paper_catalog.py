"""Create the global academic catalogue and private library links."""

import sqlalchemy as sa

from alembic import op

revision = "c83a2f1a4d71"
down_revision = "b21c4b995d13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "papers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("publication_type", sa.String(length=64), nullable=True),
        sa.Column("canonical_url", sa.String(length=2048), nullable=True),
        sa.Column("citation_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_papers_doi", "papers", ["doi"], unique=True)
    op.create_index("ix_papers_title", "papers", ["title"])

    op.create_table(
        "authors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("orcid", sa.String(length=19), nullable=True),
        sa.UniqueConstraint("orcid", name="uq_authors_orcid"),
    )
    op.create_index("ix_authors_normalized_name", "authors", ["normalized_name"])

    op.create_table(
        "paper_authors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "paper_id",
            sa.Integer(),
            sa.ForeignKey("papers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.Integer(),
            sa.ForeignKey("authors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("paper_id", "author_id", name="uq_paper_authors_pair"),
        sa.UniqueConstraint("paper_id", "position", name="uq_paper_authors_position"),
    )
    op.create_index("ix_paper_authors_paper_id", "paper_authors", ["paper_id"])
    op.create_index("ix_paper_authors_author_id", "paper_authors", ["author_id"])

    op.create_table(
        "paper_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "paper_id",
            sa.Integer(),
            sa.ForeignKey("papers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "retrieved_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "provider", "external_id", name="uq_paper_sources_provider_external"
        ),
    )
    op.create_index("ix_paper_sources_paper_id", "paper_sources", ["paper_id"])

    op.create_table(
        "user_papers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "paper_id",
            sa.Integer(),
            sa.ForeignKey("papers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "legacy_paper_id",
            sa.Integer(),
            sa.ForeignKey("research_papers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "saved_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.UniqueConstraint("user_id", "paper_id", name="uq_user_papers_user_paper"),
        sa.UniqueConstraint("legacy_paper_id", name="uq_user_papers_legacy_paper"),
    )
    op.create_index("ix_user_papers_user_id", "user_papers", ["user_id"])
    op.create_index("ix_user_papers_paper_id", "user_papers", ["paper_id"])
    op.create_index("ix_user_papers_user_saved", "user_papers", ["user_id", "saved_at"])


def downgrade() -> None:
    op.drop_table("user_papers")
    op.drop_table("paper_sources")
    op.drop_table("paper_authors")
    op.drop_table("authors")
    op.drop_table("papers")
