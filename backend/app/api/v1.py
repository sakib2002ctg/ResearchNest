from fastapi import APIRouter

from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.papers import router as papers_router
from app.routers.research import router as research_router
from app.routers.users import router as users_router

api_router = APIRouter(prefix="/api/v1", tags=["API v1"])

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(papers_router)
api_router.include_router(research_router)
api_router.include_router(health_router)
