from __future__ import annotations

import hashlib
import math
import multiprocessing
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol


class EmbeddingProvider(Protocol):
    model_name: str
    dimension: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashEmbeddingProvider:
    """Offline deterministic embeddings for tests and local development."""

    def __init__(self, dimension: int = 384, model_name: str = "hash-384") -> None:
        if not 8 <= dimension <= 4096:
            raise ValueError("Embedding dimension is outside the supported range.")
        self.dimension = dimension
        self.model_name = model_name

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            for token in text.casefold().split():
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimension
                sign = 1.0 if digest[4] & 1 else -1.0
                vector[index] += sign * (0.5 + digest[5] / 255.0)
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


def _encode_local(model_path: str, texts: list[str], sender) -> None:
    # This optional adapter runs in a separate bounded process. Its process
    # environment blocks Hugging Face network/model downloads.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(model_path, local_files_only=True, device="cpu")
        if int(model.get_sentence_embedding_dimension()) != 384:
            sender.send(None)
            return
        rows = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        sender.send([list(map(float, row)) for row in rows])
    except Exception:
        sender.send(None)
    finally:
        sender.close()


class SentenceTransformerProvider:
    """Optional local model hook; no dependency/model is loaded during tests."""

    dimension = 384

    def __init__(self, model_name: str, dimension: int = 384) -> None:
        if dimension != self.dimension:
            raise ValueError("Local embedding models must produce 384 dimensions.")
        self._model_path = str(Path(model_name).resolve())
        self.model_name = f"sentence-transformers:{Path(model_name).name}"[:128]

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not Path(self._model_path).is_dir():
            raise RuntimeError("The local embedding model is unavailable.")
        context = multiprocessing.get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(
            target=_encode_local,
            args=(self._model_path, list(texts), sender),
            daemon=True,
        )
        try:
            process.start()
            sender.close()
            if not receiver.poll(30):
                raise TimeoutError("Local embedding generation timed out.")
            result = receiver.recv()
            if result is None:
                raise RuntimeError("The local embedding model is unavailable.")
            return result
        finally:
            receiver.close()
            sender.close()
            if process.pid is not None:
                process.join(0.1)
                if process.is_alive():
                    process.terminate()
                    process.join(2)

    def close(self) -> None:
        pass
