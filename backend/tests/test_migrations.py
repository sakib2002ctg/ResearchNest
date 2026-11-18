import io
import os
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from alembic import command


def migration_config(url=None):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    if url is not None:
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def test_migration_chain_is_linear_and_generates_postgresql_ddl():
    config = migration_config("postgresql://localhost/offline")
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["b21c4b995d13"]
    assert [revision.revision for revision in script.walk_revisions()] == [
        "b21c4b995d13",
        "8ad1e721e53b",
        "009360f02c17",
        "146022ae25cb",
        "f49273ec7757",
    ]

    config.output_buffer = io.StringIO()
    command.upgrade(config, "head", sql=True)
    upgrade_sql = config.output_buffer.getvalue()
    assert (
        upgrade_sql.index("CREATE TABLE research_papers")
        < upgrade_sql.index("CREATE TABLE users")
        < upgrade_sql.index("ALTER TABLE research_papers ADD COLUMN owner_id")
    )
    assert "FOREIGN KEY(owner_id) REFERENCES users (id)" in upgrade_sql

    config.output_buffer = io.StringIO()
    command.downgrade(config, "head:base", sql=True)
    downgrade_sql = config.output_buffer.getvalue()
    assert (
        downgrade_sql.index("DROP CONSTRAINT fk_research_papers_owner_id_users")
        < (downgrade_sql.index("DROP TABLE users"))
        < downgrade_sql.index("DROP TABLE research_papers")
    )


def test_postgresql_migration_round_trip():
    # Must point to a disposable, empty database, never a development/production DB.
    url = os.getenv("TEST_MIGRATION_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set TEST_MIGRATION_DATABASE_URL to an empty disposable PostgreSQL DB"
        )

    engine = create_engine(url)
    try:
        assert engine.dialect.name == "postgresql"
        assert not inspect(engine).get_table_names(), "Migration test DB must be empty"
        config = migration_config(url)

        command.upgrade(config, "head")
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == {
            "users",
            "research_papers",
            "alembic_version",
            "profiles",
            "user_preferences",
            "user_sessions",
            "verification_tokens",
            "audit_logs",
        }
        assert {
            column["name"] for column in inspector.get_columns("research_papers")
        } == {
            "id",
            "title",
            "authors",
            "abstract",
            "source",
            "url",
            "owner_id",
            "created_at",
        }
        assert inspector.get_foreign_keys("research_papers")[0]["referred_table"] == (
            "users"
        )
        owner_column = next(
            c
            for c in inspector.get_columns("research_papers")
            if c["name"] == "owner_id"
        )
        assert owner_column["nullable"] is False
        with engine.begin() as connection:
            assert (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                == "b21c4b995d13"
            )
            user_id = connection.execute(
                text(
                    "INSERT INTO users (username, email, hashed_password) "
                    "VALUES ('migration-test', 'migration@example.com', 'test-hash') "
                    "RETURNING id"
                )
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO research_papers (title, owner_id) "
                    "VALUES ('Migration round trip', :owner_id)"
                ),
                {"owner_id": user_id},
            )

        command.downgrade(config, "base")
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT count(*) FROM alembic_version")
                ).scalar()
                == 0
            )
        command.upgrade(config, "head")
        assert "user_sessions" in inspect(engine).get_table_names()
        command.downgrade(config, "base")

        # A database already at the Phase 01A revision keeps its data on upgrade.
        command.upgrade(config, "009360f02c17")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, username, email, hashed_password) "
                    "VALUES (42, 'legacy', 'legacy@example.com', 'legacy-hash')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO research_papers (title, owner_id) "
                    "VALUES ('Legacy paper', 42)"
                )
            )
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT language, allow_external_ai "
                    "FROM user_preferences WHERE user_id = 42"
                )
            ).one() == ("en", False)
            assert (
                connection.execute(
                    text("SELECT count(*) FROM profiles WHERE user_id = 42")
                ).scalar_one()
                == 1
            )
            assert (
                connection.execute(
                    text("SELECT title FROM research_papers WHERE owner_id = 42")
                ).scalar_one()
                == "Legacy paper"
            )
            assert (
                connection.execute(
                    text("SELECT is_verified FROM users WHERE id = 42")
                ).scalar_one()
                is False
            )
            assert (
                connection.execute(
                    text("SELECT created_at FROM research_papers WHERE owner_id = 42")
                ).scalar_one()
                is not None
            )
        command.downgrade(config, "009360f02c17")
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT hashed_password FROM users WHERE id = 42")
                ).scalar_one()
                == "legacy-hash"
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM research_papers WHERE owner_id = 42")
                ).scalar_one()
                == 1
            )
        command.downgrade(config, "base")
        # Alembic retains its empty bookkeeping table; leave the disposable DB
        # genuinely empty so the round-trip test is repeatable.
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
    finally:
        engine.dispose()
