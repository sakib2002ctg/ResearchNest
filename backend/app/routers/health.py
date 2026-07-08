from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.database.database import engine

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("")
def health():
    """
    Liveness probe.
    """
    return {"status": "healthy"}


@router.get("/ready")
def readiness():
    """
    Readiness probe.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ready",
            "database": "connected",
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable.",
        )
