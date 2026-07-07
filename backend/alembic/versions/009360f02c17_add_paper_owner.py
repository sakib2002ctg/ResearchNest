"""add paper owner

Revision ID: 009360f02c17
Revises: 146022ae25cb
Create Date: 2026-07-04 03:27:53.924432

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "009360f02c17"
down_revision: Union[str, Sequence[str], None] = "146022ae25cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "research_papers",
        sa.Column("owner_id", sa.Integer(), nullable=False),
    )

    op.create_foreign_key(
        "fk_research_papers_owner_id_users",
        "research_papers",
        "users",
        ["owner_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_research_papers_owner_id_users",
        "research_papers",
        type_="foreignkey",
    )

    op.drop_column(
        "research_papers",
        "owner_id",
    )
