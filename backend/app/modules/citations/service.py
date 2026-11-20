import hashlib
import re
import unicodedata
from datetime import UTC

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.time import utc_now
from app.models.audit_log import AuditLog
from app.models.paper import Author, Paper, PaperAuthor, PaperSource, UserPaper
from app.models.research_paper import ResearchPaper
from app.models.writing import Citation
from app.modules.ai.quota import lock_owner
from app.modules.citations.formatter import metadata_warnings
from app.modules.citations.schemas import CitationInput, CitationResult
from app.modules.discovery.gateway import InvalidPaperReference, PaperNotFound
from app.modules.discovery.providers import ProviderUnavailable


def title_year_key(title, year):
    title = unicodedata.normalize("NFKC", title).casefold()
    title = " ".join(
        "".join(
            c if unicodedata.category(c)[0] in "LMN" else " " for c in title
        ).split()
    )
    return hashlib.sha256(f"{title}:{year or ''}".encode()).hexdigest()


def identity_key(values):
    return (
        hashlib.sha256(("doi:" + values["doi"]).encode()).hexdigest()
        if values.get("doi")
        else title_year_key(values["title"], values.get("year"))
    )


def result(row):
    values = CitationResult.model_validate(row).model_dump()
    for key in ("created_at", "updated_at"):
        if values[key].tzinfo is None:
            values[key] = values[key].replace(tzinfo=UTC)
    values["warnings"] = metadata_warnings(row)
    return values


async def owned(db, owner, citation_id):
    row = await db.scalar(
        select(Citation).where(Citation.user_id == owner, Citation.id == citation_id)
    )
    if row is None:
        raise HTTPException(404, "Citation not found.")
    return row


async def owned_rows(db, owner, citation_ids=None, *, limit=2000):
    query = select(Citation).where(Citation.user_id == owner)
    if citation_ids is not None:
        query = query.where(Citation.id.in_(citation_ids))
    rows = list(await db.scalars(query.order_by(Citation.id).limit(limit)))
    if citation_ids is not None:
        by_id = {row.id: row for row in rows}
        if set(by_id) != set(citation_ids):
            raise HTTPException(404, "One or more citations were not found.")
        return [by_id[item] for item in dict.fromkeys(citation_ids)]
    if len(rows) == limit:
        # Never silently truncate an all-references export.
        extra = await db.scalar(
            select(Citation.id)
            .where(Citation.user_id == owner)
            .order_by(Citation.id)
            .offset(limit)
            .limit(1)
        )
        if extra is not None:
            raise HTTPException(413, "Select at most 2000 citations per export.")
    return rows


async def library_metadata(db, owner, paper_id):
    row = (
        await db.execute(
            select(UserPaper, ResearchPaper)
            .join(
                ResearchPaper,
                and_(
                    ResearchPaper.id == UserPaper.legacy_paper_id,
                    ResearchPaper.owner_id == owner,
                ),
            )
            .where(UserPaper.user_id == owner, UserPaper.id == paper_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "Library paper not found.")
    link, legacy = row
    values = {
        "title": legacy.title,
        "authors": [
            n.strip()
            for n in re.split(r";|\s+and\s+", legacy.authors or "")
            if n.strip()
        ],
        "venue": legacy.source,
        "url": legacy.url,
        "user_paper_id": paper_id,
    }
    if link.paper_id is None:
        return values, False
    canonical = await db.scalar(
        select(Paper).join(
            UserPaper,
            and_(
                UserPaper.paper_id == Paper.id,
                UserPaper.id == paper_id,
                UserPaper.user_id == owner,
            ),
        )
    )
    if canonical is None:
        return values, False
    authors = list(
        await db.scalars(
            select(Author.display_name)
            .join(PaperAuthor, PaperAuthor.author_id == Author.id)
            .join(
                UserPaper,
                and_(
                    UserPaper.paper_id == PaperAuthor.paper_id,
                    UserPaper.id == paper_id,
                    UserPaper.user_id == owner,
                ),
            )
            .order_by(PaperAuthor.position)
        )
    )
    provenance = await db.scalar(
        select(PaperSource.id)
        .join(
            UserPaper,
            and_(
                UserPaper.paper_id == PaperSource.paper_id,
                UserPaper.id == paper_id,
                UserPaper.user_id == owner,
            ),
        )
        .limit(1)
    )
    values.update(
        title=canonical.title,
        authors=authors or values["authors"],
        doi=canonical.doi,
        year=canonical.publication_date.year if canonical.publication_date else None,
        url=canonical.canonical_url or values["url"],
        entry_type=_entry_type(canonical.publication_type),
    )
    # Provider names are not publication venues.
    if values["venue"] in {
        "arxiv",
        "crossref",
        "openalex",
        "semantic_scholar",
        "pubmed",
    }:
        values["venue"] = None
    return values, provenance is not None


def _entry_type(value):
    return {
        "conference": "inproceedings",
        "book": "book",
        "preprint": "preprint",
        "article": "article",
        "review": "article",
    }.get(value, "misc")


async def prepare(db, owner, body, gateway):
    provided = body.model_dump(exclude_unset=True)
    source, verified = {}, False
    if body.user_paper_id is not None:
        source, verified = await library_metadata(db, owner, body.user_paper_id)
    elif body.doi and body.title is None:
        try:
            paper = await gateway.lookup_doi(body.doi)
        except InvalidPaperReference:
            raise HTTPException(422, "Invalid DOI.") from None
        except PaperNotFound:
            raise HTTPException(404, "DOI metadata was not found.") from None
        except ProviderUnavailable:
            raise HTTPException(
                503, "Academic metadata providers are unavailable."
            ) from None
        source = {
            "title": paper.title,
            "authors": paper.authors,
            "year": paper.publication_date.year if paper.publication_date else None,
            "doi": paper.doi,
            "url": str(paper.url) if paper.url else None,
            "entry_type": _entry_type(paper.paper_type),
        }
        verified = True
    if any(
        key not in {"user_paper_id", "cite_key"} and source.get(key) != value
        for key, value in provided.items()
    ):
        verified = False
    values = CitationInput.model_validate({**source, **provided}).model_dump()
    if not values["title"]:
        raise HTTPException(422, "Citation title is required.")
    values["is_verified"] = bool(
        verified
        and values["authors"]
        and values["year"]
        and (
            values["venue"]
            or values["doi"]
            or (values["entry_type"] == "book" and values["publisher"])
        )
    )
    values["title_year_key"] = title_year_key(values["title"], values["year"])
    values["identity_key"] = identity_key(values)
    return values


async def _existing(db, owner, values, exclude_id=None):
    conditions = [
        Citation.identity_key == values["identity_key"],
        Citation.title_year_key == values["title_year_key"],
    ]
    if values.get("doi"):
        conditions.append(Citation.doi == values["doi"])
    query = select(Citation).where(Citation.user_id == owner, or_(*conditions))
    if exclude_id is not None:
        query = query.where(Citation.id != exclude_id)
    return await db.scalar(query.order_by(Citation.id).limit(1))


async def _key(db, owner, values):
    if values.get("cite_key"):
        if await db.scalar(
            select(Citation.id).where(
                Citation.user_id == owner, Citation.cite_key == values["cite_key"]
            )
        ):
            raise HTTPException(
                409, "This citation key already belongs to another reference."
            )
        return values["cite_key"]
    stem = (
        values["authors"][0].split(",", 1)[0].split()[-1]
        if values["authors"]
        else "ref"
    )
    stem = (
        re.sub(
            "[^a-z0-9]",
            "",
            unicodedata.normalize("NFKD", stem.casefold())
            .encode("ascii", "ignore")
            .decode(),
        )
        or "ref"
    )
    title = re.sub(
        "[^a-z0-9]",
        "",
        unicodedata.normalize("NFKD", values["title"].casefold())
        .encode("ascii", "ignore")
        .decode(),
    )[:16]
    base = stem[:24] + str(values["year"] or "nd") + (title or "paper")
    for number in range(1, 202):
        key = base if number == 1 else f"{base}{number}"
        if not await db.scalar(
            select(Citation.id).where(
                Citation.user_id == owner, Citation.cite_key == key
            )
        ):
            return key
    raise HTTPException(409, "Unable to allocate a unique citation key.")


async def insert_prepared(db, owner, values):
    existing = await _existing(db, owner, values)
    if existing is not None:
        if existing.user_paper_id is None and values.get("user_paper_id") is not None:
            await library_metadata(db, owner, values["user_paper_id"])
            existing.user_paper_id = values["user_paper_id"]
            existing.updated_at = utc_now()
            db.add(
                AuditLog(
                    user_id=owner,
                    action="citation.linked",
                    resource_type="citation",
                    resource_id=str(existing.id),
                )
            )
        return existing, False
    if values.get("user_paper_id") is not None:
        await library_metadata(db, owner, values["user_paper_id"])
    values = {**values, "cite_key": await _key(db, owner, values)}
    row = Citation(user_id=owner, **values)
    db.add(row)
    await db.flush()
    db.add(
        AuditLog(
            user_id=owner,
            action="citation.created",
            resource_type="citation",
            resource_id=str(row.id),
        )
    )
    return row, True


async def create(db, owner, body, gateway):
    values = await prepare(db, owner, body, gateway)
    await db.rollback()
    await lock_owner(db, owner)
    row, _ = await insert_prepared(db, owner, values)
    await db.commit()
    return result(row)


async def update(db, owner, citation_id, body):
    await lock_owner(db, owner)
    row = await owned(db, owner, citation_id)
    changes = body.model_dump(exclude_unset=True)
    if "cite_key" in changes and changes["cite_key"] != row.cite_key:
        # Saved Markdown and version history keep stable reference identifiers.
        raise HTTPException(
            409,
            "Citation keys are immutable; create a new reference to use another key.",
        )
    if changes.get("user_paper_id") is not None:
        await library_metadata(db, owner, changes["user_paper_id"])
    values = {name: getattr(row, name) for name in CitationInput.model_fields}
    values.update(changes)
    validated = CitationInput.model_validate(values).model_dump()
    validated["is_verified"] = row.is_verified if not changes else False
    validated["title_year_key"] = title_year_key(validated["title"], validated["year"])
    validated["identity_key"] = identity_key(validated)
    if await _existing(db, owner, validated, exclude_id=row.id):
        raise HTTPException(
            409, "A citation for this DOI or title and year already exists."
        )
    for key, value in validated.items():
        setattr(row, key, value)
    row.updated_at = utc_now()
    db.add(
        AuditLog(
            user_id=owner,
            action="citation.updated",
            resource_type="citation",
            resource_id=str(row.id),
        )
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "A matching reference already exists.") from None
    return result(row)
