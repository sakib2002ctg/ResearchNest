import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database.database import Base
from app.database.discovery_database import create_discovery_engine


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def factory(tmp_path, monkeypatch):
    from sqlalchemy.engine import URL

    url = URL.create("sqlite", database=str(tmp_path / "processor.sqlite"))
    engine = create_discovery_engine(url)
    monkeypatch.setattr("app.core.config.settings.PDF_STORAGE_ROOT", tmp_path / "pdfs")
    monkeypatch.setattr("app.core.config.settings.APP_ENV", "test")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()
