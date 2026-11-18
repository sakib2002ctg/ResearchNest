"""Add profiles, preferences, sessions, verification tokens, and audit events."""

import sqlalchemy as sa

from alembic import op

revision = "8ad1e721e53b"
down_revision = "009360f02c17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("full_name", sa.String(255)),
        sa.Column("bio", sa.Text()),
        sa.Column("institution", sa.String(255)),
        sa.Column("academic_role", sa.String(100)),
        sa.Column("avatar_url", sa.String(2048)),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("language", sa.String(2), server_default="en", nullable=False),
        sa.Column("theme", sa.String(10), server_default="system", nullable=False),
        sa.Column(
            "privacy_default", sa.String(10), server_default="private", nullable=False
        ),
        sa.Column(
            "allow_external_ai", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.CheckConstraint("language IN ('en', 'bn')", name="ck_preferences_language"),
        sa.CheckConstraint(
            "theme IN ('system', 'light', 'dark')", name="ck_preferences_theme"
        ),
        sa.CheckConstraint(
            "privacy_default IN ('private', 'public')", name="ck_preferences_privacy"
        ),
    )
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_jti", sa.String(36), nullable=False),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.String(512)),
        sa.Column(
            "is_revoked", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index(
        "ix_user_sessions_token_jti", "user_sessions", ["token_jti"], unique=True
    )
    op.create_table(
        "verification_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('email_verification', 'password_reset')",
            name="ck_verification_token_purpose",
        ),
    )
    op.create_index(
        "ix_verification_tokens_token_hash",
        "verification_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50)),
        sa.Column("resource_id", sa.String(100)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("details", sa.JSON()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    for column in ("user_id", "action", "created_at"):
        op.create_index(f"ix_audit_logs_{column}", "audit_logs", [column])

    op.execute("INSERT INTO profiles (user_id) SELECT id FROM users")
    op.execute("INSERT INTO user_preferences (user_id) SELECT id FROM users")


def downgrade() -> None:
    for table in (
        "audit_logs",
        "verification_tokens",
        "user_sessions",
        "user_preferences",
        "profiles",
    ):
        op.drop_table(table)
