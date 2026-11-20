"""PostgreSQL validates team ACL constraints and revocation ordering."""

import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, event, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session

from alembic import command
from app.database.discovery_database import create_discovery_engine
from app.models.assistant import AIUsage
from app.models.education import LearningProgress
from app.models.library import Collection, CollectionPaper
from app.models.paper import UserPaper
from app.models.research_paper import ResearchPaper
from app.models.teams import TeamMember, TeamNote, TeamSharedCollection, TeamWorkspace
from app.models.user import User
from app.modules.teams import repository, service
from app.modules.teams.schemas import AddMember, CreateNote, CreateWorkspace
from tests import test_identity_postgresql
from tests.test_migrations import migration_config

identity_database = test_identity_postgresql.identity_database


@pytest.fixture
def collaborators(identity_database):
    suffix = uuid4().hex
    with Session(identity_database) as db:
        users = [
            User(
                username=f"collab-{suffix}-{n}",
                email=f"collab-{suffix}-{n}@example.com",
                hashed_password="test",
            )
            for n in range(4)
        ]
        db.add_all(users)
        db.commit()
        ids = [user.id for user in users]
    try:
        yield ids
    finally:
        with Session(identity_database) as db:
            # The historical ResearchPaper FK intentionally restricts account
            # deletion; remove test-owned projections before their accounts.
            db.execute(delete(ResearchPaper).where(ResearchPaper.owner_id.in_(ids)))
            db.execute(delete(User).where(User.id.in_(ids)))
            db.commit()


def seed_workspace(db, owner, editor):
    workspace = TeamWorkspace(owner_id=owner, name="Concurrent research")
    db.add(workspace)
    db.flush()
    db.add_all(
        [
            TeamMember(
                workspace_id=workspace.id,
                user_id=owner,
                role="owner",
                owner_user_id=owner,
                invited_by_id=owner,
            ),
            TeamMember(
                workspace_id=workspace.id,
                user_id=editor,
                role="editor",
                invited_by_id=owner,
            ),
        ]
    )
    db.commit()
    return workspace.id


@pytest.mark.parametrize("operation", ["demote", "remove"])
def test_waiting_editor_rechecks_revoked_role_under_workspace_lock(
    identity_database, collaborators, operation
):
    owner, editor = collaborators[:2]
    with Session(identity_database) as db:
        wid = seed_workspace(db, owner, editor)

    async def run():
        engine = create_discovery_engine(identity_database.url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        attempted = asyncio.Event()
        try:
            async with factory() as revoker:
                await service.lock_workspace(revoker, owner, wid, "owner")
                # Hold the workspace lock while an editor starts a write. This
                # models membership changing after its UPDATE snapshot begins.
                predicate = (
                    TeamMember.workspace_id == wid,
                    TeamMember.user_id == editor,
                )
                if operation == "demote":
                    await revoker.execute(
                        update(TeamMember).where(*predicate).values(role="viewer")
                    )
                else:
                    await revoker.execute(delete(TeamMember).where(*predicate))

                def before_execute(
                    connection, cursor, statement, params, context, many
                ):
                    if statement.startswith("UPDATE team_workspaces "):
                        attempted.set()

                event.listen(
                    engine.sync_engine, "before_cursor_execute", before_execute
                )

                async def stale_editor():
                    async with factory() as writer:
                        try:
                            await service.create_note(
                                writer, editor, wid, CreateNote(title="Must be denied")
                            )
                            return 201
                        except HTTPException as error:
                            return error.status_code

                writing = asyncio.create_task(stale_editor())
                try:
                    await asyncio.wait_for(attempted.wait(), timeout=15)
                    await revoker.commit()
                    assert await asyncio.wait_for(writing, timeout=15) == (
                        403 if operation == "demote" else 404
                    )
                finally:
                    if not writing.done():
                        writing.cancel()
                        await asyncio.gather(writing, return_exceptions=True)
                    event.remove(
                        engine.sync_engine, "before_cursor_execute", before_execute
                    )
            async with factory() as db:
                assert (
                    await db.scalar(
                        select(func.count(TeamNote.id)).where(
                            TeamNote.workspace_id == wid
                        )
                    )
                    == 0
                )
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_team_database_ownership_membership_and_nullable_paper_integrity(
    identity_database, collaborators
):
    owner, editor, viewer, outsider = collaborators
    with Session(identity_database) as db:
        wid = seed_workspace(db, owner, editor)
        collection = Collection(user_id=editor, name="Explicitly shared sources")
        outside_collection = Collection(user_id=outsider, name="Private sources")
        legacy = ResearchPaper(owner_id=editor, title="Shared citation metadata")
        db.add_all([collection, outside_collection, legacy])
        db.flush()
        paper = UserPaper(user_id=editor, legacy_paper_id=legacy.id)
        db.add(paper)
        db.commit()
        cid, outside_cid, pid = collection.id, outside_collection.id, paper.id
        invalid = [
            TeamMember(
                workspace_id=wid, user_id=viewer, role="owner", owner_user_id=viewer
            ),
            TeamMember(workspace_id=wid, user_id=viewer, role="admin"),
            TeamSharedCollection(
                workspace_id=wid, collection_id=cid, shared_by_id=owner
            ),
            TeamSharedCollection(
                workspace_id=wid, collection_id=outside_cid, shared_by_id=outsider
            ),
            TeamNote(
                workspace_id=wid,
                author_id=owner,
                user_paper_id=2147483647,
                title="Missing paper link",
                content="Blocked",
            ),
        ]
        for row in invalid:
            db.add(row)
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()

        db.add(CollectionPaper(user_id=editor, collection_id=cid, user_paper_id=pid))
        db.add(
            TeamSharedCollection(
                workspace_id=wid, collection_id=cid, shared_by_id=editor
            )
        )
        note = TeamNote(
            workspace_id=wid,
            author_id=owner,
            user_paper_id=pid,
            title="Shared team note",
            content="Retained collaboration",
        )
        db.add(note)
        db.commit()
        nid = note.id
        db.execute(
            delete(TeamMember).where(
                TeamMember.workspace_id == wid, TeamMember.user_id == editor
            )
        )
        db.commit()
        assert (
            db.scalar(
                select(func.count(TeamSharedCollection.id)).where(
                    TeamSharedCollection.workspace_id == wid
                )
            )
            == 0
        )
        assert db.get(UserPaper, pid) is not None
        assert db.get(TeamNote, nid).content == "Retained collaboration"

        async def read_masked_note():
            engine = create_discovery_engine(identity_database.url)
            try:
                async with async_sessionmaker(
                    engine, expire_on_commit=False
                )() as session:
                    row = await repository.note(session, owner, wid, nid)
                    data = await repository.note_data(session, owner, wid, row)
                    assert data["user_paper_id"] is None
                    assert data["content"] == "Retained collaboration"
            finally:
                await engine.dispose()

        asyncio.run(read_masked_note())
        db.execute(
            delete(UserPaper).where(UserPaper.id == pid, UserPaper.user_id == editor)
        )
        db.commit()
        db.expire_all()
        assert db.get(TeamNote, nid).user_paper_id is None
        assert db.get(TeamNote, nid).author_id == owner


def test_workspace_owners_can_cross_invite_without_account_lock_deadlock(
    identity_database, collaborators, monkeypatch
):
    first, second = collaborators[:2]
    with Session(identity_database) as db:
        names = dict(
            db.execute(
                select(User.id, User.username).where(User.id.in_([first, second]))
            ).all()
        )

    async def run():
        engine = create_discovery_engine(identity_database.url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        ready = asyncio.Event()
        arrivals = set()
        original = service.lock_workspace
        try:
            async with factory() as db:
                first_workspace = await service.create_workspace(
                    db, first, CreateWorkspace(name="First research team")
                )
            async with factory() as db:
                second_workspace = await service.create_workspace(
                    db, second, CreateWorkspace(name="Second research team")
                )

            async def rendezvous(db, actor, wid, permission="write"):
                result = await original(db, actor, wid, permission)
                arrivals.add(actor)
                if len(arrivals) == 2:
                    ready.set()
                await asyncio.wait_for(ready.wait(), timeout=15)
                return result

            monkeypatch.setattr(service, "lock_workspace", rendezvous)

            async def invite(actor, workspace_id, target):
                async with factory() as db:
                    return await service.add_member(
                        db,
                        actor,
                        workspace_id,
                        AddMember(identifier=names[target], role="editor"),
                    )

            # Both writers hold their independent workspace locks before either
            # inserts a foreign-user membership FK. Actor account locks here
            # would form an ABBA cycle with the other FK's KEY SHARE lock.
            async with asyncio.timeout(25):
                results = await asyncio.gather(
                    invite(first, first_workspace["id"], second),
                    invite(second, second_workspace["id"], first),
                )
            assert {item["user_id"] for item in results} == {first, second}
            assert all(item["role"] == "editor" for item in results)
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_learning_progress_uniqueness_is_tenant_scoped(
    identity_database, collaborators
):
    owner, second = collaborators[:2]
    with Session(identity_database) as db:
        db.add_all(
            [
                LearningProgress(
                    user_id=owner,
                    guide_slug="three-pass-reading",
                    completed_step_ids=["orient"],
                ),
                LearningProgress(
                    user_id=second,
                    guide_slug="three-pass-reading",
                    completed_step_ids=[],
                ),
            ]
        )
        db.commit()
        db.add(
            LearningProgress(
                user_id=owner, guide_slug="three-pass-reading", completed_step_ids=[]
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert (
            db.scalar(
                select(func.count(LearningProgress.id)).where(
                    LearningProgress.user_id.in_([owner, second])
                )
            )
            == 2
        )


@pytest.mark.parametrize("kind", ["progress", "workspace", "usage"])
def test_phase11_downgrade_protects_existing_learning_team_and_usage_data(
    identity_database, collaborators, kind
):
    owner = collaborators[0]
    with Session(identity_database) as db:
        if kind == "progress":
            db.add(
                LearningProgress(
                    user_id=owner,
                    guide_slug="three-pass-reading",
                    completed_step_ids=["orient"],
                )
            )
        elif kind == "workspace":
            seed_workspace(db, owner, collaborators[1])
        else:
            db.add(
                AIUsage(
                    user_id=owner,
                    request_id=str(uuid4()),
                    request_fingerprint="a" * 64,
                    feature="education",
                    provider="offline",
                    model_name="extractive-v1",
                    status="completed",
                    reserved_tokens=100,
                    prompt_tokens=50,
                    completion_tokens=10,
                )
            )
        db.commit()
    config = migration_config(
        identity_database.url.render_as_string(hide_password=False)
    )
    with pytest.raises(RuntimeError, match="purge education and team data"):
        command.downgrade(config, "d0f14b8a632e")
    with identity_database.connect() as connection:
        assert (
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            == "f2d36e0c854a"
        )
