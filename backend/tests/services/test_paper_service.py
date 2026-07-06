from app.repositories.paper_repository import PaperRepository
from app.schemas.research_paper import ResearchPaperCreate
from app.services.paper_service import PaperService


def test_create_paper_service(db):
    repository = PaperRepository(db)
    service = PaperService(repository)

    paper = ResearchPaperCreate(
        title="BERT",
        authors="Jacob Devlin",
        abstract="Bidirectional Encoder Representations from Transformers",
        source="Google",
        url="https://arxiv.org/abs/1810.04805",
    )

    result = service.create_paper(paper)

    assert result.id is not None
    assert result.title == "BERT"
    assert result.authors == "Jacob Devlin"