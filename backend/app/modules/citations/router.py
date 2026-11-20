from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import ValidationError
from sqlalchemy import delete, select

from app.models.audit_log import AuditLog
from app.models.writing import Citation
from app.modules.ai.quota import lock_owner
from app.modules.ai.router import private_headers
from app.modules.ai.schemas import ID
from app.modules.citations import service
from app.modules.citations.formatter import format_citations
from app.modules.citations.interchange import (
    export_bibtex,
    export_ris,
    parse_bibtex,
    parse_ris,
)
from app.modules.citations.schemas import (
    CitationInput,
    CitationUpdate,
    FormatRequest,
    ImportRequest,
)
from app.modules.library.dependencies import LibraryDB, Owner

router = APIRouter(
    prefix="/citations",
    tags=["Reference manager"],
    dependencies=[Depends(private_headers)],
)


@router.get("")
async def list_citations(
    owner: Owner,
    db: LibraryDB,
    q: Annotated[str | None, Query(max_length=300)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
):
    query = select(Citation).where(Citation.user_id == owner)
    if q:
        query = query.where(Citation.title.icontains(q.strip(), autoescape=True))
    return [
        service.result(row)
        for row in await db.scalars(
            query.order_by(Citation.id.desc()).limit(limit).offset(offset)
        )
    ]


@router.post("", status_code=201)
async def create_citation(
    body: CitationInput, owner: Owner, db: LibraryDB, request: Request
):
    return await service.create(db, owner, body, request.app.state.discovery_gateway)


@router.post("/format")
async def format_references(body: FormatRequest, owner: Owner, db: LibraryDB):
    return format_citations(
        await service.owned_rows(db, owner, body.citation_ids), body.style
    )


@router.post("/import", status_code=201)
async def import_references(body: ImportRequest, owner: Owner, db: LibraryDB):
    try:
        records = (
            parse_bibtex(body.content)
            if body.format == "bibtex"
            else parse_ris(body.content)
        )
    except (ValueError, ValidationError):
        raise HTTPException(
            422,
            "Invalid or unsupported reference data. Supply valid titles "
            "and supported BibTeX/RIS fields.",
        ) from None
    values = [await service.prepare(db, owner, record, None) for record in records]
    await db.rollback()
    await lock_owner(db, owner)
    items, created, duplicates = [], 0, 0
    for metadata in values:
        row, added = await service.insert_prepared(db, owner, metadata)
        created += int(added)
        duplicates += int(not added)
        items.append(row)
    db.add(
        AuditLog(
            user_id=owner,
            action="citation.imported",
            resource_type="citation",
            details={
                "created": created,
                "duplicates": duplicates,
                "format": body.format,
            },
        )
    )
    await db.commit()
    rendered = [service.result(row) for row in items]
    return {
        "items": rendered,
        "created": created,
        "duplicates": duplicates,
        "warnings": list(
            dict.fromkeys(warning for item in rendered for warning in item["warnings"])
        ),
    }


@router.get("/export")
async def export_references(
    owner: Owner,
    db: LibraryDB,
    format: Literal["bibtex", "ris"] = "bibtex",
    citation_ids: Annotated[list[ID] | None, Query(max_length=200)] = None,
):
    rows = await service.owned_rows(db, owner, citation_ids)
    content = export_bibtex(rows) if format == "bibtex" else export_ris(rows)
    extension = "bib" if format == "bibtex" else "ris"
    media = (
        "application/x-bibtex"
        if format == "bibtex"
        else "application/x-research-info-systems"
    )
    return Response(
        content=content,
        media_type=media,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'attachment; filename="references.{extension}"',
        },
    )


@router.put("/{citation_id}")
async def update_citation(
    citation_id: ID, body: CitationUpdate, owner: Owner, db: LibraryDB
):
    return await service.update(db, owner, citation_id, body)


@router.delete("/{citation_id}", status_code=204)
async def delete_citation(citation_id: ID, owner: Owner, db: LibraryDB):
    await lock_owner(db, owner)
    await service.owned(db, owner, citation_id)
    await db.execute(
        delete(Citation).where(Citation.user_id == owner, Citation.id == citation_id)
    )
    db.add(
        AuditLog(
            user_id=owner,
            action="citation.deleted",
            resource_type="citation",
            resource_id=str(citation_id),
        )
    )
    await db.commit()
