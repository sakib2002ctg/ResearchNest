from unittest.mock import AsyncMock

import fitz
import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import Base
from app.models.document_intelligence import (
    DocumentChunk,
    DocumentPage,
    Embedding,
    ProcessingJob,
)
from app.models.library import Document
from app.modules.documents.processing import DocumentProcessor

BASE = "/api/v1/documents"


@pytest.fixture
def db(tmp_path, monkeypatch):
    url = URL.create("sqlite", database=str(tmp_path / "documents.sqlite"))
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "DATABASE_URL", str(url))
    monkeypatch.setattr(settings, "PDF_STORAGE_ROOT", tmp_path / "private-pdfs")
    monkeypatch.setattr(settings, "CLAMAV_HOST", None)
    monkeypatch.setattr("app.main.engine", engine)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def sample_pdf():
    with fitz.open() as pdf:
        for n in range(2):
            page = pdf.new_page()
            page.insert_text((72, 72), f"SECTION {n + 1}", fontsize=18)
            page.insert_text(
                (72, 110), f"This is the private body of page {n + 1}. " * 5
            )
        return pdf.tobytes()


def upload(client, token):
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client.post(
        "/api/v1/library/upload",
        files={"file": ("paper.pdf", sample_pdf(), "application/pdf")},
    )


def process(client, job_id):
    factory = client.app.state.discovery_session_factory
    client.portal.call(DocumentProcessor(factory).process_job, job_id)


def test_upload_creates_durable_job_and_owner_scoped_indexed_pages(
    client, db, access_token, another_access_token
):
    dispatch = AsyncMock()
    client.app.state.document_dispatcher = dispatch
    result = upload(client, access_token)
    assert result.status_code == 201, result.text
    result = result.json()
    doc_id = result["id"]
    assert result["status"] == "pending"
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.document_id == doc_id))
    assert job is not None and job.status == "queued" and job.attempts == 0
    dispatch.enqueue.assert_awaited_once_with(job.id)
    doc = db.get(Document, doc_id)
    assert doc.file_hash == doc.sha256
    assert len(doc.file_hash) == 64
    db.commit()
    process(client, job.id)
    db.expire_all()

    response = client.get(f"{BASE}/{doc_id}")
    assert response.status_code == 200
    assert response.json() == {
        "id": doc_id,
        "user_paper_id": result["user_paper_id"],
        "page_count": 2,
        "status": "completed",
        "version": 1,
    }
    assert response.headers["cache-control"] == "private, no-store"
    response = client.get(f"{BASE}/{doc_id}/status")
    assert response.status_code == 200
    assert response.json()["jobs"][0]["status"] == "completed"
    assert response.json()["jobs"][0]["attempts"] == 1
    pages = client.get(f"{BASE}/{doc_id}/pages?size=1").json()
    assert pages["total"] == pages["pages"] == 2
    assert pages["items"][0]["page_number"] == 1
    assert "page 1" in pages["items"][0]["raw_text"]
    second = client.get(f"{BASE}/{doc_id}/pages?size=1&page=2").json()
    assert second["items"][0]["page_number"] == 2
    assert "page 2" in second["items"][0]["raw_text"]
    assert db.scalar(select(func.count()).select_from(DocumentChunk)) == 2
    assert db.scalar(select(func.count()).select_from(Embedding)) == 2
    db.commit()
    process(client, job.id)
    db.expire_all()
    assert db.get(ProcessingJob, job.id).attempts == 1
    assert db.scalar(select(func.count()).select_from(DocumentPage)) == 2
    db.commit()

    client.headers["Authorization"] = f"Bearer {another_access_token}"
    for suffix in ("", "/status", "/pages"):
        denied = client.get(f"{BASE}/{doc_id}{suffix}")
        assert denied.status_code == 404
        assert "private body" not in denied.text
    assert client.post(f"{BASE}/{doc_id}/retry").status_code == 404


def test_failed_index_retry_increments_version_and_cannot_duplicate_running_job(
    client, db, access_token
):
    result = upload(client, access_token).json()
    doc_id = result["id"]
    first_job = db.scalar(
        select(ProcessingJob).where(ProcessingJob.document_id == doc_id)
    )
    assert client.post(f"{BASE}/{doc_id}/retry").status_code == 409
    doc = db.get(Document, doc_id)
    doc.status = "failed"
    first_job.status = "failed"
    first_job.last_error = "Document processing failed."
    db.commit()
    retry = client.post(f"{BASE}/{doc_id}/retry")
    assert retry.status_code == 200, retry.text
    assert retry.json()["version"] == 2
    assert retry.json()["status"] == "pending"
    new_job_id = retry.json()["jobs"][0]["id"]
    assert client.post(f"{BASE}/{doc_id}/retry").status_code == 409
    process(client, new_job_id)
    assert client.get(f"{BASE}/{doc_id}/status").json()["status"] == "completed"
    pages = client.get(f"{BASE}/{doc_id}/pages").json()
    assert pages["total"] == 2
    db.expire_all()
    assert db.get(ProcessingJob, first_job.id).status == "failed"


@pytest.mark.parametrize("suffix", ["", "/status", "/pages", "/retry"])
def test_document_endpoints_require_authentication(client, suffix):
    response = (
        client.post(f"{BASE}/1{suffix}")
        if suffix == "/retry"
        else client.get(f"{BASE}/1{suffix}")
    )
    assert response.status_code == 401


def test_document_api_rejects_invalid_identifiers(client, access_token):
    client.headers["Authorization"] = f"Bearer {access_token}"
    assert client.get(f"{BASE}/2147483648").status_code == 422
    assert client.get(f"{BASE}/1/pages?size=51").status_code == 422
