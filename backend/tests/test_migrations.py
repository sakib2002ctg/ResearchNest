import io
import os
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command


def migration_config(url=None):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    if url is not None:
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def test_migration_chain_is_linear_and_generates_postgresql_ddl():
    config = migration_config("postgresql://localhost/offline")
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["d429e3a5b6c1"]
    assert [revision.revision for revision in script.walk_revisions()] == [
        "d429e3a5b6c1",
        "c83a2f1a4d71",
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
    assert (
        "FOREIGN KEY(legacy_paper_id) REFERENCES research_papers (id) ON DELETE CASCADE"
        in upgrade_sql
    )
    assert (
        "FOREIGN KEY(user_id, legacy_paper_id) "
        "REFERENCES research_papers (owner_id, id) ON DELETE CASCADE"
    ) in upgrade_sql

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
            "papers",
            "authors",
            "paper_authors",
            "paper_sources",
            "user_papers",
            "collections",
            "collection_papers",
            "tags",
            "paper_tags",
            "annotations",
            "documents",
            "pdf_deletions",
        }
        assert {
            (
                tuple(fk["constrained_columns"]),
                fk["referred_table"],
                fk["options"].get("ondelete"),
            )
            for fk in inspector.get_foreign_keys("user_papers")
        } == {
            (("user_id",), "users", "CASCADE"),
            (("paper_id",), "papers", "CASCADE"),
            (("user_id", "legacy_paper_id"), "research_papers", "CASCADE"),
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
                == "d429e3a5b6c1"
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

        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO pdf_deletions (storage_key) "
                    "VALUES ('pending-deletion.pdf')"
                )
            )
        with pytest.raises(RuntimeError, match="purge stored PDFs"):
            command.downgrade(config, "c83a2f1a4d71")
        with engine.begin() as connection:
            assert (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                == "d429e3a5b6c1"
            )
            connection.execute(text("DELETE FROM pdf_deletions"))

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
        command.upgrade(config, "c83a2f1a4d71")
        with engine.begin() as connection:
            canonical_id = connection.execute(
                text(
                    "INSERT INTO papers (title) "
                    "VALUES ('Discovered paper') RETURNING id"
                )
            ).scalar_one()
            discovery_projection_id = connection.execute(
                text(
                    "INSERT INTO research_papers (title, owner_id) "
                    "VALUES ('Discovered paper', 42) RETURNING id"
                )
            ).scalar_one()
            discovery_link_id = connection.execute(
                text(
                    "INSERT INTO user_papers "
                    "(user_id, paper_id, legacy_paper_id, note) "
                    "VALUES (42, :canonical, :projection, 'Private saved note') "
                    "RETURNING id"
                ),
                {"canonical": canonical_id, "projection": discovery_projection_id},
            ).scalar_one()
        command.upgrade(config, "head")
        with engine.begin() as connection:
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
                    text(
                        "SELECT title FROM research_papers "
                        "WHERE owner_id = 42 AND title = 'Legacy paper'"
                    )
                ).scalar_one()
                == "Legacy paper"
            )
            assert (
                connection.execute(
                    text("SELECT is_verified FROM users WHERE id = 42")
                ).scalar_one()
                is False
            )
            assert connection.execute(
                text(
                    "SELECT u.user_id, u.paper_id, u.saved_at = r.created_at, "
                    "u.reading_status, u.reading_progress_percent "
                    "FROM research_papers AS r "
                    "JOIN user_papers AS u ON u.legacy_paper_id = r.id "
                    "WHERE r.title = 'Legacy paper'"
                )
            ).one() == (42, None, True, "unread", 0)
            assert connection.execute(
                text(
                    "SELECT id, paper_id, note FROM user_papers "
                    "WHERE legacy_paper_id = :projection"
                ),
                {"projection": discovery_projection_id},
            ).one() == (discovery_link_id, canonical_id, "Private saved note")
            connection.execute(
                text(
                    "INSERT INTO users (id, username, email, hashed_password) "
                    "VALUES (43, 'other', 'other@example.com', 'test')"
                )
            )
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(
                    text(
                        "INSERT INTO annotations "
                        "(user_id, user_paper_id, type, content) "
                        "VALUES (43, :paper_id, 'note', 'blocked')"
                    ),
                    {"paper_id": discovery_link_id},
                )
            _verify_workspace_cascades(connection, discovery_link_id)
        command.downgrade(config, "c83a2f1a4d71")
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT id, note FROM user_papers")
            ).one() == (
                discovery_link_id,
                "Private saved note",
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM research_papers WHERE owner_id = 42")
                ).scalar_one()
                == 2
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
                == 2
            )
        command.downgrade(config, "base")
        # Alembic retains its empty bookkeeping table; leave the disposable DB
        # genuinely empty so the round-trip test is repeatable.
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
    finally:
        engine.dispose()


def _verify_workspace_cascades(connection, discovery_link_id):
    collection_id = connection.execute(
        text("INSERT INTO collections (user_id, name) VALUES (42, 'Test') RETURNING id")
    ).scalar_one()
    tag_id = connection.execute(
        text("INSERT INTO tags (user_id, name) VALUES (42, 'Test') RETURNING id")
    ).scalar_one()
    private_link_id = connection.execute(
        text("SELECT id FROM user_papers WHERE paper_id IS NULL")
    ).scalar_one()
    connection.execute(
        text(
            "INSERT INTO collection_papers (user_id, collection_id, user_paper_id) "
            "VALUES (42, :collection_id, :paper_id)"
        ),
        {"collection_id": collection_id, "paper_id": discovery_link_id},
    )
    connection.execute(
        text(
            "INSERT INTO paper_tags (user_id, tag_id, user_paper_id) "
            "VALUES (42, :tag_id, :paper_id)"
        ),
        {"tag_id": tag_id, "paper_id": private_link_id},
    )
    connection.execute(
        text("DELETE FROM collections WHERE id = :id"), {"id": collection_id}
    )
    # Roll back the test deletion so the downgrade still encounters a private link.
    with connection.begin_nested() as savepoint:
        connection.execute(
            text("DELETE FROM user_papers WHERE id = :id"), {"id": private_link_id}
        )
        assert connection.execute(text("SELECT count(*) FROM paper_tags")).scalar() == 0
        savepoint.rollback()
    assert (
        connection.execute(text("SELECT count(*) FROM collection_papers")).scalar() == 0
    )
