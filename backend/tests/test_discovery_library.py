import asyncio
import os
import sqlite3
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.schema import CreateSchema, DropSchema

from app.database.database import Base
from app.database.discovery_database import create_discovery_engine
from app.models.paper import Paper, PaperSource, UserPaper
from app.models.research_paper import ResearchPaper
from app.models.user import User
from app.modules.discovery.library import PaperIdentityConflict, save_to_library
from app.modules.discovery.schemas import DiscoveryPaper
from app.repositories.paper_repository import PaperRepository


@pytest.fixture
def provider_paper():
    return DiscoveryPaper(
        title="A Public Research Paper",
        authors=["Ada Lovelace", "Grace Hopper"],
        doi="https://doi.org/10.1234/Research",
        url="https://example.com/works/A",
        source="openalex",
        external_id="W100",
    )


def test_two_owners_share_the_catalog_and_have_private_library_items(
    db, test_user, another_user, provider_paper
):
    first = save_to_library(db, test_user.id, provider_paper)
    repeated = save_to_library(db, test_user.id, provider_paper)
    crossref = provider_paper.model_copy(
        update={"source": "crossref", "external_id": "10.1234/research"}
    )
    second = save_to_library(db, another_user.id, crossref)

    assert not first.already_saved and not second.already_saved
    assert repeated.already_saved and repeated.user_paper_id == first.user_paper_id
    assert first.paper_id == second.paper_id
    assert first.user_paper_id != second.user_paper_id
    canonical = db.get(Paper, first.paper_id)
    assert canonical.doi == "10.1234/research"
    assert [
        (entry.author.display_name, entry.position) for entry in canonical.authors
    ] == [
        ("Ada Lovelace", 0),
        ("Grace Hopper", 1),
    ]
    assert {source.provider for source in canonical.sources} == {"crossref", "openalex"}

    repo = PaperRepository(db)
    first_projection = repo.get_all_papers(test_user.id)
    second_projection = repo.get_all_papers(another_user.id)
    assert len(first_projection) == len(second_projection) == 1
    assert repo.get_paper_by_id(first_projection[0].id, another_user.id) is None
    assert repo.get_paper_by_id(second_projection[0].id, test_user.id) is None

    repo.delete_paper(first_projection[0])
    assert db.get(UserPaper, first.user_paper_id) is None
    assert db.get(UserPaper, second.user_paper_id) is not None
    assert db.get(Paper, first.paper_id) is not None
    assert repo.get_all_papers(test_user.id) == []
    resaved = save_to_library(db, test_user.id, provider_paper)
    assert resaved.paper_id == first.paper_id
    assert not resaved.already_saved


def test_conflicting_provider_id_cannot_relink_a_public_work(
    db, test_user, another_user, provider_paper
):
    first = save_to_library(db, test_user.id, provider_paper)
    different = provider_paper.model_copy(
        update={"doi": "10.1234/different", "external_id": "W200"}
    )
    other = save_to_library(db, test_user.id, different)
    assert first.paper_id != other.paper_id
    with pytest.raises(PaperIdentityConflict):
        conflicting = provider_paper.model_copy(update={"doi": different.doi})
        save_to_library(db, another_user.id, conflicting)
    assert (
        db.scalar(select(PaperSource.paper_id).where(PaperSource.external_id == "W100"))
        == first.paper_id
    )
    assert PaperRepository(db).get_all_papers(another_user.id) == []


def test_existing_provider_id_can_gain_a_verified_doi(db, test_user, provider_paper):
    first = save_to_library(
        db, test_user.id, provider_paper.model_copy(update={"doi": None})
    )
    repeated = save_to_library(db, test_user.id, provider_paper)
    assert repeated.already_saved and repeated.paper_id == first.paper_id
    assert db.get(Paper, first.paper_id).doi == "10.1234/research"


def test_unique_collision_retries_without_retaining_a_partial_save(
    db, test_user, provider_paper, monkeypatch
):
    original_commit = db.commit
    attempts = 0

    def commit():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise IntegrityError(
                "INSERT",
                {},
                sqlite3.IntegrityError("UNIQUE constraint failed: papers.doi"),
            )
        original_commit()

    monkeypatch.setattr(db, "commit", commit)
    result = save_to_library(db, test_user.id, provider_paper)
    assert attempts == 2
    assert result.saved and not result.already_saved
    assert db.scalar(select(func.count()).select_from(Paper)) == 1
    assert db.scalar(select(func.count()).select_from(PaperSource)) == 1
    assert db.scalar(select(func.count()).select_from(ResearchPaper)) == 1
    assert db.scalar(select(func.count()).select_from(UserPaper)) == 1


def test_postgresql_simultaneous_saves_share_one_library_item(provider_paper):
    database_url = os.getenv("TEST_MIGRATION_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_MIGRATION_DATABASE_URL to a disposable PostgreSQL DB")

    asyncio.run(_exercise_concurrent_saves(database_url, provider_paper))


async def _exercise_concurrent_saves(database_url, provider_paper):
    engine = create_discovery_engine(database_url)
    schema = f"discovery_race_{uuid4().hex}"
    isolated_engine = engine.execution_options(schema_translate_map={None: schema})
    barrier = asyncio.Barrier(2)
    synchronized_tasks = set()

    def wait_after_first_doi_lookup(
        connection, cursor, statement, parameters, context, executemany
    ):
        if statement.startswith("SELECT ") and "papers.doi = " in statement:
            task = asyncio.current_task()
            if task not in synchronized_tasks:
                synchronized_tasks.add(task)
                connection.connection.run_async(lambda _: barrier.wait())

    async def save(user_id):
        async with AsyncSession(isolated_engine) as race_db:
            result = await race_db.run_sync(save_to_library, user_id, provider_paper)
            assert asyncio.current_task() in synchronized_tasks
            return result

    try:
        assert engine.dialect.name == "postgresql"
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
        try:
            async with isolated_engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with AsyncSession(isolated_engine) as race_db:
                user = User(
                    username="race-user",
                    email="race@example.com",
                    hashed_password="test",
                )
                race_db.add(user)
                await race_db.flush()
                user_id = user.id
                await race_db.commit()

            event.listen(
                isolated_engine.sync_engine,
                "after_cursor_execute",
                wait_after_first_doi_lookup,
            )
            async with asyncio.timeout(20):
                results = await asyncio.gather(save(user_id), save(user_id))

            assert sorted(result.already_saved for result in results) == [False, True]
            assert results[0].paper_id == results[1].paper_id
            assert results[0].user_paper_id == results[1].user_paper_id
            async with AsyncSession(isolated_engine) as race_db:
                for table in (Paper, PaperSource, ResearchPaper, UserPaper):
                    assert (
                        await race_db.scalar(select(func.count()).select_from(table))
                        == 1
                    )
        finally:
            async with engine.begin() as connection:
                await connection.execute(DropSchema(schema, cascade=True))
    finally:
        await engine.dispose()
