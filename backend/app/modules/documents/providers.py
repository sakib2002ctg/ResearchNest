from app.core.config import settings
from app.modules.documents.embeddings import (
    HashEmbeddingProvider,
    SentenceTransformerProvider,
)


def embedding_provider():
    if settings.DOCUMENT_EMBEDDING_PROVIDER == "hash":
        return HashEmbeddingProvider()
    model = settings.DOCUMENT_EMBEDDING_MODEL_PATH
    if model is None or not model.is_dir():
        raise ValueError(
            "Set DOCUMENT_EMBEDDING_MODEL_PATH to an installed local model."
        )
    return SentenceTransformerProvider(str(model.resolve()), dimension=384)
