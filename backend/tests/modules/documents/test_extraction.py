import fitz
import pytest

from app.modules.documents import extractor
from app.modules.documents.chunking import make_chunks
from app.modules.documents.embeddings import HashEmbeddingProvider


def create_pdf(page_texts):
    document = fitz.open()
    for text in page_texts:
        page = document.new_page()
        page.insert_text((72, 72), text, fontsize=11)
    payload = document.tobytes()
    document.close()
    return payload


def test_extracts_page_text_heading_and_number():
    pages = extractor.extract_pages(
        create_pdf(
            ["1 Introduction\nFirst page details.", "Another page text with details."]
        )
    )
    assert [page.page_number for page in pages] == [1, 2]
    assert "First page details" in pages[0].raw_text
    assert pages[0].section_heading == "1 Introduction"
    assert not any(page.ocr_used for page in pages)


def test_bilingual_chunking_preserves_page_boundaries_and_overlap():
    pages = [
        extractor.ExtractedPage(
            1, "বাংলা গবেষণা: " + ("মাঠের তথ্য ও গবেষণা। " * 190), False, "বাংলা গবেষণা"
        ),
        extractor.ExtractedPage(
            2,
            "English section: " + ("Independent page boundary text. " * 190),
            False,
            "English section",
        ),
    ]
    chunks = make_chunks(pages)
    assert {chunk.page_number for chunk in chunks} == {1, 2}
    assert all(len(chunk.content) <= 1600 for chunk in chunks)
    assert all(chunk.token_count == len(chunk.content.split()) for chunk in chunks)
    assert any("বাংলা" in chunk.content for chunk in chunks)
    page_one = [chunk for chunk in chunks if chunk.page_number == 1]
    page_two = [chunk for chunk in chunks if chunk.page_number == 2]
    assert page_one[-1].chunk_index + 1 == len(page_one)
    assert page_two[0].chunk_index == 0
    assert not any(
        chunk.page_number == 1 and "English section" in chunk.content
        for chunk in chunks
    )
    assert page_one[0].content[-100:] in page_one[1].content


def test_missing_tesseract_is_a_graceful_fallback(monkeypatch):
    monkeypatch.setattr(extractor.shutil, "which", lambda _: None)
    document = fitz.open(stream=create_pdf([""]), filetype="pdf")
    try:
        assert extractor._ocr_page(document[0]) is None
    finally:
        document.close()
    pages = extractor.extract_pages(create_pdf([""]))
    assert pages[0].raw_text == ""
    assert pages[0].ocr_used is False


def test_scanned_page_uses_successful_ocr(monkeypatch):
    monkeypatch.setattr(extractor, "_ocr_page", lambda page: "OCR বাংলা text")
    pages = extractor.extract_pages(create_pdf([""]))
    assert pages[0].ocr_used
    assert pages[0].raw_text == "OCR বাংলা text"


def test_pdf_bytes_are_validated_and_no_empty_chunks_are_created():
    with pytest.raises(ValueError):
        extractor.extract_pages(b"")
    with pytest.raises(Exception):
        extractor.extract_pages(b"not a PDF")
    assert make_chunks([extractor.ExtractedPage(1, "", False, None)]) == []


def test_hash_embeddings_are_deterministic_and_unit_normalized():
    provider = HashEmbeddingProvider()
    text = "বাংলা researchers and English terms"
    values = provider.embed([text, text])
    assert values[0] == values[1]
    assert len(values[0]) == 384
    assert abs(sum(x * x for x in values[0]) ** 0.5 - 1.0) < 1e-6


def test_total_character_limit_is_not_silently_truncated(monkeypatch):
    from app.modules.documents import chunking

    monkeypatch.setattr(chunking, "MAX_TOTAL_CHARACTERS", 10)
    with pytest.raises(ValueError, match="indexing limit"):
        make_chunks([extractor.ExtractedPage(1, "long text" * 5, False, None)])
