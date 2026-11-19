"""Offline generations against PostgreSQL exercise cross-process quota locking."""

import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session

from app.database.discovery_database import create_discovery_engine
from app.models.analysis import Analysis, ComparisonPaper
from app.models.assistant import AIUsage, Conversation
from app.models.library import Document
from app.models.research_paper import ResearchPaper
from app.models.user import User
from app.models.writing import Citation, WritingVersion
from app.modules.ai.gateway import AIProviderGateway, OfflineProvider
from app.modules.ai.schemas import Question
from app.modules.ai.service import send_message
from app.modules.analysis import service as analysis_service
from app.modules.analysis.schemas import CompareRequest, Options
from app.modules.writing import service as writing_service
from app.modules.writing.schemas import CreateDocument, UpdateDocument
from tests import test_identity_postgresql
from tests.modules.ai.test_assistant import indexed_paper
from tests.modules.analysis.test_routes import paper
from tests.test_migrations import migration_config

identity_database = test_identity_postgresql.identity_database


def test_postgresql_writing_concurrent_saves_ownership_and_safe_downgrade(
    identity_database,
):
    from sqlalchemy.exc import IntegrityError

    from alembic import command

    with Session(identity_database) as db:
        suffix = uuid4().hex
        users = [
            User(
                username=f"writing-{suffix}-{n}",
                email=f"writing-{suffix}-{n}@example.com",
                hashed_password="test",
            )
            for n in range(2)
        ]
        db.add_all(users)
        db.commit()
        owner, foreign = users[0].id, users[1].id
        item, _, _ = paper(db, owner)
        paper_id = item.id

    async def run():
        engine = create_discovery_engine(identity_database.url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as db:
                result = await writing_service.create(
                    db,
                    owner,
                    CreateDocument(
                        doc_type="thesis",
                        title="Concurrent",
                        content_markdown="Initial.",
                    ),
                )
                did = result["id"]

            async def save(text):
                async with factory() as db:
                    try:
                        return await writing_service.update(
                            db,
                            owner,
                            did,
                            UpdateDocument(
                                content_markdown=text,
                                expected_revision=1,
                                create_version=True,
                            ),
                        )
                    except HTTPException as error:
                        return error.status_code

            results = await asyncio.gather(save("First save."), save("Second save."))
            assert results.count(409) == 1
            async with factory() as db:
                versions = list(
                    await db.scalars(
                        select(WritingVersion.version_number)
                        .where(
                            WritingVersion.user_id == owner,
                            WritingVersion.writing_document_id == did,
                        )
                        .order_by(WritingVersion.version_number)
                    )
                )
                assert versions == [1, 2]
            return did
        finally:
            await engine.dispose()

    try:
        did = asyncio.run(run())
        config = migration_config(
            identity_database.url.render_as_string(hide_password=False)
        )
        with pytest.raises(RuntimeError, match="purge writing"):
            command.downgrade(config, "a7c14e5f902b")
        with Session(identity_database) as db:
            db.add(
                WritingVersion(
                    user_id=foreign,
                    writing_document_id=did,
                    version_number=99,
                    title="Blocked",
                    content_markdown="private",
                    outline=[],
                    cited_citation_ids=[],
                )
            )
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
            db.add(
                Citation(
                    user_id=foreign,
                    user_paper_id=paper_id,
                    cite_key="blocked",
                    identity_key="a" * 64,
                    title_year_key="b" * 64,
                    title="Blocked",
                    authors=[],
                    entry_type="misc",
                )
            )
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
    finally:
        with Session(identity_database) as db:
            db.execute(
                delete(ResearchPaper).where(
                    ResearchPaper.owner_id.in_([owner, foreign])
                )
            )
            db.execute(delete(User).where(User.id.in_([owner, foreign])))
            db.commit()


def test_postgresql_analysis_owner_constraints_source_deletion_and_downgrade(
    identity_database,
):
    from sqlalchemy.exc import IntegrityError

    from alembic import command

    with Session(identity_database) as db:
        suffix = uuid4().hex
        users = [
            User(
                username=f"analysis-{suffix}-{n}",
                email=f"analysis-{suffix}-{n}@example.com",
                hashed_password="test",
            )
            for n in range(2)
        ]
        db.add_all(users)
        db.commit()
        owner, foreign = users[0].id, users[1].id
        first, document, _ = paper(db, owner)
        second, _, _ = paper(db, owner)
        other, foreign_doc, _ = paper(db, foreign)
        paper_ids = [first.id, second.id]
        doc_id, foreign_doc_id, other_id = document.id, foreign_doc.id, other.id

    async def run():
        engine = create_discovery_engine(identity_database.url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        gateway = AIProviderGateway()
        try:
            async with factory() as db:
                result = await analysis_service.analyze(
                    db, owner, paper_ids[0], Options(provider="offline"), gateway
                )
                assert result["status"] == "completed" and result["is_stale"] is False
            async with factory() as db:
                comparison = await analysis_service.compare(
                    db,
                    owner,
                    CompareRequest(user_paper_ids=paper_ids, provider="offline"),
                    gateway,
                )
                assert len(comparison["research_gaps"]) == 1
                return result["id"], comparison["id"]
        finally:
            await engine.dispose()

    try:
        analysis_id, comparison_id = asyncio.run(run())
        config = migration_config(
            identity_database.url.render_as_string(hide_password=False)
        )
        with pytest.raises(RuntimeError, match="purge paper intelligence"):
            command.downgrade(config, "f6b92d04a173")
        with Session(identity_database) as db:
            db.add(
                ComparisonPaper(
                    user_id=owner, comparison_id=comparison_id, user_paper_id=other_id
                )
            )
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
            analysis = db.scalar(
                select(Analysis).where(
                    Analysis.id == analysis_id, Analysis.user_id == owner
                )
            )
            analysis.document_id = foreign_doc_id
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
            db.execute(
                delete(Document).where(Document.id == doc_id, Document.user_id == owner)
            )
            db.commit()
            assert (
                db.scalar(
                    select(Analysis.document_id).where(
                        Analysis.id == analysis_id, Analysis.user_id == owner
                    )
                )
                is None
            )
    finally:
        with Session(identity_database) as db:
            db.execute(
                delete(ResearchPaper).where(
                    ResearchPaper.owner_id.in_([owner, foreign])
                )
            )
            db.execute(delete(User).where(User.id.in_([owner, foreign])))
            db.commit()


@pytest.mark.parametrize("same_request", [False, True])
def test_postgresql_atomic_quota_and_replay(identity_database, same_request):
    with Session(identity_database) as db:
        suffix = uuid4().hex
        user = User(
            username=suffix, email=f"{suffix}@example.com", hashed_password="test"
        )
        db.add(user)
        db.commit()
        owner = user.id
        paper, _, _ = indexed_paper(db, owner)
        conversation = Conversation(
            user_id=owner,
            title="Atomic quota",
            language="en",
            scope_type="single_paper",
            scope_paper_ids=[paper.id],
        )
        db.add(conversation)
        db.commit()
        conversation_id = conversation.id

    async def run():
        engine = create_discovery_engine(identity_database.url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        gateway = AIProviderGateway()
        gate = asyncio.Event()
        calls = []

        class SlowOffline(OfflineProvider):
            async def generate(self, messages, passages):
                calls.append(1)
                await gate.wait()
                return await super().generate(messages, passages)

        gateway.offline = SlowOffline()
        request_id = uuid4()

        async def send():
            async with factory() as db:
                try:
                    return await send_message(
                        db,
                        owner,
                        conversation_id,
                        Question(
                            content="photosynthesis sunlight",
                            provider="offline",
                            request_id=request_id if same_request else uuid4(),
                        ),
                        gateway,
                    )
                except HTTPException as error:
                    return error.status_code

        try:
            tasks = [asyncio.create_task(send()) for _ in range(4)]
            # Wait for three rejected reservations; release the sole provider call.
            done = []
            async with asyncio.timeout(15):
                while len(done) < 3:
                    done = [task for task in tasks if task.done()]
                    await asyncio.sleep(0.01)
            gate.set()
            results = await asyncio.gather(*tasks)
            assert len([result for result in results if isinstance(result, dict)]) == 1
            assert results.count(409 if same_request else 429) == 3
            assert len(calls) == 1
            async with factory() as db:
                assert (
                    await db.scalar(
                        select(func.count(AIUsage.id)).where(AIUsage.user_id == owner)
                    )
                    == 1
                )
        finally:
            gate.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            await engine.dispose()

    try:
        asyncio.run(run())
        from alembic import command

        with pytest.raises(RuntimeError, match="Export or purge AI"):
            command.downgrade(
                migration_config(
                    identity_database.url.render_as_string(hide_password=False)
                ),
                "e5a14c7b9d32",
            )
    finally:
        with Session(identity_database) as db:
            # Legacy papers use the existing explicit account-deletion policy.
            db.execute(delete(ResearchPaper).where(ResearchPaper.owner_id == owner))
            db.execute(delete(User).where(User.id == owner))
            db.commit()
