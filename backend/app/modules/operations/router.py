from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.modules.operations.health import VERSION, readiness

router = APIRouter(tags=["Operational health"])


@router.get("/health")
async def liveness():
    return JSONResponse(
        {"status": "ok", "version": VERSION}, headers={"Cache-Control": "no-store"}
    )


@router.get("/health/ready")
async def ready(request: Request):
    body, status = await readiness(request.app)
    return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store"})
