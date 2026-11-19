"""Bounded BibTeX/RIS data parsing. No TeX execution or macro expansion."""

import re

from app.modules.citations.schemas import CitationInput

MAX_ENTRIES = 200
FIELDS = {
    "title": "title",
    "year": "year",
    "journal": "venue",
    "booktitle": "venue",
    "volume": "volume",
    "number": "issue",
    "pages": "pages",
    "doi": "doi",
    "url": "url",
    "publisher": "publisher",
}


def _plain(value):
    value = value.replace(r"\textbackslash{}", "\uffff")
    value = re.sub(r"(?<!\\)[{}]", "", value)
    value = re.sub(r"\\([{}%&#_$])", r"\1", value)
    return " ".join(value.replace("\uffff", "\\").split())


def _balanced(text, start, opening="{", closing="}"):
    if start >= len(text) or text[start] != opening:
        raise ValueError("Malformed BibTeX grouping.")
    depth, escaped, quote = 1, False, False
    index = start + 1
    while index < len(text):
        char = text[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"' and opening == "(":
            quote = not quote
        elif not quote and char == opening:
            depth += 1
            if depth > 30:
                raise ValueError("BibTeX grouping is too deeply nested.")
        elif not quote and char == closing:
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
        index += 1
    raise ValueError("Unclosed BibTeX entry.")


def _value(text, index):
    if text[index] == "{":
        return _balanced(text, index)
    if text[index] == '"':
        start, index, escaped, depth = index + 1, index + 1, False, 0
        while index < len(text):
            char = text[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            elif char == '"' and depth == 0:
                return text[start:index], index + 1
            if depth < 0 or depth > 30:
                raise ValueError("Invalid BibTeX grouping.")
            index += 1
        raise ValueError("Unclosed BibTeX string.")
    match = re.match(r"\d+", text[index:])
    if not match:
        raise ValueError("BibTeX macros are unsupported; use quoted or braced values.")
    return match.group(), index + len(match.group())


def _bib_fields(text):
    index, values = 0, {}
    while index < len(text):
        while index < len(text) and text[index] in " \r\n\t,":
            index += 1
        if index == len(text):
            break
        match = re.match(r"([A-Za-z][A-Za-z0-9_-]*)\s*=\s*", text[index:])
        if not match:
            raise ValueError("Malformed BibTeX field.")
        field = match.group(1).lower()
        index += match.end()
        if index == len(text):
            raise ValueError("Missing BibTeX value.")
        value, index = _value(text, index)
        if field in values:
            raise ValueError("Duplicate BibTeX field.")
        values[field] = value
        while index < len(text) and text[index].isspace():
            index += 1
        if index < len(text) and text[index] != ",":
            raise ValueError("BibTeX concatenation and macros are unsupported.")
    return values


def parse_bibtex(content):
    records, index = [], 0
    while index < len(content):
        while index < len(content) and content[index].isspace():
            index += 1
        if index == len(content):
            break
        if content[index] == "%":
            next_line = content.find("\n", index)
            index = len(content) if next_line < 0 else next_line + 1
            continue
        match = re.match(r"@([A-Za-z]+)\s*([({])", content[index:])
        if not match:
            raise ValueError("Malformed BibTeX entry.")
        entry_type, opener = match.groups()
        entry_type = entry_type.casefold()
        body, index = _balanced(
            content, index + match.end() - 1, opener, "}" if opener == "{" else ")"
        )
        if entry_type == "comment":
            continue
        if entry_type in {"string", "preamble"}:
            raise ValueError("BibTeX macros and preambles are unsupported.")
        if "," not in body:
            raise ValueError("BibTeX entries require a key and metadata.")
        key, body = body.split(",", 1)
        values = _bib_fields(body)
        data = {
            target: _plain(values[field])
            for field, target in FIELDS.items()
            if field in values
        }
        if data.get("year"):
            data["year"] = int(data["year"])
        data["authors"] = [
            _plain(name)
            for name in re.split(r"\s+and\s+", values.get("author", ""), flags=re.I)
            if name.strip()
        ]
        data["entry_type"] = (
            entry_type
            if entry_type in {"article", "inproceedings", "book", "misc", "preprint"}
            else "misc"
        )
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9:_-]{0,99}", key.strip()):
            data["cite_key"] = key.strip()
        if not data.get("title"):
            raise ValueError("Imported citations require a title.")
        records.append(CitationInput.model_validate(data))
        if len(records) > MAX_ENTRIES:
            raise ValueError("Import at most 200 citations at a time.")
    if not records:
        raise ValueError("No BibTeX citations found.")
    return records


RIS_TYPES = {
    "JOUR": "article",
    "CONF": "inproceedings",
    "CPAPER": "inproceedings",
    "BOOK": "book",
    "UNPB": "preprint",
    "GEN": "misc",
}
RIS_FIELDS = {
    "TI": "title",
    "T1": "title",
    "JO": "venue",
    "JF": "venue",
    "T2": "venue",
    "VL": "volume",
    "IS": "issue",
    "DO": "doi",
    "UR": "url",
    "PB": "publisher",
    "ID": "cite_key",
}


def parse_ris(content):
    records, fields, last = [], None, None
    for line in content.splitlines():
        if not line.strip():
            continue
        match = re.match(r"^([A-Z0-9]{2})  - ?(.*)$", line)
        if not match:
            if fields is not None and last and line[:1].isspace():
                fields[last][-1] += " " + line.strip()
                continue
            raise ValueError("Malformed RIS tag.")
        tag, value = match.groups()
        if tag == "TY":
            if fields is not None:
                raise ValueError("RIS entry is missing ER terminator.")
            fields = {"TY": [value]}
        elif fields is None:
            raise ValueError("RIS entry must start with TY.")
        elif tag == "ER":
            data = {
                target: " ".join(fields[source][0].split())
                for source, target in RIS_FIELDS.items()
                if source in fields
            }
            data["entry_type"] = RIS_TYPES.get(fields["TY"][0], "misc")
            data["authors"] = fields.get("AU", fields.get("A1", []))
            year = fields.get("PY", fields.get("Y1", []))
            if year:
                if not re.match(r"^\d{4}(?:[/ -]|$)", year[0]):
                    raise ValueError("RIS publication year is invalid.")
                data["year"] = int(year[0][:4])
            if "SP" in fields:
                data["pages"] = fields["SP"][0] + (
                    "-" + fields["EP"][0] if "EP" in fields else ""
                )
            if data.get("cite_key") and not re.fullmatch(
                r"[A-Za-z][A-Za-z0-9:_-]{0,99}", data["cite_key"]
            ):
                data.pop("cite_key")
            if not data.get("title"):
                raise ValueError("Imported citations require a title.")
            records.append(CitationInput.model_validate(data))
            if len(records) > MAX_ENTRIES:
                raise ValueError("Import at most 200 citations at a time.")
            fields = None
        else:
            fields.setdefault(tag, []).append(value)
        last = tag
    if fields is not None:
        raise ValueError("RIS entry is missing ER terminator.")
    if not records:
        raise ValueError("No RIS citations found.")
    return records


def _bib_escape(value):
    return "".join(
        (
            r"\textbackslash{}"
            if char == "\\"
            else "\\" + char if char in "{}%&#_$" else char
        )
        for char in str(value)
    )


def export_bibtex(rows):
    entries = []
    for row in rows:
        fields = {
            "title": row.title,
            "author": " and ".join(row.authors),
            "year": row.year,
            "booktitle" if row.entry_type == "inproceedings" else "journal": row.venue,
            "volume": row.volume,
            "number": row.issue,
            "pages": row.pages,
            "doi": row.doi,
            "url": row.url,
            "publisher": row.publisher,
        }
        rendered = [
            f"  {key} = {{{_bib_escape(value)}}}"
            for key, value in fields.items()
            if value is not None and value != ""
        ]
        entries.append(
            f"@{row.entry_type}{{{row.cite_key},\n" + ",\n".join(rendered) + "\n}"
        )
    return "\n\n".join(entries) + ("\n" if entries else "")


def export_ris(rows):
    entries = []
    type_codes = {
        "article": "JOUR",
        "inproceedings": "CONF",
        "book": "BOOK",
        "misc": "GEN",
        "preprint": "UNPB",
    }
    for row in rows:
        fields = [
            ("TY", type_codes[row.entry_type]),
            ("ID", row.cite_key),
            ("TI", row.title),
        ]
        fields += [("AU", name) for name in row.authors]
        fields += [
            ("PY", row.year),
            ("JO", row.venue),
            ("VL", row.volume),
            ("IS", row.issue),
        ]
        if row.pages:
            pages = re.split(r"[-–—]+", row.pages, maxsplit=1)
            fields.append(("SP", pages[0]))
            if len(pages) == 2:
                fields.append(("EP", pages[1]))
        fields += [("DO", row.doi), ("UR", row.url), ("PB", row.publisher), ("ER", "")]
        entries.append(
            "\n".join(f"{tag}  - {value}" for tag, value in fields if value is not None)
        )
    return "\n\n".join(entries) + ("\n" if entries else "")
