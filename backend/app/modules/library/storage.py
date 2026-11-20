"""Private PDF validation, malware scanning, and filesystem storage."""

import csv
import hashlib
import io
import os
import re
import secrets
import socket
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import BinaryIO

from pypdf import PdfReader
from pypdf.errors import PyPdfError
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, StreamObject

from app.core.config import settings

MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_PAGES = 1_000
MAX_GRAPH_OBJECTS = 50_000
CHUNK_BYTES = 64 * 1024
_PDF_KEY = re.compile(r"[0-9a-f]{64}\.pdf")
_PDF_HEADER = re.compile(rb"%PDF-(?:1\.[0-7]|2\.0)[\r\n]")
_ACTIVE_KEYS = {
    "/AA",
    "/AcroForm",
    "/AF",
    "/EF",
    "/EmbeddedFiles",
    "/JavaScript",
    "/JS",
    "/OpenAction",
    "/RichMediaContent",
    "/XFA",
}
_ACTIVE_TYPES = {
    "/3D",
    "/EmbeddedFile",
    "/FileAttachment",
    "/GoToE",
    "/GoToR",
    "/ImportData",
    "/JavaScript",
    "/Launch",
    "/Movie",
    "/Rendition",
    "/RichMedia",
    "/Screen",
    "/Sound",
    "/SubmitForm",
}


class InvalidPDF(ValueError):
    pass


class PDFTooLarge(InvalidPDF):
    pass


class ScannerUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredPDF:
    key: str
    size: int
    sha256: str
    pages: int


def _is_link(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    return stat.S_ISLNK(info.st_mode) or bool(
        attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def _harden_windows_directory(path: Path) -> None:
    system_root = os.environ.get("SystemRoot")
    if not system_root:
        raise OSError("Could not secure PDF storage directory.")
    system32 = Path(system_root) / "System32"
    whoami = system32 / "whoami.exe"
    icacls = system32 / "icacls.exe"
    try:
        identity = subprocess.run(
            [str(whoami), "/user", "/fo", "csv", "/nh"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
        principals = next(csv.reader(io.StringIO(identity.stdout)), [])
        service_sid = principals[-1].strip()
        if not service_sid.startswith("S-1-"):
            raise ValueError("Invalid service account SID.")
        subprocess.run(
            [
                str(icacls),
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"*{service_sid}:(OI)(CI)F",
                "*S-1-5-18:(OI)(CI)F",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError, csv.Error, IndexError, ValueError):
        raise OSError("Could not secure PDF storage directory.") from None


class PDFStorage:
    key_pattern = _PDF_KEY

    def __init__(self, root: Path) -> None:
        self.root = root.absolute()

    def _path(self, key: str, *, create: bool = False) -> Path:
        if not self.key_pattern.fullmatch(key):
            raise OSError("Invalid PDF storage key.")
        for directory in (*reversed(self.root.parents), self.root):
            try:
                info = directory.lstat()
            except FileNotFoundError:
                if not create:
                    raise
                directory.mkdir(mode=0o700, exist_ok=True)
                info = directory.lstat()
            if _is_link(info) or not stat.S_ISDIR(info.st_mode):
                raise OSError("Invalid PDF storage directory.")
        if create and os.name == "nt":
            _harden_windows_directory(self.root)
        if os.name == "posix" and self.root.stat().st_mode & 0o077:
            raise OSError("PDF storage directory permissions are too broad.")
        return self.root / key

    def store(self, stream: BinaryIO, pages: int) -> StoredPDF:
        key = hashlib.sha256(secrets.token_bytes(32)).hexdigest() + ".pdf"
        path = self._path(key, create=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        digest = hashlib.sha256()
        size = 0
        stream.seek(0)
        descriptor = os.open(path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as output:
                for block in iter(lambda: stream.read(CHUNK_BYTES), b""):
                    size += len(block)
                    if size > MAX_PDF_BYTES:
                        raise PDFTooLarge("The PDF exceeds the upload limit.")
                    digest.update(block)
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return StoredPDF(key, size, digest.hexdigest(), pages)

    def open(self, key: str, size: int) -> BinaryIO:
        path = self._path(key)
        expected = path.lstat()
        if _is_link(expected) or not stat.S_ISREG(expected.st_mode):
            raise OSError("Invalid PDF storage object.")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags)
        try:
            actual = os.fstat(descriptor)
            if (
                not stat.S_ISREG(actual.st_mode)
                or not os.path.samestat(expected, actual)
                or actual.st_size != size
            ):
                raise OSError("Invalid PDF storage object.")
            return os.fdopen(descriptor, "rb")
        except BaseException:
            os.close(descriptor)
            raise

    def remove(self, key: str) -> None:
        """Remove a stored object if present so queue retries are safe."""
        try:
            path = self._path(key)
            info = path.lstat()
            if _is_link(info) or not stat.S_ISREG(info.st_mode):
                raise OSError("Invalid PDF storage object.")
            path.unlink()
        except FileNotFoundError:
            pass


def storage_from_settings() -> PDFStorage:
    return PDFStorage(Path(settings.PDF_STORAGE_ROOT))


def _scan_with_clamav(stream: BinaryIO, host: str, port: int, timeout: float) -> None:
    deadline = monotonic() + timeout

    def set_remaining_timeout(connection: socket.socket) -> None:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError
        connection.settimeout(remaining)

    try:
        with socket.create_connection((host, port), timeout=timeout) as connection:
            set_remaining_timeout(connection)
            connection.sendall(b"zINSTREAM\x00")
            stream.seek(0)
            for chunk in iter(lambda: stream.read(CHUNK_BYTES), b""):
                set_remaining_timeout(connection)
                connection.sendall(len(chunk).to_bytes(4, "big") + chunk)
            set_remaining_timeout(connection)
            connection.sendall(b"\x00\x00\x00\x00")

            reply = bytearray()
            while len(reply) < 1_024 and b"\x00" not in reply:
                set_remaining_timeout(connection)
                data = connection.recv(1_024 - len(reply))
                if not data:
                    break
                reply.extend(data)
    except OSError:
        raise ScannerUnavailable("PDF scanning is unavailable.") from None

    if reply == b"stream: OK\x00":
        return
    if reply.startswith(b"stream: ") and reply.endswith(b" FOUND\x00"):
        raise InvalidPDF("The PDF did not pass the malware scan.")
    raise ScannerUnavailable("PDF scanning is unavailable.")


def _validate_content(root: DictionaryObject) -> None:
    remaining = MAX_GRAPH_OBJECTS
    pending = [root]
    seen_references: set[tuple[int, int]] = set()
    seen_containers: set[int] = set()
    while pending:
        if remaining <= 0:
            raise InvalidPDF("The PDF structure exceeds the validation limit.")
        remaining -= 1
        value = pending.pop()
        if isinstance(value, IndirectObject):
            reference = (value.idnum, value.generation)
            if reference in seen_references:
                continue
            seen_references.add(reference)
            value = value.get_object()
        if isinstance(value, (DictionaryObject, ArrayObject)):
            if id(value) in seen_containers:
                continue
            seen_containers.add(id(value))
        if isinstance(value, DictionaryObject):
            if _ACTIVE_KEYS.intersection(value) or any(
                str(value.get(field)) in _ACTIVE_TYPES
                for field in ("/S", "/Subtype", "/Type")
            ):
                raise InvalidPDF("The PDF contains unsupported active content.")
            if isinstance(value, StreamObject) and "/F" in value:
                raise InvalidPDF("The PDF contains an external stream.")
            pending.extend(value.values())
        elif isinstance(value, ArrayObject):
            pending.extend(value)
        if len(pending) > MAX_GRAPH_OBJECTS:
            raise InvalidPDF("The PDF structure exceeds the validation limit.")


def _page_count(root: DictionaryObject) -> int:
    pages = root.raw_get("/Pages")
    pending = [pages]
    visited: set[tuple[int, int]] = set()
    count = 0
    while pending:
        reference = pending.pop()
        if not isinstance(reference, IndirectObject):
            raise InvalidPDF("The PDF page tree is invalid.")
        identifier = (reference.idnum, reference.generation)
        if identifier in visited or len(visited) >= MAX_PAGES * 2:
            raise InvalidPDF("The PDF page tree exceeds the validation limit.")
        visited.add(identifier)
        node = reference.get_object()
        if not isinstance(node, DictionaryObject):
            raise InvalidPDF("The PDF page tree is invalid.")
        kind = node.get("/Type")
        if kind == "/Page":
            count += 1
            if count > MAX_PAGES:
                raise InvalidPDF("The PDF exceeds the page limit.")
        elif kind == "/Pages":
            children = node["/Kids"]
            if not isinstance(children, ArrayObject) or len(children) > MAX_PAGES:
                raise InvalidPDF("The PDF page tree exceeds the validation limit.")
            pending.extend(reversed(children))
        else:
            raise InvalidPDF("The PDF page tree is invalid.")
    if count == 0:
        raise InvalidPDF("The PDF has no pages.")
    return count


def validate_pdf(stream: BinaryIO) -> int:
    """Check bounded structural metadata without decoding page content."""
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    if size > MAX_PDF_BYTES:
        raise PDFTooLarge("The PDF exceeds the upload limit.")

    stream.seek(0)
    if not _PDF_HEADER.match(stream.read(16)):
        raise InvalidPDF("The file does not have a valid PDF signature.")
    stream.seek(max(0, size - 1_024))
    if not stream.read().rstrip(b" \t\r\n").endswith(b"%%EOF"):
        raise InvalidPDF("The PDF is incomplete.")

    if settings.CLAMAV_HOST:
        _scan_with_clamav(
            stream,
            settings.CLAMAV_HOST,
            settings.CLAMAV_PORT,
            settings.CLAMAV_TIMEOUT_SECONDS,
        )
    elif settings.APP_ENV in {"production", "staging"}:
        raise ScannerUnavailable("PDF scanning is unavailable.")

    stream.seek(0)
    try:
        with PdfReader(
            stream,
            strict=True,
            root_object_recovery_limit=128,
            xref_stream_maximum_entries=MAX_GRAPH_OBJECTS,
        ) as reader:
            if reader.is_encrypted:
                raise InvalidPDF("Encrypted PDFs are not supported.")
            root = reader.root_object
            count = _page_count(root)
            _validate_content(root)
            return count
    except InvalidPDF:
        raise
    except (PyPdfError, KeyError, ValueError, TypeError, RecursionError, OSError):
        raise InvalidPDF("The PDF structure is invalid.") from None
