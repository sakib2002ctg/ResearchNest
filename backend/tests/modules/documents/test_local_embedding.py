import pytest

from app.modules.documents.embeddings import SentenceTransformerProvider


def test_local_embedding_does_not_download_an_unavailable_model(tmp_path):
    provider = SentenceTransformerProvider(str(tmp_path / "missing-model"))
    with pytest.raises(RuntimeError, match="unavailable"):
        provider.embed(["Private research"])
    provider.close()


def test_pgvector_models_require_the_fixed_dimension(tmp_path):
    with pytest.raises(ValueError, match="384"):
        SentenceTransformerProvider(str(tmp_path), dimension=768)
