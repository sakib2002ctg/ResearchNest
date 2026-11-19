import asyncio
import math
import re
import unicodedata
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.assistant import Conversation
from app.models.document_intelligence import DocumentChunk, Embedding
from app.models.library import Collection, CollectionPaper, Document
from app.models.paper import UserPaper
from app.models.research_paper import ResearchPaper
from app.modules.documents.providers import embedding_provider


async def scoped_papers(
    db: AsyncSession, owner: int, conversation: Conversation
) -> list[int]:
    if conversation.scope_type == "collection":
        collection = await db.scalar(
            select(Collection.id).where(
                Collection.id == conversation.scope_collection_id,
                Collection.user_id == owner,
            )
        )
        if collection is None:
            raise HTTPException(404, "Conversation collection is no longer available.")
        return list(
            await db.scalars(
                select(CollectionPaper.user_paper_id)
                .join(
                    UserPaper,
                    and_(
                        UserPaper.id == CollectionPaper.user_paper_id,
                        UserPaper.user_id == owner,
                    ),
                )
                .where(
                    CollectionPaper.user_id == owner,
                    CollectionPaper.collection_id == collection,
                )
            )
        )
    expected = set(conversation.scope_paper_ids)
    actual = set(
        await db.scalars(
            select(UserPaper.id).where(
                UserPaper.user_id == owner, UserPaper.id.in_(expected)
            )
        )
    )
    if actual != expected:
        raise HTTPException(404, "One or more scoped papers are no longer available.")
    return sorted(actual)


@dataclass
class Passage:
    chunk_id: int
    document_id: int
    user_paper_id: int
    paper_title: str
    page_number: int
    section_heading: str | None
    content: str
    relevance_score: float

    def prompt_data(self):
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "paper_title": self.paper_title,
            "page_number": self.page_number,
        }


STOP_WORDS = set(
    (
        "a an the is are was were what which how why does do of in on to and or "
        "for with from this that about explain please summarize summary "
        "paper study findings"
    ).split()
)
STOP_WORDS.update(
    "এই কি কী কেন কিভাবে এবং বা এর এ ও সম্পর্কে করুন বলুন গবেষণা সারসংক্ষেপ".split()
)


def terms(text: str) -> set[str]:
    # Preserve Bengali combining marks rather than splitting them with \w.
    normalized = unicodedata.normalize("NFC", text.casefold())
    normalized = "".join(
        c if unicodedata.category(c)[0] in "LMN" else " " for c in normalized
    )
    return {
        word for word in normalized.split() if len(word) > 1 and word not in STOP_WORDS
    }


def cosine(left, right):
    if len(left) != len(right) or not left or not all(math.isfinite(v) for v in right):
        return 0.0
    denom = math.sqrt(sum(v * v for v in left) * sum(v * v for v in right))
    return (
        max(0.0, min(1.0, sum(a * b for a, b in zip(left, right)) / denom))
        if denom
        else 0.0
    )


async def retrieve(
    db: AsyncSession, owner: int, paper_ids: list[int], question: str
) -> list[Passage]:
    # Every ACL, scope and current-version predicate runs in SQL, before scoring.
    rows = (
        await db.execute(
            select(
                DocumentChunk,
                Document.user_paper_id,
                ResearchPaper.title,
                Embedding.vector_json,
                Embedding.model_name,
            )
            .join(
                Document,
                and_(
                    Document.id == DocumentChunk.document_id,
                    Document.user_id == owner,
                    Document.version == DocumentChunk.document_version,
                    Document.status == "completed",
                ),
            )
            .join(
                UserPaper,
                and_(
                    UserPaper.id == Document.user_paper_id, UserPaper.user_id == owner
                ),
            )
            .join(
                ResearchPaper,
                and_(
                    ResearchPaper.id == UserPaper.legacy_paper_id,
                    ResearchPaper.owner_id == owner,
                ),
            )
            .outerjoin(
                Embedding,
                and_(
                    Embedding.chunk_id == DocumentChunk.id,
                    Embedding.user_id == owner,
                    Embedding.document_version == DocumentChunk.document_version,
                ),
            )
            .where(DocumentChunk.user_id == owner, UserPaper.id.in_(paper_ids))
            .order_by(DocumentChunk.id)
            .limit(5000)
        )
    ).all()
    if not rows:
        return []
    query_terms = terms(question)
    if not query_terms:
        return []
    provider = embedding_provider()
    try:
        async with asyncio.timeout(3):
            vector = (await asyncio.to_thread(provider.embed, [question]))[0]
    except (RuntimeError, TimeoutError, ValueError):
        vector = []
    passages = []
    for chunk, paper_id, title, stored, model in rows:
        overlap = len(query_terms & terms(chunk.content)) / len(query_terms)
        similarity = (
            cosine(vector, stored) if stored and model == provider.model_name else 0.0
        )
        # Hash embeddings have collisions, so require lexical evidence. Semantic
        # models may admit paraphrases only with high cosine confidence.
        if (model == "hash-384" and overlap < 0.5) or (
            not overlap and similarity < 0.7
        ):
            continue
        score = 0.65 * overlap + 0.35 * similarity
        if score >= settings.AI_MIN_RELEVANCE and len(chunk.content.strip()) >= 10:
            passages.append(
                Passage(
                    chunk.id,
                    chunk.document_id,
                    paper_id,
                    title,
                    chunk.page_number,
                    chunk.section_heading,
                    chunk.content[:1600],
                    round(score, 6),
                )
            )
    # Stable lexical-aware reranking, with a fixed context budget (5 x 1600 chars).
    return sorted(passages, key=lambda p: (-p.relevance_score, p.chunk_id))[:5]


def verify_citations(generation, passages: list[Passage]):
    available = {p.chunk_id: p for p in passages}
    verified, seen = [], set()
    for claim in generation.citations:
        passage = available.get(claim.chunk_id)
        if (
            passage is None
            or claim.quoted_snippet not in passage.content
            or len(claim.quoted_snippet.strip()) < 10
            or claim.chunk_id in seen
        ):
            raise ValueError("Unverified evidence.")
        seen.add(claim.chunk_id)
        verified.append((passage, claim.quoted_snippet))
    # Text citation markers belong exclusively to the server-rendered evidence.
    if re.search(
        r"https?://|\[[^\]]+\]",
        " ".join(
            [
                generation.interpretation,
                generation.missing_information,
                *generation.follow_up_questions,
            ]
        ),
    ):
        raise ValueError("Unverified inline citation.")
    return verified
