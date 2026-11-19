import unicodedata

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.paper import Author, Paper, PaperAuthor, PaperSource, UserPaper
from app.models.research_paper import ResearchPaper
from app.modules.discovery.gateway import normalize_doi
from app.modules.discovery.schemas import (
    CitationLink,
    DiscoveryPaper,
    SaveToLibraryResponse,
)


def _provider_metadata(paper: DiscoveryPaper, previous: dict | None) -> dict:
    """Allowlist public, bounded gateway-normalized metadata; never user state.

    Providers sometimes omit citation fields on an ID-only refresh. An empty
    response is not evidence that previously recorded links ceased to exist.
    """
    previous = previous if isinstance(previous, dict) else {}
    links = [link.model_dump(mode="json") for link in paper.citation_links[:20]]
    if not links:
        old_links = previous.get("citation_links", [])
        links = old_links[:20] if isinstance(old_links, list) else []
    citations = []
    seen = set()
    for item in links:
        if not isinstance(item, dict):
            continue
        try:
            link = CitationLink.model_validate(
                {
                    key: item[key]
                    for key in ("title", "doi", "url", "source")
                    if key in item
                }
            )
        except ValidationError:
            continue
        url = link.url
        safe_url = (
            str(url)
            if url and not (url.username or url.password) and len(str(url)) <= 2048
            else None
        )
        doi = normalize_doi(link.doi)
        identity = doi or safe_url or link.title.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        citations.append(
            {
                "title": link.title[:500],
                "doi": doi,
                "url": safe_url,
                "source": link.source,
            }
        )
    metadata = {
        "metadata_version": 1,
        "title": paper.title[:500],
        "authors": [name[:255] for name in paper.authors[:100]],
        "doi": normalize_doi(paper.doi),
        "publication_date": (
            paper.publication_date.isoformat() if paper.publication_date else None
        ),
        "publication_type": paper.paper_type[:64] if paper.paper_type else None,
        "citation_count": paper.citation_count,
        "citation_links": citations,
        # Semantic Scholar's citations are works citing this paper, not its
        # outgoing references. The graph deliberately uses cites_or_related.
        "citation_direction": (
            "incoming_cited_by" if paper.source == "semantic_scholar" else "unspecified"
        ),
    }
    venue = previous.get("venue")
    if isinstance(venue, str) and venue.strip():
        metadata["venue"] = " ".join(venue.replace("\x00", "").split())[:500]
    return metadata


IDENTITY_CONSTRAINTS = {
    "ix_papers_doi",
    "uq_paper_sources_provider_external",
    "uq_user_papers_user_paper",
}
SQLITE_IDENTITY_COLUMNS = {
    "papers.doi",
    "paper_sources.provider, paper_sources.external_id",
    "user_papers.user_id, user_papers.paper_id",
}


class PaperIdentityConflict(ValueError):
    pass


def _identity_collision(error: IntegrityError) -> bool:
    diagnostic = getattr(error.orig, "diag", None)
    constraint_name = getattr(diagnostic, "constraint_name", None) or getattr(
        error.orig.__cause__, "constraint_name", None
    )
    if constraint_name in IDENTITY_CONSTRAINTS:
        return True
    prefix = "UNIQUE constraint failed: "
    message = str(error.orig)
    return message.startswith(prefix) and message[len(prefix) :] in (
        SQLITE_IDENTITY_COLUMNS
    )


def _canonical_paper(
    db: Session, paper: DiscoveryPaper, doi: str | None
) -> tuple[Paper, PaperSource | None]:
    source = None
    source_id = paper.external_id or doi
    if source_id:
        source = db.scalar(
            select(PaperSource).where(
                PaperSource.provider == paper.source,
                PaperSource.external_id == source_id,
            )
        )
    doi_paper_id = None
    if doi:
        doi_paper_id = db.scalar(select(Paper.id).where(Paper.doi == doi))
    if source and doi_paper_id and source.paper_id != doi_paper_id:
        raise PaperIdentityConflict("Provider ID and DOI identify different papers.")

    paper_id = source.paper_id if source else doi_paper_id
    if paper_id is None:
        canonical = Paper(
            doi=doi,
            title=paper.title,
            abstract=paper.abstract,
            publication_date=paper.publication_date,
            publication_type=paper.paper_type,
            canonical_url=str(paper.url) if paper.url else None,
            citation_count=paper.citation_count,
        )
        for position, name in enumerate(paper.authors):
            normalized = " ".join(
                unicodedata.normalize("NFKC", name).casefold().split()
            )
            canonical.authors.append(
                PaperAuthor(
                    author=Author(
                        display_name=name[:255], normalized_name=normalized[:255]
                    ),
                    position=position,
                )
            )
        db.add(canonical)
        db.flush()
        return canonical, source

    canonical = db.scalar(select(Paper).where(Paper.id == paper_id).with_for_update())
    if canonical is None or (doi and canonical.doi not in (None, doi)):
        raise PaperIdentityConflict("Provider ID and DOI identify different papers.")
    if canonical.doi is None and doi:
        canonical.doi = doi
    return canonical, source


def _save(
    db: Session, user_id: int, paper: DiscoveryPaper, doi: str | None
) -> SaveToLibraryResponse:
    canonical, source = _canonical_paper(db, paper, doi)
    source_id = paper.external_id or doi
    if source is None and source_id:
        source = PaperSource(
            paper_id=canonical.id,
            provider=paper.source,
            external_id=source_id,
            source_url=str(paper.url) if paper.url else None,
        )
        db.add(source)
    elif source is not None:
        # The canonical row lock serializes concurrent verified refreshes.
        # Refresh the earlier identity lookup before preserving old links.
        db.refresh(source)
    if source is not None:
        source.metadata_json = _provider_metadata(paper, source.metadata_json)
        source.retrieved_at = utc_now()
        if paper.url:
            source.source_url = str(paper.url)

    user_paper_id = db.scalar(
        select(UserPaper.id).where(
            UserPaper.user_id == user_id, UserPaper.paper_id == canonical.id
        )
    )
    already_saved = user_paper_id is not None
    if user_paper_id is None:
        url = str(paper.url) if paper.url else None
        projection = ResearchPaper(
            title=paper.title[:255],
            authors=", ".join(paper.authors)[:255] or None,
            abstract=paper.abstract[:5000] if paper.abstract else None,
            source=paper.source,
            url=url if url and len(url) <= 500 else None,
            owner_id=user_id,
        )
        db.add(projection)
        db.flush()
        saved = UserPaper(
            user_id=user_id, paper_id=canonical.id, legacy_paper_id=projection.id
        )
        db.add(saved)
        db.flush()
        user_paper_id = saved.id

    result = SaveToLibraryResponse(
        paper_id=canonical.id,
        user_paper_id=user_paper_id,
        saved=True,
        already_saved=already_saved,
    )
    db.commit()
    return result


def save_to_library(
    db: Session, user_id: int, paper: DiscoveryPaper
) -> SaveToLibraryResponse:
    """Save verified public metadata and a private library item atomically."""
    doi = normalize_doi(paper.doi)
    if not (doi or paper.external_id):
        raise PaperIdentityConflict("The paper has no verified identifier.")

    for attempt in range(2):
        try:
            return _save(db, user_id, paper, doi)
        except PaperIdentityConflict:
            db.rollback()
            raise
        except IntegrityError as error:
            db.rollback()
            if not _identity_collision(error):
                raise
            if attempt:
                raise PaperIdentityConflict(
                    "The paper identity changed. Try again."
                ) from error
    raise AssertionError("Paper save retry ended without a result.")
