from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.discovery_database import get_discovery_db
from app.dependencies.current_user import get_current_user
from app.models.user import User


def get_library_owner(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> int:
    owner_id = user.id
    db.rollback()
    return owner_id


Owner = Annotated[int, Depends(get_library_owner)]
LibraryDB = Annotated[AsyncSession, Depends(get_discovery_db)]
