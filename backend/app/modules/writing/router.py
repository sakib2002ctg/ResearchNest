import asyncio
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select

from app.models.writing import WritingDocument, WritingVersion
from app.modules.ai.gateway import AIProviderGateway
from app.modules.ai.router import get_gateway, private_headers
from app.modules.ai.schemas import ID
from app.modules.library.dependencies import LibraryDB, Owner
from app.modules.writing import assistant, service
from app.modules.writing.exports import ExportError, export_document
from app.modules.writing.repository import (
    document_for_owner,
    references,
    serialize,
    version_data,
)
from app.modules.writing.schemas import (
    AssistRequest,
    CreateDocument,
    RestoreVersion,
    UpdateDocument,
)

router = APIRouter(
    prefix="/writing", tags=["Writing studio"], dependencies=[Depends(private_headers)]
)
Gateway = Annotated[AIProviderGateway, Depends(get_gateway)]


@router.get("")
async def list_documents(
    owner: Owner,
    db: LibraryDB,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
):
    return [
        serialize(row)
        for row in await db.scalars(
            select(WritingDocument)
            .where(WritingDocument.user_id == owner)
            .order_by(WritingDocument.updated_at.desc(), WritingDocument.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ]


@router.post("", status_code=201)
async def create_document(body: CreateDocument, owner: Owner, db: LibraryDB):
    return await service.create(db, owner, body)


@router.get("/{doc_id}")
async def get_document(doc_id: ID, owner: Owner, db: LibraryDB):
    return serialize(await document_for_owner(db, owner, doc_id))


@router.put("/{doc_id}")
async def update_document(
    doc_id: ID, body: UpdateDocument, owner: Owner, db: LibraryDB
):
    return await service.update(db, owner, doc_id, body)


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: ID, owner: Owner, db: LibraryDB):
    await service.remove(db, owner, doc_id)


@router.get("/{doc_id}/versions")
async def list_versions(doc_id: ID, owner: Owner, db: LibraryDB):
    await document_for_owner(db, owner, doc_id)
    return [
        version_data(v)
        for v in await db.scalars(
            select(WritingVersion)
            .where(
                WritingVersion.user_id == owner,
                WritingVersion.writing_document_id == doc_id,
            )
            .order_by(WritingVersion.version_number.desc())
        )
    ]


@router.post("/{doc_id}/versions/{version_id}/restore")
async def restore_version(
    doc_id: ID,
    version_id: ID,
    owner: Owner,
    db: LibraryDB,
    body: RestoreVersion | None = None,
):
    return await service.restore(
        db, owner, doc_id, version_id, body.expected_revision if body else None
    )


@router.post("/{doc_id}/assist")
async def assist(
    doc_id: ID, body: AssistRequest, owner: Owner, db: LibraryDB, gateway: Gateway
):
    return await assistant.assist(db, owner, doc_id, body, gateway)


@router.get("/{doc_id}/export")
async def export(
    doc_id: ID,
    owner: Owner,
    db: LibraryDB,
    format: Literal["md", "tex", "docx", "pdf"] = "md",
    style: Literal["apa", "ieee", "mla", "chicago", "harvard"] = "apa",
):
    from fastapi import HTTPException

    row = await document_for_owner(db, owner, doc_id)
    refs = await references(db, owner, row.cited_citation_ids, row.content_markdown)
    try:
        content, mime, filename = await asyncio.to_thread(
            export_document, row, refs, format, style
        )
    except ExportError as error:
        raise HTTPException(422, str(error)) from None
    service.audit(db, owner, "writing.exported", doc_id)
    await db.commit()
    return Response(
        content=content,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
