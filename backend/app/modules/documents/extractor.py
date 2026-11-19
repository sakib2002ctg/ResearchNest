from __future__ import annotations

import io
import math
import multiprocessing
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import BinaryIO

LOW_TEXT_CHARACTERS = 24
MAX_PAGE_TEXT = 200_000
OCR_TIMEOUT_SECONDS = 8.0
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
MAX_DOCUMENT_PAGES = 1_000
MAX_DOCUMENT_CHARACTERS = 20_000_000
MAX_EXTRACTION_SECONDS = 120
_HEADING_RE = re.compile(r"^(?:\d+(?:\.\d+)*[.)]?\s+)?\S.{0,180}$")


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    raw_text: str
    ocr_used: bool
    section_heading: str | None


def _heading(text: str) -> str | None:
    for line in text.splitlines():
        value = " ".join(line.split()).strip()
        if not value or len(value) > 200:
            continue
        words = value.split()
        if len(words) <= 14 and (
            value.isupper()
            or (len(words) <= 8 and value[:1].isupper() and _HEADING_RE.match(value))
            or re.match(r"^\d+(?:\.\d+)*[.)]?\s+", value)
        ):
            return value
    # A short leading line is also useful for uncased scripts such as Bangla.
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if 0 < len(first_line) <= 100 and len(first_line.split()) <= 10:
        return first_line
    return None


def _ocr_page(page) -> str | None:
    if shutil.which("tesseract") is None:
        return None
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return None
    try:
        import fitz

        width, height = page.rect.width, page.rect.height
        if (
            not math.isfinite(width)
            or not math.isfinite(height)
            or width <= 0
            or height <= 0
        ):
            return None
        scale = min(
            1.5, 3000 / max(width, height), math.sqrt(4_000_000 / (width * height))
        )
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
        text = pytesseract.image_to_string(
            image, timeout=OCR_TIMEOUT_SECONDS, lang="eng+ben"
        )
        return text if isinstance(text, str) else None
    except Exception:
        return None


def extract_pages(
    source: bytes | bytearray | memoryview | BinaryIO | Path | str,
) -> list[ExtractedPage]:
    """Extract bounded page text; OCR is optional and never required for indexing."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PDF extraction support is unavailable.") from exc
    if isinstance(source, (bytes, bytearray, memoryview)):
        payload = bytes(source)
    elif hasattr(source, "read"):
        stream = source
        stream.seek(0)
        payload = stream.read(MAX_DOCUMENT_BYTES + 1)
    else:
        payload = Path(source).read_bytes()
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_DOCUMENT_BYTES:
        raise ValueError("The PDF has no readable content.")
    document = fitz.open(stream=payload, filetype="pdf")
    try:
        deadline = monotonic() + MAX_EXTRACTION_SECONDS
        if document.is_encrypted or not 0 < document.page_count <= MAX_DOCUMENT_PAGES:
            raise ValueError("The PDF cannot be indexed.")
        pages: list[ExtractedPage] = []
        text_length = 0
        for index in range(document.page_count):
            if monotonic() > deadline:
                raise ValueError("PDF extraction exceeded the time limit.")
            page = document.load_page(index)
            text = page.get_text("text") or ""
            text = text.replace("\x00", "").strip()
            ocr_used = False
            if len("".join(text.split())) < LOW_TEXT_CHARACTERS:
                ocr_text = _ocr_page(page)
                if ocr_text and len("".join(ocr_text.split())) > len(
                    "".join(text.split())
                ):
                    text = ocr_text.replace("\x00", "").strip()
                    ocr_used = True
            if len(text) > MAX_PAGE_TEXT:
                raise ValueError("The PDF page text exceeds the indexing limit.")
            text_length += len(text)
            if text_length > MAX_DOCUMENT_CHARACTERS:
                raise ValueError("The PDF text exceeds the indexing limit.")
            pages.append(
                ExtractedPage(
                    page_number=index + 1,
                    raw_text=text,
                    ocr_used=ocr_used,
                    section_heading=_heading(text),
                )
            )
        return pages
    finally:
        document.close()


def _extract_child(payload: bytes, sender) -> None:
    try:
        sender.send(extract_pages(payload))
    except Exception:
        sender.send(None)
    finally:
        sender.close()


def extract_pages_bounded(payload: bytes) -> list[ExtractedPage]:
    """Run the native parser in a process that can be terminated on timeout."""
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_extract_child, args=(payload, sender), daemon=True
    )
    try:
        process.start()
        sender.close()
        if not receiver.poll(MAX_EXTRACTION_SECONDS + OCR_TIMEOUT_SECONDS + 10):
            raise TimeoutError("PDF extraction timed out.")
        pages = receiver.recv()
        if pages is None:
            raise ValueError("The PDF could not be extracted.")
        return pages
    finally:
        receiver.close()
        sender.close()
        if process.pid is not None:
            process.join(0.1)
            if process.is_alive():
                process.terminate()
                process.join(2)
