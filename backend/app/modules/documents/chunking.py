from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

MAX_CHUNK_CHARACTERS = 1600
CHUNK_OVERLAP_CHARACTERS = 240
MAX_CHUNKS_PER_PAGE = 2_000
MAX_TOTAL_CHUNKS = 50_000
MAX_TOTAL_CHARACTERS = 20_000_000
_WHITESPACE = re.compile(r"[\t\r\f\v ]+")
_JOINERS = {"\u200c", "\u200d", "\u09cd"}


def _inside_cluster(text: str, position: int) -> bool:
    if not 0 < position < len(text):
        return False
    return (
        unicodedata.category(text[position]).startswith("M")
        or text[position - 1] in _JOINERS
        or text[position] in _JOINERS
    )


@dataclass(frozen=True)
class ChunkData:
    page_number: int
    chunk_index: int
    section_heading: str | None
    content: str
    token_count: int


def _clean(value: str) -> str:
    return "\n".join(
        _WHITESPACE.sub(" ", line).strip() for line in value.splitlines()
    ).strip()


def _split(text: str) -> list[str]:
    text = _clean(text)
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text) and len(chunks) < MAX_CHUNKS_PER_PAGE:
        end = min(len(text), start + MAX_CHUNK_CHARACTERS)
        if end < len(text):
            boundary = max(text.rfind(" ", start, end), text.rfind("\n", start, end))
            if boundary > start + MAX_CHUNK_CHARACTERS // 2:
                end = boundary
            while end > start and _inside_cluster(text, end):
                end -= 1
            if end == start:
                raise ValueError("Text contains an unsupported grapheme cluster.")
        value = text[start:end].strip()
        if value:
            chunks.append(value)
        if end >= len(text):
            break
        next_start = max(start + 1, end - CHUNK_OVERLAP_CHARACTERS)
        while next_start > start + 1 and _inside_cluster(text, next_start):
            next_start -= 1
        while next_start < len(text) and text[next_start].isspace():
            next_start += 1
        start = next_start
    return chunks


def make_chunks(pages) -> list[ChunkData]:
    result: list[ChunkData] = []
    total_characters = 0
    for page in pages:
        page_chunks = _split(page.raw_text)
        total_characters += len(page.raw_text)
        if total_characters > MAX_TOTAL_CHARACTERS:
            raise ValueError("Document text exceeds the indexing limit.")
        if len(result) + len(page_chunks) > MAX_TOTAL_CHUNKS:
            raise ValueError("Document contains too many chunks.")
        for index, content in enumerate(page_chunks):
            result.append(
                ChunkData(
                    page_number=page.page_number,
                    chunk_index=index,
                    section_heading=page.section_heading,
                    content=content,
                    token_count=len(content.split()),
                )
            )
    return result
