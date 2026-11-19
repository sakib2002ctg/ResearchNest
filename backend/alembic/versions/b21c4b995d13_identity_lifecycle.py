"""Add account verification and saved-paper timestamps."""

import sqlalchemy as sa

from alembic import op

revision = "b21c4b995d13"
down_revision = "8ad1e721e53b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_verified", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )
    op.add_column(
        "research_papers",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_research_papers_owner_created_id",
        "research_papers",
        ["owner_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_papers_owner_created_id", table_name="research_papers")
    op.drop_column("research_papers", "created_at")
    op.drop_column("users", "is_verified")
