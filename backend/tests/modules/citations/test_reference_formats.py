from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.modules.citations.formatter import format_citations, format_entry
from app.modules.citations.interchange import (
    export_bibtex,
    export_ris,
    parse_bibtex,
    parse_ris,
)
from app.modules.citations.schemas import CitationInput


def reference(**changes):
    data = dict(
        id=1,
        user_paper_id=None,
        cite_key="lovelace2026engine",
        entry_type="article",
        title="A Study of Analytical Engines",
        authors=["Ada Lovelace", "Charles Babbage"],
        year=2026,
        venue="Computing Research",
        volume="12",
        issue="3",
        pages="41-59",
        doi="10.1234/engine",
        url="https://example.org/paper",
        publisher=None,
        is_verified=True,
    )
    data.update(changes)
    return SimpleNamespace(**data)


@pytest.mark.parametrize("style", ["apa", "ieee", "mla", "chicago", "harvard"])
def test_five_styles_have_real_metadata_and_stable_keys(style):
    row = reference()
    result = format_citations([row], style)
    entry = result["entries"][0]
    assert entry["citation_id"] == 1 and entry["cite_key"] == row.cite_key
    assert row.title in entry["bibliography"]
    assert row.venue in entry["bibliography"]
    assert "2026" in entry["bibliography"] and row.doi in entry["bibliography"]
    assert row.pages in entry["bibliography"]
    assert result["bibliography"] == [entry["bibliography"]]
    assert (
        ("Lovelace" in entry["in_text"])
        if style != "ieee"
        else entry["in_text"] == "[1]"
    )
    if style == "apa":
        assert "Lovelace, A., & Babbage, C. (2026)." in entry["bibliography"]
        assert entry["in_text"] == "(Lovelace & Babbage, 2026)"
    if style == "mla":
        assert entry["in_text"] == "(Lovelace and Babbage)"
        assert "vol. 12, no. 3" in entry["bibliography"]
    if style == "chicago":
        assert entry["in_text"] == "(Lovelace and Babbage 2026)"


def test_ieee_numbering_preserves_selected_order_and_missing_metadata_is_honest():
    rows = [
        reference(id=9),
        reference(
            id=2,
            cite_key="unknown",
            authors=[],
            year=None,
            venue=None,
            doi=None,
            is_verified=False,
        ),
    ]
    result = format_citations(rows, "ieee")
    assert [e["citation_id"] for e in result["entries"]] == [9, 2]
    assert [e["in_text"] for e in result["entries"]] == ["[1]", "[2]"]
    assert "n.d." in result["entries"][1]["bibliography"]
    assert any("Missing authors" in warning for warning in result["warnings"])
    assert any("Missing publication year" in warning for warning in result["warnings"])
    assert "Unknown Author" not in str(result)


@pytest.mark.parametrize("style", ["apa", "ieee", "mla", "chicago", "harvard"])
def test_book_templates_use_publisher_and_many_authors_are_bounded(style):
    row = reference(
        entry_type="book",
        publisher="Research Press",
        venue=None,
        authors=[f"Author {n}" for n in range(25)],
        doi=None,
    )
    result = format_citations([row], style)
    assert "Research Press" in result["entries"][0]["bibliography"]
    assert "et al." in result["entries"][0]["in_text"] if style != "ieee" else True


def test_formatter_rejects_unknown_styles():
    with pytest.raises(ValueError):
        format_entry(reference(), "invented")


@pytest.mark.parametrize(
    "exporter,parser", [(export_bibtex, parse_bibtex), (export_ris, parse_ris)]
)
def test_reference_interchange_round_trip(exporter, parser):
    row = reference(
        title="Research & Evidence: {A} বাংলা 50%",
        authors=["Lovelace, Ada", "Charles Babbage"],
    )
    content = exporter([row])
    parsed = parser(content)
    assert len(parsed) == 1
    imported = parsed[0]
    assert imported.title == row.title
    assert imported.cite_key == row.cite_key
    assert imported.authors == row.authors
    assert imported.doi == row.doi
    assert imported.year == row.year and imported.pages == row.pages


def test_bibtex_nested_braces_quoted_values_and_comments():
    parsed = parse_bibtex(
        "% header\n@article{key2026, title = {A {Protected} Title}, "
        'author="Ada Lovelace and Charles Babbage", year=2026, doi={10.1234/test}}'
    )
    assert parsed[0].title == "A Protected Title"
    assert parsed[0].authors == ["Ada Lovelace", "Charles Babbage"]
    assert parsed[0].doi == "10.1234/test"


@pytest.mark.parametrize(
    "content",
    [
        "",
        "not bibtex",
        "@article{broken",
        "@article{key, title=macro}",
        "@article{key, title={One} # {Two}}",
        "@string{month={May}}",
        "@article{key, title={One}, title={Two}}",
        "@article{key, year={bad}}",
        "@article{key, author={Someone}}",
        "@article{key, title={" + "{" * 35 + "x" + "}" * 36 + "}",
    ],
)
def test_bad_bibtex_is_rejected_without_macro_execution(content):
    with pytest.raises((ValueError, ValidationError)):
        parse_bibtex(content)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "TI  - Missing start\n",
        "TY  - JOUR\nTI  - No end",
        "TY  - JOUR\nER  -",
        "TY  - JOUR\nTI  - A paper\nPY  - nope\nER  -",
    ],
)
def test_bad_ris_is_rejected(content):
    with pytest.raises((ValueError, ValidationError)):
        parse_ris(content)


def test_ris_continuation_lines_are_text_and_no_header_injection_is_possible():
    parsed = parse_ris(
        "TY  - JOUR\nTI  - A long\n  continued title\n"
        "AU  - Ada Lovelace\nPY  - 2026/11/01\nER  -"
    )
    assert parsed[0].title == "A long continued title"
    with pytest.raises(ValidationError):
        CitationInput(title="Title\nER  -\nTY  - JOUR")


@pytest.mark.parametrize(
    "field,value",
    [
        ("user_id", 2),
        ("is_verified", True),
        ("cite_key", "bad}key"),
        ("doi", "javascript:fake"),
        ("url", "https://secret:password@example.org"),
        ("authors", ["Name\x00control"]),
        ("year", 999),
    ],
)
def test_untrusted_owner_verification_and_invalid_metadata_are_rejected(field, value):
    with pytest.raises(ValidationError):
        CitationInput(title="A paper", **{field: value})
