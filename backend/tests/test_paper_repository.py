from app.repositories.paper_repository import PaperRepository
from app.schemas.research_paper import ResearchPaperCreate


def test_create_paper(db):
    repository = PaperRepository(db)

    paper = ResearchPaperCreate(
        title="Attention Is All You Need",
        authors="Ashish Vaswani",
        abstract="Transformer architecture",
        source="arXiv",
        url="https://arxiv.org/abs/1706.03762",
    )

    result = repository.create_paper(paper)

    assert result.id is not None
    assert result.title == "Attention Is All You Need"
    assert result.authors == "Ashish Vaswani"
    assert result.source == "arXiv"