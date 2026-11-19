import hashlib
import os
import re
import secrets

from app.core.config import settings
from app.modules.library.storage import PDFStorage


class AssetStorage(PDFStorage):
    key_pattern = re.compile(r"[0-9a-f]{64}\.png")

    def __init__(self, owner):
        if type(owner) is not int or owner <= 0:
            raise ValueError("Invalid asset owner.")
        super().__init__(settings.ASSET_STORAGE_ROOT / str(owner))

    @staticmethod
    def allocate_key():
        return hashlib.sha256(secrets.token_bytes(32)).hexdigest() + ".png"

    def save(self, image, key=None):
        if not image.startswith(b"\x89PNG\r\n\x1a\n") or len(image) > 4 * 1024 * 1024:
            raise ValueError("Invalid asset image.")
        key = key or self.allocate_key()
        path = self._path(key, create=True)
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(image)
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return key

    def read(self, key, size):
        if size is None or not 0 < size <= 4 * 1024 * 1024:
            raise ValueError("Invalid asset image size.")
        with self.open(key, size) as stream:
            return stream.read(size)
