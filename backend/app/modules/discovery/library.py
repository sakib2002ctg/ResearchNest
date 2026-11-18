import unicodedata

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.paper import Author, Paper, PaperAuthor, PaperSource, UserPaper
from app.models.research_paper import ResearchPaper
from app.modules.discovery.gateway import normalize_doi
from app.modules.discovery.schemas import DiscoveryPaper, SaveToLibraryResponse

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
    if paper.external_id:
        source = db.scalar(
            select(PaperSource).where(
                PaperSource.provider == paper.source,
                PaperSource.external_id == paper.external_id,
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
    if source is None and paper.external_id:
        db.add(
            PaperSource(
                paper_id=canonical.id,
                provider=paper.source,
                external_id=paper.external_id,
                source_url=str(paper.url) if paper.url else None,
            )
        )

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
