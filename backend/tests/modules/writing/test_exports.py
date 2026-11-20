import re
import zipfile
from io import BytesIO
from types import SimpleNamespace
from xml.etree import ElementTree

import fitz
import pytest

from app.modules.writing import exports
from app.modules.writing.exports import ExportError, export_document


def draft(content="## Introduction\n\nA supported statement [@smith2026].", **values):
    return SimpleNamespace(
        id=12,
        title=values.pop("title", "A research draft"),
        content_markdown=content,
        language=values.pop("language", "en"),
        cited_citation_ids=values.pop("cited_citation_ids", [7]),
        **values,
    )


def citation(**values):
    defaults = {
        "id": 7,
        "cite_key": "smith2026",
        "entry_type": "article",
        "title": "Reliable classification",
        "authors": ["Jane Smith"],
        "year": 2026,
        "venue": "Journal of Research",
        "volume": "12",
        "issue": "3",
        "pages": "20–30",
        "doi": "10.1234/example",
        "url": None,
        "publisher": "Research Press",
        "is_verified": True,
    }
    defaults.update(values)
    return SimpleNamespace(**defaults)


@pytest.mark.parametrize("style", ["apa", "ieee", "mla", "chicago", "harvard"])
def test_markdown_resolves_owned_placeholders_and_appends_style_bibliography(style):
    data, mime, name = export_document(draft(), [citation()], "md", style)
    text = data.decode("utf-8")
    assert name == "researchnest-writing-12.md"
    assert mime == "text/markdown; charset=utf-8"
    assert "## References" in text and "Reliable classification" in text
    assert "[@smith2026]" not in text
    assert "[1]" in text if style == "ieee" else "Smith" in text


@pytest.mark.parametrize(
    "content", ["Unowned [@foreign2026].", "Broken [@smith2026", "Bad [@x<script>]."]
)
def test_unknown_or_malformed_citations_never_export(content):
    with pytest.raises(ExportError, match="citation placeholder"):
        export_document(draft(content), [citation()], "md", "apa")


def test_missing_declared_rows_and_duplicate_keys_are_rejected():
    with pytest.raises(ExportError, match="no longer available"):
        export_document(draft(), [], "md", "apa")
    with pytest.raises(ExportError, match="Duplicate citation keys"):
        export_document(
            draft(cited_citation_ids=[7, 8]), [citation(), citation(id=8)], "md", "apa"
        )


def test_export_rechecks_owner_binding_when_supplied_owned_models():
    document = draft(user_id=1)
    with pytest.raises(ExportError, match="no longer available"):
        export_document(document, [citation(user_id=2)], "md", "apa")
    data, _, _ = export_document(document, [citation(user_id=1)], "md", "apa")
    assert "Reliable classification" in data.decode()


def test_export_accepts_the_full_database_citation_key_width():
    key = "s" * 100
    data, _, _ = export_document(
        draft(f"A statement [@{key}]."), [citation(cite_key=key)], "md", "ieee"
    )
    assert "A statement [1]." in data.decode()


def test_ieee_numbers_follow_manuscript_appearance_and_preserve_bibliography_mapping():
    jones = citation(
        id=8,
        cite_key="jones2025",
        authors=["Jane Jones"],
        year=2025,
        title="A second reference",
    )
    document = draft(
        "First [@jones2025], then [@smith2026], then [@jones2025].",
        cited_citation_ids=[7, 8],
    )
    data, _, _ = export_document(document, [citation(), jones], "md", "ieee")
    text = data.decode()
    assert "First [1], then [2], then [1]." in text
    bibliography = text.split("## References", 1)[1]
    assert bibliography.index("[1] J. Jones") < bibliography.index("[2] J. Smith")


def test_ieee_explicit_uncited_references_follow_appearing_references():
    jones = citation(
        id=8,
        cite_key="jones2025",
        authors=["Jane Jones"],
        year=2025,
        title="An uncited reference",
    )
    zane = citation(
        id=9,
        cite_key="zane2024",
        authors=["Jane Zane"],
        year=2024,
        title="The cited reference",
    )
    data, _, _ = export_document(
        draft("Evidence [@zane2024].", cited_citation_ids=[7, 8, 9]),
        [citation(), jones, zane],
        "md",
        "ieee",
    )
    text = data.decode()
    assert "Evidence [1]." in text
    bibliography = text.split("## References", 1)[1]
    assert bibliography.index("[1] J. Zane") < bibliography.index("[2] J. Smith")
    assert bibliography.index("[2] J. Smith") < bibliography.index("[3] J. Jones")


@pytest.mark.parametrize("style", ["apa", "mla", "chicago", "harvard"])
def test_author_date_bibliographies_sort_alphabetically_without_changing_attribution(
    style,
):
    jones = citation(
        id=8,
        cite_key="jones2025",
        authors=["Jane Jones"],
        year=2025,
        title="A second reference",
    )
    data, _, _ = export_document(
        draft("First [@smith2026], then [@jones2025].", cited_citation_ids=[7, 8]),
        [citation(), jones],
        "md",
        style,
    )
    text = data.decode()
    bibliography = text.split("## References", 1)[1]
    assert bibliography.index("Jones") < bibliography.index("Smith")
    assert "First (Smith" in text and "then (Jones" in text


@pytest.mark.parametrize("character", ["\x00", "\ud800", "\ufffe", "\uffff"])
def test_invalid_xml_characters_fail_before_formatting(character):
    with pytest.raises(ExportError, match="control characters"):
        export_document(draft("Invalid " + character), [citation()], "docx", "apa")


def test_latex_escapes_user_commands_special_characters_and_reference_metadata():
    doc = draft(
        "## Methods & results\n\n" + r"\input{/etc/passwd} 100%_$#{}~^ [@smith2026]",
        title=r"Test \write18{bad}",
    )
    data, mime, name = export_document(
        doc, [citation(title=r"Bad \input{secret} & safe")], "tex", "ieee"
    )
    text = data.decode()
    assert mime.startswith("application/x-tex") and name.endswith(".tex")
    assert r"\input{" not in text and r"\write18{" not in text
    assert r"\textbackslash{}input\{/etc/passwd\}" in text
    assert r"\subsection{Methods \& results}" in text
    assert r"100\%\_\$\#\{\}\textasciitilde{}\textasciicircum{}" in text
    assert "[1]" in text and "References" in text


def test_docx_contains_real_paragraphs_bibliography_and_no_external_relationships():
    data, mime, name = export_document(
        draft(
            "## Methods\n\nA paragraph [@smith2026].\n\n- First point\n\n"
            "```text\n<xml>literal</xml>\n```"
        ),
        [citation()],
        "docx",
        "apa",
    )
    assert name.endswith(".docx") and "wordprocessingml" in mime
    with zipfile.ZipFile(BytesIO(data)) as archive:
        xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        text = " ".join(root.itertext())
        assert "A research draft" in text and "Reliable classification" in text
        assert "Methods" in text and "First point" in text
        assert "<xml>literal</xml>" in text
        assert "[@smith2026]" not in text
        rels = archive.read("word/_rels/document.xml.rels")
        assert b'TargetMode="External"' not in rels


def test_pdf_is_real_multi_page_document_with_bibliography_and_no_resource_fetches():
    content = (
        "## Introduction\n\n"
        + ("A supported finding about classification [@smith2026]. " * 30 + "\n\n") * 12
    )
    data, mime, name = export_document(draft(content), [citation()], "pdf", "ieee")
    assert (
        data.startswith(b"%PDF") and mime == "application/pdf" and name.endswith(".pdf")
    )
    with fitz.open(stream=data, filetype="pdf") as document:
        assert 1 < len(document) < 200
        text = "\n".join(page.get_text(flags=0) for page in document)
        assert "A research draft" in text and "[1]" in text
        assert "References" in text and "Reliable classification" in text
        assert "[@smith2026]" not in text
        assert document.metadata["title"] == "A research draft"
        assert all(not page.get_links() for page in document)
        assert not document.embfile_count()


def test_pdf_treats_html_resource_payload_as_plain_text():
    content = (
        '<img src="file:///private/secret.pdf"><script>alert(1)</script> [@smith2026]'
    )
    data, _, _ = export_document(draft(content), [citation()], "pdf", "apa")
    with fitz.open(stream=data, filetype="pdf") as document:
        text = document[0].get_text(flags=0)
        assert "file:///private/secret.pdf" in text and "alert(1)" in text
        assert all(not page.get_images() for page in document)


@pytest.mark.parametrize("format", ["md", "tex", "docx", "pdf"])
def test_bangla_export_is_offline_unicode_and_pdf_has_bengali_font_glyphs(format):
    title = "বাংলা গবেষণা"
    doc = draft(
        "## পদ্ধতি\n\nউদ্ভিদ সূর্যালোক থেকে শক্তি উৎপন্ন করে। [@smith2026]",
        title=title,
        language="bn",
    )
    data, _, _ = export_document(doc, [citation()], format, "apa")
    if format in {"md", "tex"}:
        assert title in data.decode() and "তথ্যসূত্র" in data.decode()
    elif format == "docx":
        with zipfile.ZipFile(BytesIO(data)) as archive:
            assert title in archive.read("word/document.xml").decode()
    else:
        with fitz.open(stream=data, filetype="pdf") as document:
            assert document.metadata["title"] == title
            text = "\n".join(page.get_text() for page in document)
            assert re.search(r"[\u0980-\u09ff]", text)
            assert any(
                "Bengali" in font[3] or "Bangla" in font[3]
                for page in document
                for font in page.get_fonts()
            )
            assert document[0].get_pixmap().width > 0


def test_export_size_controls_and_page_limit(monkeypatch):
    with pytest.raises(ExportError, match="size limit"):
        export_document(draft("x" * (200000 + 1)), [citation()], "md", "apa")
    with pytest.raises(ExportError, match="control characters"):
        export_document(draft("A bad\x00draft"), [citation()], "md", "apa")
    monkeypatch.setattr(exports, "MAX_PDF_PAGES", 1)
    with pytest.raises(ExportError, match="page limit"):
        export_document(draft("A paragraph.\n\n" * 300), [citation()], "pdf", "apa")


@pytest.mark.parametrize("format,style", [("html", "apa"), ("pdf", "unrecognized")])
def test_unsupported_formats_and_styles_are_rejected(format, style):
    with pytest.raises(ExportError, match="Unsupported"):
        export_document(draft(), [citation()], format, style)
