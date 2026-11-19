"""Tenant-scoped upload, download, and removal of private PDFs."""

import re
import unicodedata
from collections.abc import AsyncIterator
from typing import Annotated, BinaryIO
from urllib.parse import quote

from anyio import CancelScope, CapacityLimiter, WouldBlock, fail_after, to_thread
from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from pydantic import BaseModel
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import FormData, UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.requests import ClientDisconnect
from starlette.responses import StreamingResponse

from app.core.logging import logger
from app.database.discovery_database import get_discovery_db
from app.models.audit_log import AuditLog
from app.models.library import Document, PDFDeletion
from app.models.paper import UserPaper
from app.models.research_paper import ResearchPaper
from app.models.user import User
from app.modules.library.cleanup import drain_pdf_deletions
from app.modules.library.dependencies import get_library_owner
from app.modules.library.storage import (
    CHUNK_BYTES,
    MAX_PDF_BYTES,
    InvalidPDF,
    PDFTooLarge,
    ScannerUnavailable,
    storage_from_settings,
    validate_pdf,
)

router = APIRouter(tags=["Library PDFs"])
_MAX_FORM_BYTES = MAX_PDF_BYTES + 64 * 1024
_MAX_PART_HEADERS = 8 * 1024
_UPLOAD_SLOTS = CapacityLimiter(4)
_NO_CACHE = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
_UPLOAD_SCHEMA = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["file"],
                    "properties": {
                        "file": {"type": "string", "format": "binary"},
                        "title": {"type": "string", "maxLength": 255},
                        "user_paper_id": {"type": "integer", "minimum": 1},
                    },
                }
            }
        },
    }
}

Owner = Annotated[int, Depends(get_library_owner)]
DB = Annotated[AsyncSession, Depends(get_discovery_db)]
PaperID = Annotated[int, Path(gt=0, le=2_147_483_647)]


class DocumentResponse(BaseModel):
    id: int
    user_paper_id: int
    original_filename: str
    size_bytes: int
    page_count: int


class _FormTooLarge(MultiPartException):
    pass


class _PDFFormParser(MultiPartParser):
    """Limit file and header bytes within Starlette's streamed multipart parser."""

    _file_bytes: int = 0
    _header_bytes: int = 0
    _finished: bool = False

    def on_part_begin(self) -> None:
        self._file_bytes = self._header_bytes = 0
        super().on_part_begin()

    def _count_header_bytes(self, start: int, end: int) -> None:
        self._header_bytes += end - start
        if self._header_bytes > _MAX_PART_HEADERS:
            raise _FormTooLarge("Multipart headers are too large.")

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        self._count_header_bytes(start, end)
        super().on_header_field(data, start, end)

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        self._count_header_bytes(start, end)
        super().on_header_value(data, start, end)

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        self._file_bytes += end - start
        if self._file_bytes > MAX_PDF_BYTES:
            raise _FormTooLarge("The PDF exceeds the upload limit.")
        super().on_part_data(data, start, end)

    def on_end(self) -> None:
        self._finished = True

    async def parse(self) -> FormData:
        try:
            result = await super().parse()
            if not self._finished:
                raise MultiPartException("Incomplete multipart form.")
            return result
        except BaseException:
            # Also close spools on disconnect, cancellation and malformed MIME.
            for spool in self._files_to_close_on_error:
                spool.close()
            raise


async def _bounded_stream(request: Request) -> AsyncIterator[bytes]:
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > _MAX_FORM_BYTES:
            raise _FormTooLarge("The request exceeds the upload limit.")
        yield chunk


async def _read_form(request: Request) -> FormData:
    content_type, params = parse_options_header(request.headers.get("content-type"))
    if content_type != b"multipart/form-data":
        raise HTTPException(415, "Expected a multipart PDF upload.")
    boundary = params.get(b"boundary")
    if not boundary or len(boundary) > 70:
        raise HTTPException(400, "Invalid multipart form.")
    length = request.headers.get("content-length")
    if length is not None:
        if not re.fullmatch(r"[0-9]{1,20}", length):
            raise HTTPException(400, "Invalid request size.")
        if int(length) > _MAX_FORM_BYTES:
            raise HTTPException(413, "The request exceeds the upload limit.")
    parser = _PDFFormParser(
        request.headers,
        _bounded_stream(request),
        max_files=1,
        max_fields=2,
        max_part_size=1_024,
    )
    try:
        with fail_after(60):
            return await parser.parse()
    except _FormTooLarge as error:
        raise HTTPException(413, error.message) from None
    except (MultiPartException, MultipartParseError, ClientDisconnect):
        raise HTTPException(400, "Invalid multipart form.") from None
    except TimeoutError:
        raise HTTPException(408, "The upload timed out.") from None


def _clean_filename(filename: str | None) -> str:
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(c for c in name if not unicodedata.category(c).startswith("C"))
    name = name.strip(". ")
    stem = name[:-4] if name.lower().endswith(".pdf") else name
    return f"{stem[:251].strip('. ') or 'document'}.pdf"


def _extract_form_values(form: FormData) -> tuple[UploadFile, str, str, int | None]:
    keys = [key for key, _ in form.multi_items()]
    if len(keys) != len(set(keys)) or set(keys) - {"file", "title", "user_paper_id"}:
        raise HTTPException(400, "Unexpected or repeated multipart fields.")
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        raise HTTPException(422, "A PDF file is required.")
    content_type, _ = parse_options_header(upload.content_type)
    if content_type != b"application/pdf":
        raise HTTPException(415, "The file must be declared as application/pdf.")
    filename = _clean_filename(upload.filename)
    title = form.get("title", filename.removesuffix(".pdf"))
    if (
        not isinstance(title, str)
        or not 1 <= len(title.strip()) <= 255
        or any(unicodedata.category(c).startswith("C") for c in title.strip())
    ):
        raise HTTPException(422, "Enter a title of up to 255 characters.")
    paper_id = form.get("user_paper_id")
    if paper_id is None:
        return upload, filename, title.strip(), None
    if (
        not isinstance(paper_id, str)
        or not re.fullmatch(r"[0-9]{1,10}", paper_id)
        or not 0 < int(paper_id) <= 2_147_483_647
    ):
        raise HTTPException(422, "Invalid library paper ID.")
    return upload, filename, title.strip(), int(paper_id)


async def _lock_owner(db: AsyncSession, owner: int) -> None:
    user_id = await db.scalar(select(User.id).where(User.id == owner).with_for_update())
    if user_id is None:
        raise HTTPException(401, "Could not validate credentials.")


async def _find_document(
    db: AsyncSession, owner: int, paper_id: int
) -> Document | None:
    return await db.scalar(
        select(Document).where(
            Document.user_id == owner, Document.user_paper_id == paper_id
        )
    )


async def _check_attachment_target(db: AsyncSession, owner: int, paper_id: int) -> None:
    saved_id = await db.scalar(
        select(UserPaper.id).where(UserPaper.user_id == owner, UserPaper.id == paper_id)
    )
    if saved_id is None:
        raise HTTPException(404, "Library paper not found.")
    if await _find_document(db, owner, paper_id):
        raise HTTPException(409, "This paper already has a PDF attachment.")


async def _store_document(
    db: AsyncSession,
    owner: int,
    upload: UploadFile,
    filename: str,
    title: str,
    paper_id: int | None,
) -> DocumentResponse:
    if paper_id is not None:
        await _check_attachment_target(db, owner, paper_id)
        # Release this read transaction during the scan. Check again under the lock.
        await db.rollback()
    pages = await to_thread.run_sync(validate_pdf, upload.file)
    await _lock_owner(db, owner)
    if paper_id is None:
        projection = ResearchPaper(title=title, source="upload", owner_id=owner)
        db.add(projection)
        await db.flush()
        saved_paper = UserPaper(user_id=owner, legacy_paper_id=projection.id)
        db.add(saved_paper)
        await db.flush()
        paper_id = saved_paper.id
    else:
        await _check_attachment_target(db, owner, paper_id)

    storage = storage_from_settings()
    with CancelScope(shield=True):
        stored = await to_thread.run_sync(storage.store, upload.file, pages)
        try:
            document = Document(
                user_id=owner,
                user_paper_id=paper_id,
                storage_key=stored.key,
                original_filename=filename,
                size_bytes=stored.size,
                sha256=stored.sha256,
                page_count=stored.pages,
            )
            db.add(document)
            await db.flush()
            db.add(
                AuditLog(
                    user_id=owner,
                    action="library.pdf.uploaded",
                    resource_type="document",
                    resource_id=str(document.id),
                )
            )
            result = DocumentResponse(
                id=document.id,
                user_paper_id=paper_id,
                original_filename=filename,
                size_bytes=stored.size,
                page_count=stored.pages,
            )
            await db.commit()
        except BaseException:
            try:
                await db.rollback()
                persisted = await db.scalar(
                    select(Document.id).where(Document.storage_key == stored.key)
                )
            except Exception:
                # Storage is private; preserve it when the database is uncertain.
                logger.error(
                    "PDF persistence outcome is uncertain; preserving the object."
                )
                raise
            if persisted is None:
                try:
                    await to_thread.run_sync(storage.remove, stored.key)
                except OSError:
                    logger.error("Could not discard an uncommitted PDF.")
            # If the document exists, commit may have succeeded despite an error.
            raise
    return result


@router.post(
    "/upload",
    status_code=201,
    response_model=DocumentResponse,
    openapi_extra=_UPLOAD_SCHEMA,
)
async def upload_pdf(request: Request, owner: Owner, db: DB) -> DocumentResponse:
    try:
        _UPLOAD_SLOTS.acquire_nowait()
    except WouldBlock:
        raise HTTPException(
            429, "PDF upload capacity is busy.", headers={"Retry-After": "5"}
        ) from None
    try:
        form = await _read_form(request)
        try:
            upload, filename, title, paper_id = _extract_form_values(form)
            return await _store_document(db, owner, upload, filename, title, paper_id)
        finally:
            with CancelScope(shield=True):
                await form.close()
    except PDFTooLarge as error:
        raise HTTPException(413, str(error)) from None
    except InvalidPDF as error:
        raise HTTPException(422, str(error)) from None
    except ScannerUnavailable:
        raise HTTPException(503, "PDF processing is temporarily unavailable.") from None
    except OSError as error:
        logger.warning("PDF storage I/O failed (errno=%s).", error.errno)
        raise HTTPException(503, "PDF processing is temporarily unavailable.") from None
    finally:
        _UPLOAD_SLOTS.release()


async def _pdf_chunks(stream: BinaryIO) -> AsyncIterator[bytes]:
    try:
        while chunk := await to_thread.run_sync(stream.read, CHUNK_BYTES):
            yield chunk
    finally:
        stream.close()


@router.get("/papers/{paper_id}/pdf", response_class=StreamingResponse)
async def download_pdf(paper_id: PaperID, owner: Owner, db: DB) -> StreamingResponse:
    document = await _find_document(db, owner, paper_id)
    if document is None:
        raise HTTPException(404, "PDF not found.")
    try:
        stream = await to_thread.run_sync(
            storage_from_settings().open, document.storage_key, document.size_bytes
        )
    except FileNotFoundError:
        raise HTTPException(404, "PDF not found.") from None
    except OSError:
        logger.error("Could not open a private PDF.")
        raise HTTPException(503, "PDF processing is temporarily unavailable.") from None
    filename = quote(_clean_filename(document.original_filename), safe="")
    headers = {
        **_NO_CACHE,
        "Content-Disposition": (
            f"""attachment; filename="document.pdf"; filename*=UTF-8''{filename}"""
        ),
        "Content-Length": str(document.size_bytes),
    }
    return StreamingResponse(
        _pdf_chunks(stream), media_type="application/pdf", headers=headers
    )


@router.delete("/papers/{paper_id}/pdf", status_code=204)
async def delete_pdf(paper_id: PaperID, owner: Owner, db: DB) -> Response:
    await _lock_owner(db, owner)
    document = await _find_document(db, owner, paper_id)
    if document is None:
        raise HTTPException(404, "PDF not found.")
    db.add(PDFDeletion(storage_key=document.storage_key))
    db.add(
        AuditLog(
            user_id=owner,
            action="library.pdf.deleted",
            resource_type="document",
            resource_id=str(document.id),
        )
    )
    await db.delete(document)
    await db.commit()
    await drain_pdf_deletions(db)
    return Response(status_code=204, headers=_NO_CACHE)
