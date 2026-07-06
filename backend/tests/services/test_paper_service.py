from unittest.mock import Mock

import pytest

from app.exceptions.custom_exceptions import (
    PaperNotFoundException,
    PaperPermissionDeniedException,
)
from app.models.research_paper import ResearchPaper
from app.schemas.research_paper import (
    ResearchPaperCreate,
    ResearchPaperUpdate,
)
from app.services.paper_service import PaperService


@pytest.fixture
def repository():
    return Mock()


@pytest.fixture
def service(repository):
    return PaperService(repository)


@pytest.fixture
def sample_paper():
    return ResearchPaper(
        id=1,
        title="Transformer",
        authors="Author",
        abstract="Attention Is All You Need",
        source="NeurIPS",
        url="https://example.com",
        owner_id=1,
    )


@pytest.fixture
def paper_list():
    return [
        ResearchPaper(
            id=i,
            title=f"Paper {i}",
            authors="Author",
            abstract="Abstract",
            source="IEEE",
            url=f"https://example.com/{i}",
            owner_id=1,
        )
        for i in range(1, 11)
    ]


def test_create_paper(service, repository):
    paper = ResearchPaperCreate(
        title="Transformer",
        authors="Author",
        abstract="Abstract",
        source="IEEE",
        url="https://example.com",
    )

    service.create_paper(
        paper,
        owner_id=1,
    )

    repository.create_paper.assert_called_once_with(
        paper,
        1,
    )


def test_get_all_papers(service, repository, paper_list):
    repository.get_all_papers.return_value = paper_list[:2]
    repository.count_papers.return_value = 2

    result = service.get_all_papers(
        page=1,
        size=10,
    )

    assert result.page == 1
    assert result.size == 10
    assert result.total == 2
    assert result.pages == 1
    assert len(result.items) == 2


def test_get_all_papers_empty(service, repository):
    repository.get_all_papers.return_value = []
    repository.count_papers.return_value = 0

    result = service.get_all_papers(
        page=1,
        size=10,
    )

    assert result.total == 0
    assert result.pages == 0
    assert result.items == []


def test_search_papers(service, repository, paper_list):
    repository.search_papers.return_value = paper_list[:1]
    repository.count_search_results.return_value = 1

    result = service.search_papers(
        query="Transformer",
        page=1,
        size=10,
    )

    assert result.total == 1
    assert result.pages == 1
    assert len(result.items) == 1


def test_search_papers_empty(service, repository):
    repository.search_papers.return_value = []
    repository.count_search_results.return_value = 0

    result = service.search_papers(
        query="Nothing",
        page=1,
        size=10,
    )

    assert result.total == 0
    assert result.pages == 0
    assert result.items == []


def test_get_paper_by_id(service, repository, sample_paper):
    repository.get_paper_by_id.return_value = sample_paper

    result = service.get_paper_by_id(1)

    assert result == sample_paper


def test_get_paper_by_id_not_found(service, repository):
    repository.get_paper_by_id.return_value = None

    with pytest.raises(PaperNotFoundException):
        service.get_paper_by_id(999)


def test_verify_paper_owner_success(service, sample_paper):
    service.verify_paper_owner(
        sample_paper,
        user_id=1,
    )


def test_verify_paper_owner_failure(service, sample_paper):
    with pytest.raises(PaperPermissionDeniedException):
        service.verify_paper_owner(
            sample_paper,
            user_id=99,
        )


def test_update_paper(service, repository, sample_paper):
    update = ResearchPaperUpdate(
        title="Updated",
    )

    service.update_paper(
        sample_paper,
        update,
    )

    repository.update_paper.assert_called_once_with(
        sample_paper,
        update,
    )


def test_delete_paper(service, repository, sample_paper):
    service.delete_paper(sample_paper)

    repository.delete_paper.assert_called_once_with(
        sample_paper,
    )


def test_get_all_papers_multiple_pages(
    service,
    repository,
    paper_list,
):
    repository.get_all_papers.return_value = paper_list
    repository.count_papers.return_value = 25

    result = service.get_all_papers(
        page=2,
        size=10,
    )

    assert result.page == 2
    assert result.total == 25
    assert result.pages == 3
    assert len(result.items) == 10


def test_search_multiple_pages(
    service,
    repository,
    paper_list,
):
    repository.search_papers.return_value = paper_list
    repository.count_search_results.return_value = 21

    result = service.search_papers(
        query="AI",
        page=2,
        size=10,
    )

    assert result.page == 2
    assert result.total == 21
    assert result.pages == 3
    assert len(result.items) == 10