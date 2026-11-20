"""Real PostgreSQL checks for administrative lock ordering and job fencing."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session

from alembic import command
from app.core.time import utc_now
from app.database.discovery_database import create_discovery_engine
from app.models.audit_log import AuditLog
from app.models.document_intelligence import ProcessingJob
from app.models.library import Document
from app.models.research_paper import ResearchPaper
from app.models.session import Session as UserSession
from app.models.user import User
from app.modules.admin.dependencies import AdminPrincipal
from app.modules.admin.service import requeue, revoke_sessions
from app.modules.documents.processing import DocumentProcessor
from tests import test_identity_postgresql
from tests.modules.ai.test_assistant import indexed_paper
from tests.test_migrations import migration_config

identity_database = test_identity_postgresql.identity_database


@pytest.fixture
def operational_accounts(identity_database):
    suffix = uuid4().hex
    with Session(identity_database) as db:
        users = [
            User(
                username=f"ops-{suffix}-{n}",
                email=f"ops-{suffix}-{n}@example.com",
                hashed_password="test",
                is_admin=n < 2,
            )
            for n in range(3)
        ]
        db.add_all(users)
        db.flush()
        sessions = [
            UserSession(
                user_id=user.id,
                token_jti=str(uuid4()),
                expires_at=utc_now() + timedelta(minutes=30),
            )
            for user in users[:2]
        ]
        db.add_all(sessions)
        db.commit()
        ids = [user.id for user in users]
        principals = [
            AdminPrincipal(row.user_id, row.id, row.token_jti) for row in sessions
        ]
    try:
        yield ids, principals
    finally:
        with Session(identity_database) as db:
            db.execute(delete(ResearchPaper).where(ResearchPaper.owner_id.in_(ids)))
            db.execute(delete(User).where(User.id.in_(ids)))
            db.commit()


def test_concurrent_administrators_revoke_each_other_without_deadlock(
    identity_database, operational_accounts
):
    ids, principals = operational_accounts

    async def run():
        engine = create_discovery_engine(identity_database.url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:

            async def revoke(actor, target):
                async with factory() as db:
                    try:
                        return await revoke_sessions(db, actor, target)
                    except HTTPException as error:
                        return error.status_code

            async with asyncio.timeout(20):
                results = await asyncio.gather(
                    revoke(principals[0], ids[1]), revoke(principals[1], ids[0])
                )
            successful = [item for item in results if isinstance(item, dict)]
            assert len(successful) == 1 and results.count(401) == 1
            assert successful[0]["revoked_sessions"] == 1
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_concurrent_admin_requeue_creates_one_new_version_and_fences_old_job(
    identity_database, operational_accounts
):
    ids, principals = operational_accounts
    with Session(identity_database) as db:
        _, document, _ = indexed_paper(db, ids[2])
        document.status = "failed"
        old = ProcessingJob(
            user_id=ids[2],
            document_id=document.id,
            document_version=1,
            status="failed",
            attempts=5,
            last_error="Private upstream detail must not escape",
        )
        db.add(old)
        db.commit()
        old_id, document_id = old.id, document.id

    async def run():
        engine = create_discovery_engine(identity_database.url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        dispatches = []

        class Dispatcher:
            async def enqueue(self, job_id):
                dispatches.append(job_id)

        try:

            async def again():
                async with factory() as db:
                    try:
                        return await requeue(db, principals[0], old_id, Dispatcher())
                    except HTTPException as error:
                        return error.status_code

            async with asyncio.timeout(20):
                results = await asyncio.gather(again(), again())
            successful = [item for item in results if isinstance(item, dict)]
            assert len(successful) == 1 and results.count(409) == 1
            fresh_id = successful[0]["id"]
            assert fresh_id != old_id and dispatches == [fresh_id]
            assert successful[0]["document_version"] == 2
            # A delayed old queue delivery cannot claim the replacement version.
            await DocumentProcessor(factory).process_job(old_id, owner_id=ids[2])
            async with factory() as db:
                current = await db.get(Document, document_id)
                fresh = await db.get(ProcessingJob, fresh_id)
                old = await db.get(ProcessingJob, old_id)
                assert current.version == 2 and current.status == "pending"
                assert fresh.status == "queued" and fresh.attempts == 0
                assert old.status == "failed" and old.attempts == 5
                logs = list(
                    await db.scalars(
                        select(AuditLog).where(
                            AuditLog.action == "admin.job.requeued",
                            AuditLog.user_id == ids[0],
                        )
                    )
                )
                assert len(logs) == 1
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_admin_privilege_downgrade_requires_explicit_revocation(
    identity_database, operational_accounts
):
    config = migration_config(
        identity_database.url.render_as_string(hide_password=False)
    )
    with pytest.raises(RuntimeError, match="Revoke administrator privileges"):
        command.downgrade(config, "e1c25d9b743f")
    with identity_database.connect() as connection:
        assert (
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            == "f2d36e0c854a"
        )
