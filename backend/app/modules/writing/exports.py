"""In-memory academic draft exports without TeX processes or remote resources."""

import html
import re
from io import BytesIO
from typing import Literal

import fitz

from app.modules.citations.formatter import format_citations

ExportFormat = Literal["md", "tex", "docx", "pdf"]
MAX_CONTENT_CHARACTERS = 200000
MAX_EXPORT_CHARACTERS = 400000
MAX_PDF_PAGES = 200
_CITE_KEY = r"[A-Za-z][A-Za-z0-9:_-]{0,99}"
_CITATION = re.compile(r"\[@(" + _CITE_KEY + r")\]")
_INVALID_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")
_MIME_TYPES = {
    "md": "text/markdown; charset=utf-8",
    "tex": "application/x-tex; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


class ExportError(ValueError):
    """A draft cannot be exported faithfully within the supported limits."""


def _checked_text(value, *, limit):
    if not isinstance(value, str) or len(value) > limit:
        raise ExportError("Document text exceeds the export size limit.")
    if _INVALID_XML.search(value):
        raise ExportError("Remove unsupported control characters before exporting.")
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _resolved(document, citations, style):
    title = _checked_text(document.title, limit=1000)
    content = _checked_text(document.content_markdown, limit=MAX_CONTENT_CHARACTERS)
    if len(citations) > 500:
        raise ExportError("A draft may export at most 500 references.")
    expected = set(document.cited_citation_ids)
    actual = {citation.id for citation in citations}
    if expected != actual or len(actual) != len(citations):
        raise ExportError("One or more draft references are no longer available.")
    owner = getattr(document, "user_id", None)
    if owner is not None and any(
        getattr(citation, "user_id", None) != owner for citation in citations
    ):
        raise ExportError("One or more draft references are no longer available.")
    # The HTTP use case supplies owner-scoped rows. Verify the declaration again
    # so a partial caller result cannot silently omit a bibliography entry.
    if style == "ieee":
        appearance = dict.fromkeys(_CITATION.findall(title + "\n" + content))
        positions = {key: number for number, key in enumerate(appearance)}
        # Stable sorting puts explicitly selected but uncited references last.
        citations = sorted(
            citations, key=lambda row: positions.get(row.cite_key, len(positions))
        )
    formatted = format_citations(citations, style)
    references = {entry["cite_key"]: entry for entry in formatted["entries"]}
    if len(references) != len(citations):
        raise ExportError("Duplicate citation keys cannot be exported.")

    def replace(match):
        entry = references.get(match[1])
        if entry is None:
            raise ExportError("The draft contains an unknown citation placeholder.")
        return entry["in_text"]

    # Validate title references too, even though academic titles rarely cite work.
    title, content = _CITATION.sub(replace, title), _CITATION.sub(replace, content)
    if "[@" in content or "[@" in title:
        raise ExportError("The draft contains a malformed citation placeholder.")
    entries = formatted["entries"]
    if style != "ieee":
        entries = sorted(
            entries,
            key=lambda entry: (
                re.sub(r"^[^\w]+", "", entry["bibliography"]).casefold(),
                entry["cite_key"],
            ),
        )
    bibliography = [
        _checked_text(entry["bibliography"], limit=10000) for entry in entries
    ]
    if sum(map(len, bibliography)) + len(content) + len(title) > MAX_EXPORT_CHARACTERS:
        raise ExportError("Document and bibliography exceed the export size limit.")
    return title, content, bibliography


def _blocks(content):
    """Render headings, paragraphs, lists and fenced code as escaped plain text."""
    paragraph = []
    in_code = False
    code = []
    for line in content.split("\n"):
        if line.startswith("```"):
            if paragraph:
                yield "paragraph", "\n".join(paragraph)
                paragraph = []
            if in_code:
                yield "code", "\n".join(code)
                code = []
            in_code = not in_code
            continue
        if in_code:
            code.append(line)
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        bullet = re.match(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+)$", line)
        if heading or bullet or not line.strip():
            if paragraph:
                yield "paragraph", "\n".join(paragraph)
                paragraph = []
            if heading:
                yield "heading" + str(len(heading[1])), heading[2]
            elif bullet:
                yield "bullet", bullet[1]
        else:
            paragraph.append(line)
    if paragraph:
        yield "paragraph", "\n".join(paragraph)
    if code:
        yield "code", "\n".join(code)


def _markdown(title, content, bibliography, language):
    output = f"# {title}\n\n{content.rstrip()}\n"
    if bibliography:
        heading = "তথ্যসূত্র" if language == "bn" else "References"
        output += f"\n## {heading}\n\n" + "\n\n".join(bibliography) + "\n"
    return output.encode("utf-8")


_TEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "$": r"\$",
    "&": r"\&",
    "#": r"\#",
    "%": r"\%",
    "_": r"\_",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _tex_escape(text):
    return "".join(_TEX_ESCAPES.get(character, character) for character in text)


def _latex(title, content, bibliography, language):
    # User input never becomes a command or a file path. This source is returned
    # directly; no TeX executable, shell-escape or filesystem compiler is invoked.
    output = [
        "% Compile with XeLaTeX or LuaLaTeX. No compilation occurs in ResearchNest.",
        r"\documentclass[11pt]{article}",
        r"\usepackage{fontspec}",
        r"\usepackage[margin=1in]{geometry}",
    ]
    if language == "bn" or re.search(r"[\u0980-\u09ff]", title + content):
        output.extend(
            [
                "% Install Noto Serif Bengali for Bangla shaping.",
                r"\setmainfont[Script=Bengali]{Noto Serif Bengali}",
            ]
        )
    output.extend(
        [
            r"\title{" + _tex_escape(title) + "}",
            r"\date{}",
            r"\begin{document}",
            r"\maketitle",
        ]
    )
    commands = {
        "heading1": "section",
        "heading2": "subsection",
        "heading3": "subsubsection",
        "heading4": "paragraph",
        "heading5": "subparagraph",
        "heading6": "subparagraph",
    }
    for kind, text in _blocks(content):
        escaped = _tex_escape(text)
        if kind in commands:
            output.append("\\" + commands[kind] + "{" + escaped + "}")
        elif kind == "bullet":
            output.append(r"\begin{itemize}\item " + escaped + r"\end{itemize}")
        else:
            output.append(escaped + "\n")
    if bibliography:
        heading = "তথ্যসূত্র" if language == "bn" else "References"
        output.append(r"\section*{" + heading + "}")
        for entry in bibliography:
            output.append(_tex_escape(entry) + r"\par\medskip")
    output.append(r"\end{document}")
    return ("\n".join(output) + "\n").encode("utf-8")


def _word(title, content, bibliography, language):
    from docx import Document
    from docx.shared import Inches, Pt

    document = Document()
    section = document.sections[0]
    section.top_margin = section.bottom_margin = Inches(0.8)
    section.left_margin = section.right_margin = Inches(0.85)
    normal = document.styles["Normal"]
    normal.font.name = "Nirmala UI" if language == "bn" else "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(8)
    document.core_properties.title = title
    document.core_properties.language = "bn-BD" if language == "bn" else "en"
    document.add_heading(title, level=0)
    for kind, text in _blocks(content):
        if kind.startswith("heading"):
            document.add_heading(text, level=min(6, int(kind[-1])))
        elif kind == "bullet":
            document.add_paragraph(text, style="List Bullet")
        else:
            paragraph = document.add_paragraph(text)
            if kind == "code":
                for run in paragraph.runs:
                    run.font.name = "Courier New"
                    run.font.size = Pt(9)
    if bibliography:
        document.add_heading("তথ্যসূত্র" if language == "bn" else "References", level=1)
        for entry in bibliography:
            paragraph = document.add_paragraph(entry)
            paragraph.paragraph_format.left_indent = Inches(0.25)
            paragraph.paragraph_format.first_line_indent = Inches(-0.25)
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def _pdf(title, content, bibliography, language):
    parts = ["<h1>" + html.escape(title) + "</h1>"]
    for kind, text in _blocks(content):
        safe = html.escape(text).replace("\n", "<br/>")
        if kind.startswith("heading"):
            tag = "h" + kind[-1]
            parts.append(f"<{tag}>{safe}</{tag}>")
        elif kind == "bullet":
            parts.append("<ul><li>" + safe + "</li></ul>")
        elif kind == "code":
            parts.append("<pre>" + safe + "</pre>")
        else:
            parts.append("<p>" + safe + "</p>")
    if bibliography:
        parts.append(
            "<h2>" + ("তথ্যসূত্র" if language == "bn" else "References") + "</h2>"
        )
        parts.extend("<p>" + html.escape(entry) + "</p>" for entry in bibliography)
    # Story shapes complex scripts with bundled MuPDF fallback fonts. The HTML
    # contains only server-generated tags and escaped text: no URLs, styles,
    # JavaScript, images, archive paths, or remote/local resources can be supplied.
    story = fitz.Story(
        html="".join(parts),
        user_css=(
            "body { font-family: sans-serif; font-size: 11pt; line-height: 1.4; } "
            "h1 { font-size: 20pt; } h2 { font-size: 15pt; } "
            "p { margin-top: 0; margin-bottom: 9pt; } "
            "pre { font-size: 9pt; white-space: pre-wrap; }"
        ),
    )
    output = BytesIO()
    writer = fitz.DocumentWriter(output)
    page = fitz.paper_rect("a4")
    content_rect = page + (48, 48, -48, -48)
    more = True
    page_count = 0
    try:
        while more and page_count < MAX_PDF_PAGES:
            device = writer.begin_page(page)
            more, _ = story.place(content_rect)
            story.draw(device)
            writer.end_page()
            page_count += 1
    finally:
        writer.close()
    if more:
        raise ExportError("PDF export exceeds the 200-page limit.")
    with fitz.open(stream=output.getvalue(), filetype="pdf") as document:
        document.set_metadata({"title": title, "producer": "ResearchNest"})
        return document.tobytes(garbage=3, deflate=True)


def export_document(document, citations, format: ExportFormat, style: str):
    """Return bytes/MIME/generated filename for an already-authorized draft."""
    if format not in _MIME_TYPES:
        raise ExportError("Unsupported document export format.")
    if style not in {"apa", "ieee", "mla", "chicago", "harvard"}:
        raise ExportError("Unsupported bibliography style.")
    title, content, bibliography = _resolved(document, citations, style)
    language = document.language
    renderer = {"md": _markdown, "tex": _latex, "docx": _word, "pdf": _pdf}[format]
    data = renderer(title, content, bibliography, language)
    document_id = getattr(document, "id", None)
    suffix = (
        str(document_id) if type(document_id) is int and document_id > 0 else "draft"
    )
    return data, _MIME_TYPES[format], f"researchnest-writing-{suffix}.{format}"
