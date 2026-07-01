from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ResearchPaper(BaseModel):
    title: str
    authors: str
    abstract: str


@router.post("/research")
def create_research(paper: ResearchPaper):
    return {
        "message": "Research paper received successfully!",
        "paper": paper
    }