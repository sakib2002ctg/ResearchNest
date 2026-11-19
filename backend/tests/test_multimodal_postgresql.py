"""Live tenant constraints and deletion outbox for assets, with no provider calls."""

from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.models.library import Document
from app.models.multimodal import AssetChunkLink, AssetDeletion, DocumentAsset
from app.models.research_paper import ResearchPaper
from app.models.user import User
from tests import test_identity_postgresql
from tests.modules.analysis.test_routes import paper
from tests.test_migrations import migration_config

identity_database = test_identity_postgresql.identity_database


def test_asset_owner_constraints_raw_cascades_and_outbox(identity_database):
    with Session(identity_database) as db:
        suffix = uuid4().hex
        users = [
            User(
                username=f"visual-{suffix}-{i}",
                email=f"{suffix}-{i}@example.com",
                hashed_password="test",
            )
            for i in range(2)
        ]
        db.add_all(users)
        db.commit()
        owner, other = users[0].id, users[1].id
        _, document, chunk = paper(db, owner)
        _, foreign_document, foreign_chunk = paper(db, other)
        document_id = document.id
        asset = DocumentAsset(
            user_id=owner,
            document_id=document_id,
            document_version=1,
            extraction_generation=1,
            asset_type="figure",
            page_number=1,
            asset_label="Figure 1",
            caption="Caption",
            storage_key="a" * 64 + ".png",
            image_size_bytes=100,
            linked_chunk_ids=[chunk.id],
        )
        db.add(asset)
        db.commit()
        asset_id = asset.id
        config = migration_config(
            identity_database.url.render_as_string(hide_password=False)
        )
        try:
            with pytest.raises(RuntimeError, match="Purge assets"):
                command.downgrade(config, "b8d29e6a410c")
            db.add(
                AssetChunkLink(
                    user_id=owner, asset_id=asset_id, chunk_id=foreign_chunk.id
                )
            )
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
            asset = db.get(DocumentAsset, asset_id)
            asset.document_id = foreign_document.id
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
            db.execute(
                delete(Document).where(
                    Document.id == document_id, Document.user_id == owner
                )
            )
            db.commit()
            queued = db.scalar(
                select(AssetDeletion).where(AssetDeletion.user_id == owner)
            )
            assert queued.storage_key == "a" * 64 + ".png"
            assert db.get(DocumentAsset, asset_id) is None
        finally:
            db.execute(
                delete(ResearchPaper).where(ResearchPaper.owner_id.in_([owner, other]))
            )
            db.execute(delete(User).where(User.id.in_([owner, other])))
            db.execute(
                delete(AssetDeletion).where(AssetDeletion.user_id.in_([owner, other]))
            )
            db.commit()
