"""Real PostgreSQL checks for project serialization and database ACLs."""

import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session

from alembic import command
from app.database.discovery_database import create_discovery_engine
from app.models.assistant import Conversation
from app.models.library import Collection
from app.models.paper import UserPaper
from app.models.projects import ProjectPaper, ProjectTask, ResearchNote, ResearchProject
from app.models.research_paper import ResearchPaper
from app.models.user import User
from app.modules.projects import service
from app.modules.projects.schemas import (
    CreateProject,
    CreateTask,
    UpdateProject,
    UpdateTask,
)
from tests import test_identity_postgresql
from tests.test_migrations import migration_config

identity_database = test_identity_postgresql.identity_database


@pytest.fixture
def project_users(identity_database):
    suffix = uuid4().hex
    with Session(identity_database) as db:
        users = [
            User(
                username=f"project-{suffix}-{n}",
                email=f"project-{suffix}-{n}@example.com",
                hashed_password="test",
            )
            for n in range(2)
        ]
        db.add_all(users)
        db.commit()
        ids = [user.id for user in users]
    try:
        yield ids
    finally:
        with Session(identity_database) as db:
            db.execute(delete(ResearchPaper).where(ResearchPaper.owner_id.in_(ids)))
            db.execute(delete(User).where(User.id.in_(ids)))
            db.commit()


def test_postgresql_project_tasks_serialize_progress_and_revision(
    identity_database, project_users
):
    owner = project_users[0]

    async def run():
        engine = create_discovery_engine(identity_database.url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as db:
                project = await service.create_project(
                    db, owner, CreateProject(title="Concurrent workspace")
                )
                pid = project["id"]
                first = await service.create_task(
                    db, owner, pid, CreateTask(title="Evidence", is_milestone=True)
                )
                second = await service.create_task(
                    db, owner, pid, CreateTask(title="Review")
                )

            async def finish(tid):
                async with factory() as db:
                    return await service.update_task(
                        db, owner, pid, tid, UpdateTask(status="done")
                    )

            await asyncio.gather(finish(first["id"]), finish(second["id"]))
            async with factory() as db:
                project = await db.scalar(
                    select(ResearchProject).where(
                        ResearchProject.id == pid, ResearchProject.user_id == owner
                    )
                )
                assert project.progress_percent == 100
                assert project.status == "completed"
                revision = project.revision

            async def rename(title):
                async with factory() as db:
                    try:
                        await service.update_project(
                            db,
                            owner,
                            pid,
                            UpdateProject(title=title, expected_revision=revision),
                        )
                        return 200
                    except HTTPException as error:
                        return error.status_code

            assert sorted(await asyncio.gather(rename("First"), rename("Second"))) == [
                200,
                409,
            ]
            return pid
        finally:
            await engine.dispose()

    asyncio.run(run())
    config = migration_config(
        identity_database.url.render_as_string(hide_password=False)
    )
    with pytest.raises(RuntimeError, match="purge research projects"):
        command.downgrade(config, "c9e30f7b521d")


def test_postgresql_project_foreign_keys_and_set_null_preserve_private_records(
    identity_database, project_users
):
    owner, foreign = project_users
    with Session(identity_database) as db:
        collection = Collection(user_id=owner, name="Sources")
        legacy = ResearchPaper(owner_id=owner, title="Private source")
        db.add_all([collection, legacy])
        db.flush()
        paper = UserPaper(user_id=owner, legacy_paper_id=legacy.id)
        project = ResearchProject(
            user_id=owner, title="Research", objectives=[], collection_id=collection.id
        )
        db.add_all([paper, project])
        db.commit()
        pid, cid, uid = project.id, collection.id, paper.id

        invalid = [
            ResearchProject(
                user_id=foreign, title="Blocked", objectives=[], collection_id=cid
            ),
            ProjectPaper(user_id=foreign, project_id=pid, user_paper_id=uid),
            ResearchNote(user_id=foreign, project_id=pid, title="Blocked", content=""),
            ProjectTask(user_id=foreign, project_id=pid, title="Blocked"),
            Conversation(
                user_id=foreign,
                project_id=pid,
                title="Blocked",
                scope_type="single_paper",
                scope_paper_ids=[],
            ),
        ]
        for row in invalid:
            db.add(row)
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()

        # A valid project of the second user still cannot reference A's paper.
        other = ResearchProject(user_id=foreign, title="Other", objectives=[])
        db.add(other)
        db.commit()
        other_id = other.id
        for row in [
            ProjectPaper(user_id=foreign, project_id=other_id, user_paper_id=uid),
            ResearchNote(
                user_id=foreign,
                project_id=other_id,
                user_paper_id=uid,
                title="Blocked",
                content="",
            ),
        ]:
            db.add(row)
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()

        note = ResearchNote(
            user_id=owner,
            project_id=pid,
            user_paper_id=uid,
            title="Retained",
            content="Private note",
        )
        chat = Conversation(
            user_id=owner,
            project_id=pid,
            title="Retained chat",
            scope_type="single_paper",
            scope_paper_ids=[uid],
        )
        db.add_all(
            [note, chat, ProjectPaper(user_id=owner, project_id=pid, user_paper_id=uid)]
        )
        db.commit()
        nid, chat_id = note.id, chat.id
        db.execute(
            delete(Collection).where(Collection.id == cid, Collection.user_id == owner)
        )
        db.commit()
        db.expire_all()
        assert db.get(ResearchProject, pid).collection_id is None
        db.execute(
            delete(UserPaper).where(UserPaper.id == uid, UserPaper.user_id == owner)
        )
        db.commit()
        db.expire_all()
        assert db.get(ResearchNote, nid).user_paper_id is None
        assert db.get(ResearchNote, nid).content == "Private note"
        db.execute(
            delete(ResearchProject).where(
                ResearchProject.id == pid, ResearchProject.user_id == owner
            )
        )
        db.commit()
        db.expire_all()
        assert db.get(ResearchNote, nid) is None
        assert db.get(Conversation, chat_id).project_id is None
        assert db.get(Conversation, chat_id).user_id == owner
