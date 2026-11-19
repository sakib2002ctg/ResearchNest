"""Deterministic plain-text reference styles for the supported metadata fields.

No style engine can repair missing bibliographic data. Warnings preserve that
distinction; rich typography, legal sources and every institutional variant are
outside this formatter's common article/book/conference templates.
"""

import re


def metadata_warnings(row):
    warnings = []
    if not row.title.strip():
        warnings.append("Missing title.")
    if not row.authors:
        warnings.append("Missing authors.")
    if row.year is None:
        warnings.append("Missing publication year.")
    if not (row.venue or row.doi or (row.entry_type == "book" and row.publisher)):
        warnings.append("Missing venue or DOI.")
    if not row.is_verified:
        warnings.append("Metadata has not been verified against an academic source.")
    return warnings


def _name_parts(name):
    name = " ".join(name.split())
    if "," in name:
        surname, given = name.split(",", 1)
        return surname.strip(), given.strip()
    parts = name.split()
    return (parts[-1], " ".join(parts[:-1])) if len(parts) > 1 else (name, "")


def _initials(given):
    return " ".join(
        part[0].upper() + "." for part in re.split(r"[\s-]+", given) if part
    )


def _author(name, initial=True, inverted=True):
    family, given = _name_parts(name)
    first = _initials(given) if initial else given
    return (f"{family}, {first}" if inverted else f"{first} {family}").strip(" ,")


def _join(names, conjunction):
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return conjunction.join(names)
    return ", ".join(names[:-1]) + "," + conjunction + names[-1]


def _year(row):
    return str(row.year) if row.year is not None else "n.d."


def _family_in_text(row, style):
    families = [_name_parts(name)[0] for name in row.authors]
    if not families:
        return f"“{row.title}”"
    if len(families) > 2:
        return families[0] + " et al."
    return _join(families, " & " if style == "apa" else " and ")


def _ending(text):
    return text.rstrip(" .") + "."


def _location(row):
    return f"https://doi.org/{row.doi}" if row.doi else (row.url or "")


def format_entry(row, style, number=1):
    year = _year(row)
    location = _location(row)
    authors = row.authors
    family = _family_in_text(row, style)
    if style == "apa":
        names = [_author(name) for name in authors]
        if len(names) > 20:
            author = ", ".join(names[:19]) + ", … " + names[-1]
        else:
            author = ", & ".join(names) if len(names) == 2 else _join(names, " & ")
        start = (
            f"{author} ({year}). {row.title}." if author else f"{row.title}. ({year})."
        )
        container = row.publisher if row.entry_type == "book" else (row.venue or "")
        if row.entry_type != "book":
            if row.volume:
                container += f", {row.volume}"
            if row.issue:
                container += f"({row.issue})"
            if row.pages:
                container += f", {row.pages}"
        bibliography = " ".join(
            filter(None, [start, _ending(container) if container else "", location])
        )
        in_text = f"({family}, {year})"
    elif style == "ieee":
        names = [_author(name, inverted=False) for name in authors]
        author = _join(names, " and ") if len(names) <= 6 else names[0] + " et al."
        author = (author + ", ") if author else ""
        if row.entry_type == "book":
            details = ", ".join(filter(None, [row.publisher, year]))
            bibliography = f"[{number}] {author}{row.title}. {details}."
        else:
            details = [
                row.venue or ("Preprint" if row.entry_type == "preprint" else "")
            ]
            details += [
                f"vol. {row.volume}" if row.volume else "",
                f"no. {row.issue}" if row.issue else "",
                f"pp. {row.pages}" if row.pages else "",
                year,
            ]
            bibliography = (
                f"[{number}] {author}“{row.title},” "
                + ", ".join(filter(None, details))
                + "."
            )
        if row.doi:
            bibliography += f" doi: {row.doi}."
        elif location:
            bibliography += f" [Online]. Available: {location}"
        in_text = f"[{number}]"
    elif style == "mla":
        if len(authors) > 2:
            author = _author(authors[0], initial=False) + ", et al."
        elif len(authors) == 2:
            author = (
                _author(authors[0], initial=False)
                + ", and "
                + _author(authors[1], initial=False, inverted=False)
            )
        else:
            author = _author(authors[0], initial=False) if authors else ""
        title = _ending(row.title) if row.entry_type == "book" else f"“{row.title}.”"
        details = [
            row.publisher if row.entry_type == "book" else row.venue,
            f"vol. {row.volume}" if row.volume else None,
            f"no. {row.issue}" if row.issue else None,
            year,
            f"pp. {row.pages}" if row.pages else None,
            location,
        ]
        bibliography = " ".join(
            filter(
                None,
                [
                    _ending(author) if author else "",
                    title,
                    _ending(", ".join(filter(None, details))),
                ],
            )
        )
        # MLA uses author-page rather than author-year; a locator is not invented.
        in_text = f"({family})"
    elif style == "chicago":
        # Chicago author-date; notes/bibliography is a different citation system.
        author = _join(
            [
                _author(name, initial=False, inverted=(i == 0))
                for i, name in enumerate(authors)
            ],
            " and ",
        )
        prefix = " ".join(filter(None, [_ending(author) if author else "", year + "."]))
        title = row.title if row.entry_type == "book" else f"“{row.title}.”"
        container = row.publisher if row.entry_type == "book" else (row.venue or "")
        if row.entry_type != "book":
            if row.volume:
                container += f" {row.volume}"
            if row.issue:
                container += f" ({row.issue})"
            if row.pages:
                container += f": {row.pages}"
        bibliography = " ".join(
            filter(
                None,
                [
                    prefix,
                    _ending(title) if row.entry_type == "book" else title,
                    _ending(container) if container else "",
                    location,
                ],
            )
        )
        in_text = f"({family} {year})"
    elif style == "harvard":
        author = _join([_author(name) for name in authors], " and ")
        title = row.title if row.entry_type == "book" else f"‘{row.title}’"
        container = row.publisher if row.entry_type == "book" else (row.venue or "")
        if row.entry_type != "book":
            if row.volume:
                container += f", {row.volume}"
            if row.issue:
                container += f"({row.issue})"
            if row.pages:
                container += f", pp. {row.pages}"
        bibliography = " ".join(
            filter(
                None,
                [
                    f"{author} ({year})" if author else f"({year})",
                    title + "," if container else _ending(title),
                    _ending(container) if container else "",
                    location,
                ],
            )
        )
        in_text = f"({family}, {year})"
    else:
        raise ValueError("Unsupported citation style.")
    return {
        "citation_id": row.id,
        "cite_key": row.cite_key,
        "in_text": in_text,
        "bibliography": bibliography,
        "is_verified": row.is_verified,
    }


def format_citations(rows, style="apa"):
    entries = [format_entry(row, style, number) for number, row in enumerate(rows, 1)]
    warnings = [
        f"{row.cite_key}: {warning}"
        for row in rows
        for warning in metadata_warnings(row)
    ]
    if style == "harvard":
        warnings.append(
            "Harvard uses a common author-date template; institutional variants differ."
        )
    return {
        "style": style,
        "entries": entries,
        "bibliography": [entry["bibliography"] for entry in entries],
        "warnings": warnings,
    }
