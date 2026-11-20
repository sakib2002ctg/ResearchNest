import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import Base


@pytest.fixture
def db(tmp_path, monkeypatch):
    url = URL.create("sqlite", database=str(tmp_path / "assistant.sqlite"))
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    monkeypatch.setattr(settings, "DATABASE_URL", str(url))
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "AI_DEFAULT_PROVIDER", "offline")
    monkeypatch.setattr(settings, "DOCUMENT_EMBEDDING_PROVIDER", "hash")
    monkeypatch.setattr("app.main.engine", engine)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()
