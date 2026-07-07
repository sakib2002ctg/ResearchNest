from pydantic import BaseModel, HttpUrl


class ExternalPaper(BaseModel):
    title: str
    authors: list[str]
    abstract: str
    url: HttpUrl
    source: str


class ExternalPaperSearchResponse(BaseModel):
    papers: list[ExternalPaper]
    total: int