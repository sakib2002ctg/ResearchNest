import hashlib
from io import BytesIO

import pytest
from pypdf import PdfWriter
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import Base
from app.models.audit_log import AuditLog
from app.models.library import Document, PDFDeletion
from app.models.paper import Paper, UserPaper
from app.models.research_paper import ResearchPaper
from app.modules.library import documents
from app.modules.library.cleanup import drain_pdf_deletions
from app.modules.library.storage import (
    InvalidPDF,
    PDFStorage,
    ScannerUnavailable,
    validate_pdf,
)
from tests.conftest import issue_test_session

LIBRARY = "/api/v1/library"


@pytest.fixture
def db(tmp_path, monkeypatch):
    url = URL.create("sqlite", database=str(tmp_path / "library.sqlite"))
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
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


def pdf_bytes(*, encrypted=False, active=False, page_count=1):
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=100, height=100)
    if encrypted:
        writer.encrypt("test-password")
    if active:
        writer.add_attachment("sample.txt", b"Sample attached content.")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def upload(client, content, *, filename="sample.pdf", mime="application/pdf", **fields):
    return client.post(
        f"{LIBRARY}/upload", files={"file": (filename, content, mime)}, data=fields
    )


def pdf_url(paper_id):
    return f"{LIBRARY}/papers/{paper_id}/pdf"


def test_private_pdf_round_trip_and_tenant_isolation(
    client, db, access_token, test_user, another_user
):
    pdf = pdf_bytes(page_count=2)
    headers = {"Authorization": f"Bearer {access_token}"}
    assert upload(client, pdf).status_code == 401
    client.headers.update(headers)
    created = upload(client, pdf, filename="../পরীক্ষা.pdf", title="Private source")
    assert created.status_code == 201, created.text
    result = created.json()
    assert result == {
        "id": result["id"],
        "user_paper_id": result["user_paper_id"],
        "original_filename": "পরীক্ষা.pdf",
        "size_bytes": len(pdf),
        "page_count": 2,
    }
    document = db.get(Document, result["id"])
    assert document.user_id == test_user.id
    assert document.sha256 == hashlib.sha256(pdf).hexdigest()
    stored_path = settings.PDF_STORAGE_ROOT / document.storage_key
    assert stored_path.read_bytes() == pdf
    private = db.get(UserPaper, result["user_paper_id"])
    assert private.paper_id is None
    assert db.get(ResearchPaper, private.legacy_paper_id).title == "Private source"
    assert db.scalar(select(func.count()).select_from(Paper)) == 0
    db.commit()

    url = pdf_url(result["user_paper_id"])
    download = client.get(url)
    assert download.content == pdf
    assert download.headers["content-type"] == "application/pdf"
    assert download.headers["cache-control"] == "private, no-store"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["content-disposition"].startswith("attachment;")
    assert upload(client, pdf, user_paper_id=result["user_paper_id"]).status_code == 409

    other_token = issue_test_session(db, another_user)
    client.headers.update({"Authorization": f"Bearer {other_token}"})
    assert client.get(url).status_code == 404
    assert client.delete(url).status_code == 404
    assert upload(client, pdf, user_paper_id=result["user_paper_id"]).status_code == 404

    client.headers.update(headers)
    assert client.delete(url).status_code == 204
    assert not stored_path.exists()
    assert client.get(url).status_code == 404
    assert client.delete(url).status_code == 404

    # Removing a document leaves its paper available for another attachment.
    assert upload(client, pdf, user_paper_id=result["user_paper_id"]).status_code == 201
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(PDFDeletion)) == 0
    actions = db.scalars(
        select(AuditLog.action).where(AuditLog.user_id == test_user.id)
    ).all()
    assert sorted(actions) == [
        "library.pdf.deleted",
        "library.pdf.uploaded",
        "library.pdf.uploaded",
    ]


@pytest.mark.parametrize(
    ("kind", "status"),
    [
        ("wrong_mime", 415),
        ("missing_signature", 422),
        ("invalid_structure", 422),
        ("embedded_file", 422),
        ("encrypted", 422),
        ("no_pages", 422),
        ("no_scanner_in_production", 503),
    ],
)
def test_rejected_uploads_leave_no_documents_or_files(
    authenticated_client, db, monkeypatch, kind, status
):
    data = pdf_bytes(
        encrypted=kind == "encrypted",
        active=kind == "embedded_file",
        page_count=0 if kind == "no_pages" else 1,
    )
    if kind == "missing_signature":
        data = b"These bytes are a plain text file."
    elif kind == "invalid_structure":
        data = b"%PDF-1.7\nnot a PDF structure\n%%EOF\n"
    elif kind == "no_scanner_in_production":
        monkeypatch.setattr(settings, "APP_ENV", "production")
    mime = "application/octet-stream" if kind == "wrong_mime" else "application/pdf"
    response = upload(authenticated_client, data, mime=mime)
    assert response.status_code == status, response.text
    assert db.scalar(select(func.count()).select_from(Document)) == 0
    assert db.scalar(select(func.count()).select_from(ResearchPaper)) == 0
    assert not settings.PDF_STORAGE_ROOT.exists()


def test_chunked_multipart_and_file_limits(authenticated_client, monkeypatch):
    monkeypatch.setattr(documents, "MAX_PDF_BYTES", 256)
    monkeypatch.setattr(documents, "_MAX_FORM_BYTES", 512)
    prefix = (
        b'--boundary\r\nContent-Disposition: form-data; name="file"; '
        b'filename="x.pdf"\r\nContent-Type: application/pdf\r\n\r\n'
    )
    suffix = b"\r\n--boundary--\r\n"
    main_headers = {"Content-Type": "multipart/form-data; boundary=boundary"}

    individual_file = iter((prefix, b"x" * 200, b"x" * 70, suffix))
    assert (
        authenticated_client.post(
            f"{LIBRARY}/upload", content=individual_file, headers=main_headers
        ).status_code
        == 413
    )
    complete_body = iter((prefix, b"x" * 60, suffix, b"x" * 400))
    assert (
        authenticated_client.post(
            f"{LIBRARY}/upload", content=complete_body, headers=main_headers
        ).status_code
        == 413
    )


def test_scanner_protocol_uses_a_private_stream_and_rejects_malware(monkeypatch):
    from app.modules.library import storage

    data = pdf_bytes()
    calls = []

    class Scanner:
        def __init__(self, reply):
            self.reply = iter((reply[:-1], reply[-1:]))

        def __enter__(self):
            return self

        def __exit__(self, *exception):
            return False

        def settimeout(self, timeout):
            assert 0 < timeout <= 10

        def sendall(self, content):
            calls.append(content)

        def recv(self, _length):
            return next(self.reply, b"")

    def install(reply):
        monkeypatch.setattr(
            storage.socket, "create_connection", lambda *args, **kwargs: Scanner(reply)
        )

    monkeypatch.setattr(settings, "CLAMAV_HOST", "internal-scanner")
    install(b"stream: OK\x00")
    assert validate_pdf(BytesIO(data)) == 1
    assert calls == [
        b"zINSTREAM\x00",
        len(data).to_bytes(4, "big") + data,
        b"\x00\x00\x00\x00",
    ]
    install(b"stream: flagged FOUND\x00")
    with pytest.raises(InvalidPDF, match="malware scan"):
        validate_pdf(BytesIO(data))
    install(b"INSTREAM size limit exceeded. ERROR\x00")
    with pytest.raises(ScannerUnavailable):
        validate_pdf(BytesIO(data))


def test_invalid_keys_cannot_read_or_delete_files_outside_storage(tmp_path):
    storage = PDFStorage(tmp_path / "private")
    target = tmp_path / "outside.pdf"
    target.write_bytes(b"outside")
    with pytest.raises(OSError, match="Invalid PDF storage key"):
        storage.open("../outside.pdf", 7)
    with pytest.raises(OSError, match="Invalid PDF storage key"):
        storage.remove("../outside.pdf")
    assert target.read_bytes() == b"outside"


def test_windows_storage_acl_is_restricted_and_fail_closed(tmp_path, monkeypatch):
    from app.modules.library import storage as storage_module

    monkeypatch.setenv("SystemRoot", str(tmp_path))
    calls = []

    class Result:
        stdout = '"service-account","S-1-5-21-111-222-333-1001"\r\n'

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["shell"] is False
        assert kwargs["check"] is True
        return Result()

    monkeypatch.setattr(storage_module.subprocess, "run", run)
    storage_module._harden_windows_directory(tmp_path / "pdf")
    assert len(calls) == 2
    assert calls[-1][2:] == [
        "/inheritance:r",
        "/grant:r",
        "*S-1-5-21-111-222-333-1001:(OI)(CI)F",
        "*S-1-5-18:(OI)(CI)F",
    ]

    def fail(*args, **kwargs):
        raise storage_module.subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(storage_module.subprocess, "run", fail)
    with pytest.raises(OSError, match="Could not secure PDF storage"):
        storage_module._harden_windows_directory(tmp_path / "pdf")


def test_storage_directory_symlink_is_rejected(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is unavailable in this environment.")
    with pytest.raises(OSError, match="Invalid PDF storage directory"):
        PDFStorage(link).store(BytesIO(pdf_bytes()), pages=1)


def test_database_failure_discards_uncommitted_file(
    authenticated_client, db, monkeypatch
):
    from sqlalchemy.ext.asyncio import AsyncSession

    async def fail_commit(self):
        raise OSError("Simulated database failure")

    monkeypatch.setattr(AsyncSession, "commit", fail_commit)
    response = upload(authenticated_client, pdf_bytes())
    assert response.status_code == 503
    assert not list(settings.PDF_STORAGE_ROOT.iterdir())
    assert db.scalar(select(func.count()).select_from(Document)) == 0
    assert db.scalar(select(func.count()).select_from(ResearchPaper)) == 0


def _drain(client):
    async def run():
        async with client.app.state.discovery_session_factory() as session:
            await drain_pdf_deletions(session)

    client.portal.call(run)


@pytest.mark.parametrize("remove_account", [False, True])
def test_parent_deletion_queues_correct_pdf_objects(
    authenticated_client, db, remove_account
):
    first = upload(authenticated_client, pdf_bytes()).json()
    second = upload(authenticated_client, pdf_bytes()).json()
    first_doc = db.get(Document, first["id"])
    first_key = first_doc.storage_key
    second_key = db.get(Document, second["id"]).storage_key
    first_projection = db.get(UserPaper, first["user_paper_id"]).legacy_paper_id
    db.commit()

    if remove_account:
        response = authenticated_client.delete("/api/v1/users/me")
        assert response.status_code == 204, response.text
    else:
        response = authenticated_client.delete(f"/api/v1/papers/{first_projection}")
        assert response.status_code == 200, response.text

    db.expire_all()
    assert db.get(Document, first["id"]) is None
    assert (db.get(Document, second["id"]) is None) is remove_account
    db.commit()
    _drain(authenticated_client)
    assert not (settings.PDF_STORAGE_ROOT / first_key).exists()
    assert (settings.PDF_STORAGE_ROOT / second_key).exists() is not remove_account


def test_failed_blob_removal_is_retried(authenticated_client, db, monkeypatch):
    result = upload(authenticated_client, pdf_bytes()).json()
    key = db.get(Document, result["id"]).storage_key
    db.commit()

    def fail_remove(self, key):
        raise OSError("Temporary file access failure")

    with monkeypatch.context() as patch:
        patch.setattr(PDFStorage, "remove", fail_remove)
        result = authenticated_client.delete(pdf_url(result["user_paper_id"]))
    assert result.status_code == 204
    assert db.get(PDFDeletion, key) is not None
    assert (settings.PDF_STORAGE_ROOT / key).exists()
    db.commit()

    _drain(authenticated_client)
    assert db.get(PDFDeletion, key) is None
    assert not (settings.PDF_STORAGE_ROOT / key).exists()
