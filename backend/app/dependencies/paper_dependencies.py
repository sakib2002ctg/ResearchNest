from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.repositories.paper_repository import PaperRepository
from app.services.paper_service import PaperService


def get_paper_repository(
    db: Session = Depends(get_db),
) -> PaperRepository:
    return PaperRepository(db)


def get_paper_service(
    repository: PaperRepository = Depends(get_paper_repository),
) -> PaperService:
    return PaperService(repository)
