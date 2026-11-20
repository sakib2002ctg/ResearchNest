import asyncio
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from app.modules.ai.gateway import AIProviderGateway
from app.modules.ai.router import get_gateway, private_headers
from app.modules.ai.schemas import ID
from app.modules.library.dependencies import LibraryDB, Owner
from app.modules.multimodal import service
from app.modules.multimodal.processing import request_extraction
from app.modules.multimodal.repository import (
    asset_data,
    linked_chunks,
    list_assets,
    owned_asset,
)
from app.modules.multimodal.storage import AssetStorage

router = APIRouter(
    prefix="/multimodal",
    tags=["Multimodal intelligence"],
    dependencies=[Depends(private_headers)],
)
Gateway = Annotated[AIProviderGateway, Depends(get_gateway)]


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["en", "bn"] = "en"
    provider: Literal["auto", "offline", "local", "cloud"] = "auto"
    request_id: UUID = Field(default_factory=uuid4)


class QuestionRequest(ExplainRequest):
    question: str = Field(min_length=2, max_length=2000, pattern=r"^[^\x00]*$")


@router.post("/documents/{document_id}/extract", status_code=202)
async def extract(document_id: ID, owner: Owner, db: LibraryDB):
    return await request_extraction(db, owner, document_id)


@router.get("/documents/{document_id}/assets")
async def assets(
    document_id: ID,
    owner: Owner,
    db: LibraryDB,
    asset_type: (
        Literal["figure", "chart", "diagram", "table", "equation"] | None
    ) = None,
    page_number: Annotated[int | None, Query(ge=1, le=1000)] = None,
):
    return await list_assets(db, owner, document_id, asset_type, page_number)


@router.get("/assets/{asset_id}")
async def detail(asset_id: ID, owner: Owner, db: LibraryDB):
    row = await owned_asset(db, owner, asset_id)
    return {**asset_data(row), "linked_chunks": await linked_chunks(db, owner, row)}


@router.get("/assets/{asset_id}/image")
async def image(asset_id: ID, owner: Owner, db: LibraryDB):
    row = await owned_asset(db, owner, asset_id)
    if row.storage_key is None:
        raise HTTPException(404, "Image not found.")
    try:
        data = await asyncio.to_thread(
            AssetStorage(owner).read, row.storage_key, row.image_size_bytes
        )
    except FileNotFoundError:
        raise HTTPException(404, "Image not found.") from None
    except (OSError, ValueError):
        raise HTTPException(503, "Private image is unavailable.") from None
    return Response(
        data,
        media_type="image/png",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": 'inline; filename="asset.png"',
        },
    )


@router.post("/assets/{asset_id}/explain")
async def explain(
    asset_id: ID,
    owner: Owner,
    db: LibraryDB,
    gateway: Gateway,
    body: ExplainRequest | None = None,
):
    return await service.explain(db, owner, asset_id, body or ExplainRequest(), gateway)


@router.post("/assets/{asset_id}/vqa")
async def vqa(
    asset_id: ID, body: QuestionRequest, owner: Owner, db: LibraryDB, gateway: Gateway
):
    return await service.explain(
        db, owner, asset_id, body, gateway, question=body.question
    )
