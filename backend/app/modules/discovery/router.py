from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.discovery_database import get_discovery_db
from app.dependencies.current_user import get_current_user
from app.models.user import User
from app.modules.discovery.gateway import (
    DiscoveryGateway,
    InvalidPaperReference,
    PaperNotFound,
)
from app.modules.discovery.library import PaperIdentityConflict, save_to_library
from app.modules.discovery.providers import ProviderUnavailable
from app.modules.discovery.schemas import (
    DiscoveryPaper,
    DiscoverySearchRequest,
    DiscoverySearchResponse,
    SaveToLibraryRequest,
    SaveToLibraryResponse,
)

router = APIRouter(prefix="/discovery", tags=["discovery"])


def get_discovery_gateway(request: Request) -> DiscoveryGateway:
    return request.app.state.discovery_gateway


def _get_owner_id(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> int:
    owner_id = current_user.id
    # Release the authentication query's connection before awaiting a provider.
    db.rollback()
    return owner_id


@router.post("/search")
async def search(
    query: DiscoverySearchRequest,
    gateway: DiscoveryGateway = Depends(get_discovery_gateway),
) -> DiscoverySearchResponse:
    try:
        return await gateway.search(query)
    except ProviderUnavailable as error:
        raise HTTPException(503, str(error)) from None


@router.get("/doi/{doi:path}")
async def lookup_doi(
    doi: str, gateway: DiscoveryGateway = Depends(get_discovery_gateway)
) -> DiscoveryPaper:
    try:
        return await gateway.lookup_doi(doi)
    except InvalidPaperReference as error:
        raise HTTPException(422, str(error)) from None
    except PaperNotFound as error:
        raise HTTPException(404, str(error)) from None
    except ProviderUnavailable as error:
        raise HTTPException(503, str(error)) from None


@router.post("/save-to-library")
async def save(
    reference: SaveToLibraryRequest,
    owner_id: int = Depends(_get_owner_id),
    gateway: DiscoveryGateway = Depends(get_discovery_gateway),
    db: AsyncSession = Depends(get_discovery_db),
) -> SaveToLibraryResponse:
    try:
        paper = await gateway.verify_reference(reference)
        return await db.run_sync(save_to_library, owner_id, paper)
    except InvalidPaperReference as error:
        raise HTTPException(422, str(error)) from None
    except PaperNotFound as error:
        raise HTTPException(404, str(error)) from None
    except PaperIdentityConflict as error:
        raise HTTPException(409, str(error)) from None
    except ProviderUnavailable as error:
        raise HTTPException(503, str(error)) from None
