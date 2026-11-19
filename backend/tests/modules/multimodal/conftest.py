import pytest

from app.core.config import settings
from tests.modules.ai import conftest as fixtures

db = fixtures.db


@pytest.fixture(autouse=True)
def asset_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ASSET_STORAGE_ROOT", tmp_path / "assets")
    monkeypatch.setattr(settings, "PDF_STORAGE_ROOT", tmp_path / "pdfs")
