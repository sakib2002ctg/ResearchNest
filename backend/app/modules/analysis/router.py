from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.models.analysis import Analysis, PaperComparison
from app.models.paper import UserPaper
from app.modules.ai.gateway import AIProviderGateway
from app.modules.ai.router import get_gateway, private_headers
from app.modules.ai.schemas import ID
from app.modules.analysis import service
from app.modules.analysis.repository import (
    analysis_data,
    comparison_access,
    comparison_data,
    saved_analysis,
    saved_comparison,
)
from app.modules.analysis.schemas import CompareRequest, Options
from app.modules.library.dependencies import LibraryDB, Owner

router = APIRouter(
    prefix="/analysis",
    tags=["Paper intelligence"],
    dependencies=[Depends(private_headers)],
)
Gateway = Annotated[AIProviderGateway, Depends(get_gateway)]


@router.post("/compare", status_code=201)
async def compare_papers(
    body: CompareRequest, owner: Owner, db: LibraryDB, gateway: Gateway
):
    return await service.compare(db, owner, body, gateway)


@router.get("/comparisons")
async def list_comparisons(
    owner: Owner,
    db: LibraryDB,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
):
    rows = list(
        await db.scalars(
            select(PaperComparison)
            .where(PaperComparison.user_id == owner)
            .order_by(PaperComparison.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return [
        await comparison_data(db, owner, row)
        for row in rows
        if await comparison_access(db, owner, row)
    ]


@router.get("/comparisons/{comparison_id}")
async def get_comparison(comparison_id: ID, owner: Owner, db: LibraryDB):
    return await comparison_data(
        db, owner, await saved_comparison(db, owner, comparison_id)
    )


@router.get("")
async def list_analyses(
    owner: Owner,
    db: LibraryDB,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
):
    rows = list(
        await db.scalars(
            select(Analysis)
            .join(
                UserPaper,
                (UserPaper.id == Analysis.user_paper_id) & (UserPaper.user_id == owner),
            )
            .where(Analysis.user_id == owner)
            .order_by(Analysis.updated_at.desc(), Analysis.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return [await analysis_data(db, owner, row) for row in rows]


@router.get("/{paper_id}")
async def get_analysis(
    paper_id: ID, owner: Owner, db: LibraryDB, language: Literal["en", "bn"] = "en"
):
    row = await saved_analysis(db, owner, paper_id, language)
    if row is None:
        raise HTTPException(404, "Analysis not found.")
    return await analysis_data(db, owner, row)


@router.post("/{paper_id}")
async def analyze_paper(
    paper_id: ID,
    owner: Owner,
    db: LibraryDB,
    gateway: Gateway,
    body: Options | None = None,
    language: Literal["en", "bn"] | None = None,
    force_refresh: bool | None = None,
):
    options = body or Options()
    if language is not None:
        options.language = language
    if force_refresh is not None:
        options.force_refresh = force_refresh
    return await service.analyze(db, owner, paper_id, options, gateway)
