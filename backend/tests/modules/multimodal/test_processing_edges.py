"""Worker fencing and durable cleanup across native-parser/file-I/O failures."""

import asyncio
import stat
from threading import Event

import fitz
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.time import utc_now
from app.models.multimodal import AssetDeletion, AssetExtractionJob, DocumentAsset
from app.modules.multimodal import processing
from app.modules.multimodal.cleanup import drain_asset_deletions
from app.modules.multimodal.storage import AssetStorage
from tests.modules.multimodal.test_asset_routes import BASE, indexed


def queued_job(client, db, access_token):
    document = indexed(client, db, access_token)
    response = client.post(f"{BASE}/documents/{document['id']}/extract")
    assert response.status_code == 202, response.text
    return document["id"], response.json()["job_id"]


def one_asset(_):
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20))
    pixmap.clear_with(160)
    return [
        {
            "asset_type": "figure",
            "asset_label": "Figure 1",
            "page_number": 1,
            "caption": "Figure 1: A safe source caption.",
            "extracted_text_or_latex": None,
            "structured_data": {"bbox": [50, 100, 150, 200]},
            "image_bytes": pixmap.tobytes("png"),
        }
    ]


def test_parser_failure_is_sanitized_and_does_not_leave_images(
    client, db, access_token
):
    _, job_id = queued_job(client, db, access_token)

    def fail(_):
        raise RuntimeError("PRIVATE DOCUMENT AND PARSER CONTENT")

    processor = processing.AssetProcessor(
        client.app.state.discovery_session_factory, extractor=fail
    )
    client.portal.call(processor.process_job, job_id)
    db.expire_all()
    job = db.get(AssetExtractionJob, job_id)
    assert job.status == "failed"
    assert "PRIVATE" not in job.error_message
    assert db.scalar(select(func.count()).select_from(DocumentAsset)) == 0
    assert list(settings.ASSET_STORAGE_ROOT.rglob("*.png")) == []


@pytest.mark.parametrize("mutation", ["new_generation", "failed_attempt"])
def test_stale_attempt_does_not_publish_images_or_override_new_job(
    client, db, access_token, monkeypatch, mutation
):
    _, job_id = queued_job(client, db, access_token)
    factory = client.app.state.discovery_session_factory
    original_thread = asyncio.to_thread
    mutated = False

    async def mutate_after_first_save(function, *args, **kwargs):
        nonlocal mutated
        result = await original_thread(function, *args, **kwargs)
        if getattr(function, "__name__", "") == "save" and not mutated:
            mutated = True
            async with factory() as session:
                job = await session.get(AssetExtractionJob, job_id)
                if mutation == "new_generation":
                    job.generation += 1
                    job.attempts = 0
                    job.status = "queued"
                else:
                    job.status = "failed"
                await session.commit()
        return result

    monkeypatch.setattr(processing.asyncio, "to_thread", mutate_after_first_save)
    client.portal.call(
        processing.AssetProcessor(factory, extractor=one_asset).process_job, job_id
    )
    db.expire_all()
    job = db.get(AssetExtractionJob, job_id)
    assert job.status == ("queued" if mutation == "new_generation" else "failed")
    assert db.scalar(select(func.count()).select_from(DocumentAsset)) == 0
    assert list(settings.ASSET_STORAGE_ROOT.rglob("*.png")) == []


def test_cancellation_during_threaded_save_retains_cleanup_intent_until_write_finishes(
    client, db, access_token, monkeypatch
):
    _, job_id = queued_job(client, db, access_token)
    factory = client.app.state.discovery_session_factory
    started, release, finished = Event(), Event(), Event()
    original_save = AssetStorage.save

    def delayed_save(storage, image, key=None):
        started.set()
        try:
            if not release.wait(timeout=10):
                raise RuntimeError("Test save did not receive its release signal.")
            return original_save(storage, image, key)
        finally:
            finished.set()

    async def await_event(event):
        async with asyncio.timeout(10):
            while not event.is_set():
                await asyncio.sleep(0.01)

    monkeypatch.setattr(AssetStorage, "save", delayed_save)

    async def run():
        task = asyncio.create_task(
            processing.AssetProcessor(factory, extractor=one_asset).process_job(job_id)
        )
        try:
            await await_event(started)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            # Let the non-cancellable thread finish after its coroutine has exited.
            release.set()
            await await_event(finished)
            async with factory() as session:
                assert (
                    await session.scalar(
                        select(func.count()).select_from(DocumentAsset)
                    )
                    == 0
                )
                intents = list(await session.scalars(select(AssetDeletion)))
                assert len(intents) == 1
                intent = intents[0]
                path = (
                    settings.ASSET_STORAGE_ROOT
                    / str(intent.user_id)
                    / intent.storage_key
                )
                assert path.is_file()
                # A delayed intent prevents early cleanup racing the file write.
                await drain_asset_deletions(session)
                assert path.is_file()
                intent.created_at = utc_now()
                await session.commit()
                await drain_asset_deletions(session)
                assert not path.exists()
        finally:
            release.set()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    client.portal.call(run)


@pytest.mark.parametrize(
    "key", ["../other.png", "folder/image.png", "0" * 64 + ".pdf", "C:\\private.png"]
)
def test_asset_storage_rejects_traversal_and_other_storage_types(tmp_path, key):
    storage = AssetStorage(1)
    with pytest.raises(OSError):
        storage.read(key, 12)
    with pytest.raises(OSError):
        storage.remove(key)


def test_asset_storage_rejects_symlinked_owner_directory(monkeypatch):
    storage = AssetStorage(1)
    directory = storage.root
    directory.mkdir(parents=True, exist_ok=True)
    original = type(directory).lstat

    def symlink_info(path):
        info = original(path)
        if path == directory:
            # Portable simulation of the OS symlink/reparse-point stat result;
            # Windows symlink creation is privilege-dependent in CI/sandboxes.
            data = list(info)
            data[0] = stat.S_IFLNK | 0o700
            return type(info)(data)
        return info

    monkeypatch.setattr(type(directory), "lstat", symlink_info)
    with pytest.raises(OSError, match="storage directory"):
        storage.save(one_asset(None)[0]["image_bytes"])


def test_unindexed_document_job_is_failed_instead_of_remaining_queued_forever(
    client, db, access_token
):
    from app.models.library import Document

    doc_id, job_id = queued_job(client, db, access_token)
    db.get(Document, doc_id).status = "processing"
    db.commit()
    client.portal.call(
        processing.AssetProcessor(
            client.app.state.discovery_session_factory, extractor=one_asset
        ).process_job,
        job_id,
    )
    db.expire_all()
    assert db.get(AssetExtractionJob, job_id).status == "failed"
