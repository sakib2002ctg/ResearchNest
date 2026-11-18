import pytest

from app.repositories.paper_repository import PaperRepository
from app.schemas.research_paper import (
    ResearchPaperCreate,
    ResearchPaperUpdate,
)


@pytest.fixture
def repository(db):
    return PaperRepository(db)


@pytest.fixture
def sample_paper(repository, test_user):
    paper = ResearchPaperCreate(
        title="Transformer Architecture",
        authors="Ashish Vaswani",
        abstract="Attention Is All You Need",
        source="NeurIPS",
        url="https://example.com/paper",
    )

    return repository.create_paper(
        paper=paper,
        owner_id=test_user.id,
    )


def test_create_paper(repository, test_user):
    paper = ResearchPaperCreate(
        title="BERT",
        authors="Google",
        abstract="Language Representation",
        source="NAACL",
        url="https://example.com/bert",
    )

    result = repository.create_paper(
        paper=paper,
        owner_id=test_user.id,
    )

    assert result.id is not None
    assert result.title == paper.title
    assert result.owner_id == test_user.id


def test_get_paper_by_id(repository, sample_paper):
    result = repository.get_paper_by_id(sample_paper.id, owner_id=sample_paper.owner_id)

    assert result is not None
    assert result.id == sample_paper.id


def test_get_paper_by_id_not_found(repository):
    result = repository.get_paper_by_id(9999, owner_id=1)

    assert result is None


def test_get_all_papers(repository, test_user):
    for i in range(5):
        repository.create_paper(
            ResearchPaperCreate(
                title=f"Paper {i}",
                authors="Author",
                abstract="Abstract",
                source="IEEE",
                url=f"https://example.com/{i}",
            ),
            owner_id=test_user.id,
        )

    papers = repository.get_all_papers(owner_id=test_user.id)

    assert len(papers) == 5


def test_get_all_papers_pagination(repository, test_user):
    for i in range(15):
        repository.create_paper(
            ResearchPaperCreate(
                title=f"Paper {i}",
                authors="Author",
                abstract="Abstract",
                source="IEEE",
                url=f"https://example.com/{i}",
            ),
            owner_id=test_user.id,
        )

    papers = repository.get_all_papers(
        owner_id=test_user.id,
        skip=5,
        limit=5,
    )

    assert len(papers) == 5
    assert papers[0].title == "Paper 5"


def test_count_papers(repository, test_user):
    for i in range(7):
        repository.create_paper(
            ResearchPaperCreate(
                title=f"Paper {i}",
                authors="Author",
                abstract="Abstract",
                source="IEEE",
                url=f"https://example.com/{i}",
            ),
            owner_id=test_user.id,
        )

    assert repository.count_papers(owner_id=test_user.id) == 7


def test_search_papers_by_title(repository, test_user):
    repository.create_paper(
        ResearchPaperCreate(
            title="Transformer Models",
            authors="Author",
            abstract="Abstract",
            source="IEEE",
            url="https://example.com/1",
        ),
        owner_id=test_user.id,
    )

    repository.create_paper(
        ResearchPaperCreate(
            title="CNN Basics",
            authors="Author",
            abstract="Abstract",
            source="IEEE",
            url="https://example.com/2",
        ),
        owner_id=test_user.id,
    )

    results = repository.search_papers("transformer", owner_id=test_user.id)

    assert len(results) == 1
    assert results[0].title == "Transformer Models"


def test_search_papers_by_author(repository, test_user):
    repository.create_paper(
        ResearchPaperCreate(
            title="Paper",
            authors="Andrew Ng",
            abstract="Abstract",
            source="IEEE",
            url="https://example.com",
        ),
        owner_id=test_user.id,
    )

    results = repository.search_papers("Andrew", owner_id=test_user.id)

    assert len(results) == 1


def test_search_papers_by_abstract(repository, test_user):
    repository.create_paper(
        ResearchPaperCreate(
            title="Paper",
            authors="Author",
            abstract="Deep Learning Revolution",
            source="IEEE",
            url="https://example.com",
        ),
        owner_id=test_user.id,
    )

    results = repository.search_papers("Learning", owner_id=test_user.id)

    assert len(results) == 1


def test_search_pagination(repository, test_user):
    for i in range(20):
        repository.create_paper(
            ResearchPaperCreate(
                title=f"Transformer {i}",
                authors="Author",
                abstract="Abstract",
                source="IEEE",
                url=f"https://example.com/{i}",
            ),
            owner_id=test_user.id,
        )

    results = repository.search_papers(
        "Transformer",
        owner_id=test_user.id,
        skip=5,
        limit=5,
    )

    assert len(results) == 5
    assert results[0].title == "Transformer 5"


def test_count_search_results(repository, test_user):
    repository.create_paper(
        ResearchPaperCreate(
            title="Transformer",
            authors="Author",
            abstract="Abstract",
            source="IEEE",
            url="https://example.com/1",
        ),
        owner_id=test_user.id,
    )

    repository.create_paper(
        ResearchPaperCreate(
            title="Transformer XL",
            authors="Author",
            abstract="Abstract",
            source="IEEE",
            url="https://example.com/2",
        ),
        owner_id=test_user.id,
    )

    assert repository.count_search_results("Transformer", owner_id=test_user.id) == 2


def test_update_paper(repository, sample_paper):
    update = ResearchPaperUpdate(
        title="Updated Title",
    )

    updated = repository.update_paper(
        sample_paper,
        update,
    )

    assert updated.title == "Updated Title"


def test_partial_update(repository, sample_paper):
    update = ResearchPaperUpdate(
        authors="New Author",
    )

    updated = repository.update_paper(
        sample_paper,
        update,
    )

    assert updated.authors == "New Author"
    assert updated.title == sample_paper.title


def test_delete_paper(repository, sample_paper):
    repository.delete_paper(sample_paper)

    result = repository.get_paper_by_id(sample_paper.id, owner_id=sample_paper.owner_id)

    assert result is None


def test_queries_are_owner_scoped(repository, test_user, another_user):
    own = repository.create_paper(
        ResearchPaperCreate(title="Shared term"), owner_id=test_user.id
    )
    foreign = repository.create_paper(
        ResearchPaperCreate(title="Shared term private"), owner_id=another_user.id
    )

    assert repository.get_paper_by_id(foreign.id, owner_id=test_user.id) is None
    assert repository.get_all_papers(owner_id=test_user.id) == [own]
    assert repository.count_papers(owner_id=test_user.id) == 1
    assert repository.search_papers("Shared", owner_id=test_user.id) == [own]
    assert repository.count_search_results("Shared", owner_id=test_user.id) == 1
    assert repository.get_all_papers(owner_id=another_user.id) == [foreign]
