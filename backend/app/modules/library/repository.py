from collections import defaultdict
from math import ceil

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.library import (
    Annotation,
    Collection,
    CollectionPaper,
    Document,
    PaperTag,
    Tag,
)
from app.models.paper import UserPaper
from app.models.research_paper import ResearchPaper
from app.modules.library.schemas import DocumentResult, LibraryPage, LibraryPaperResult

OwnerModel = type[Collection] | type[Tag] | type[UserPaper]


class LibraryNotFound(LookupError):
    pass


class LibraryRepository:
    def __init__(self, db: AsyncSession, owner_id: int):
        self.db = db
        self.owner_id = owner_id

    async def owned(self, model: OwnerModel, resource_id: int, *, lock=False):
        statement = select(model).where(
            model.user_id == self.owner_id, model.id == resource_id
        )
        if lock:
            statement = statement.with_for_update()
        record = await self.db.scalar(statement)
        if record is None:
            raise LibraryNotFound
        return record

    async def named_resources(self, model: type[Collection] | type[Tag]):
        return (
            await self.db.scalars(
                select(model)
                .where(model.user_id == self.owner_id)
                .order_by(func.lower(model.name), model.id)
            )
        ).all()

    async def annotation(self, paper_id: int, annotation_id: int):
        record = await self.db.scalar(
            select(Annotation).where(
                Annotation.user_id == self.owner_id,
                Annotation.user_paper_id == paper_id,
                Annotation.id == annotation_id,
            )
        )
        if record is None:
            raise LibraryNotFound
        return record

    async def annotations(self, paper_id: int):
        return (
            await self.db.scalars(
                select(Annotation)
                .where(
                    Annotation.user_id == self.owner_id,
                    Annotation.user_paper_id == paper_id,
                )
                .order_by(Annotation.created_at.desc(), Annotation.id.desc())
            )
        ).all()

    async def set_membership(
        self,
        model: type[Collection] | type[Tag],
        resource_id: int,
        paper_id: int,
        assigned: bool,
    ) -> None:
        await self.owned(model, resource_id, lock=True)
        await self.owned(UserPaper, paper_id, lock=True)
        table, field = (
            (CollectionPaper, "collection_id")
            if model is Collection
            else (PaperTag, "tag_id")
        )
        filters = {
            "user_id": self.owner_id,
            "user_paper_id": paper_id,
            field: resource_id,
        }
        row = await self.db.scalar(select(table).filter_by(**filters))
        if assigned and row is None:
            self.db.add(table(**filters))
        elif not assigned and row is not None:
            await self.db.delete(row)

    async def list_papers(
        self,
        q: str | None,
        collection_id: int | None,
        tag_id: int | None,
        page: int,
        size: int,
    ) -> LibraryPage:
        base = (
            select(UserPaper, ResearchPaper)
            .join(
                ResearchPaper,
                (ResearchPaper.id == UserPaper.legacy_paper_id)
                & (ResearchPaper.owner_id == UserPaper.user_id),
            )
            .where(UserPaper.user_id == self.owner_id)
        )
        if q:
            base = base.where(
                or_(
                    ResearchPaper.title.icontains(q, autoescape=True),
                    ResearchPaper.authors.icontains(q, autoescape=True),
                    ResearchPaper.abstract.icontains(q, autoescape=True),
                )
            )
        if collection_id is not None:
            await self.owned(Collection, collection_id)
            base = base.where(
                select(CollectionPaper.user_paper_id)
                .where(
                    CollectionPaper.user_id == self.owner_id,
                    CollectionPaper.collection_id == collection_id,
                    CollectionPaper.user_paper_id == UserPaper.id,
                )
                .exists()
            )
        if tag_id is not None:
            await self.owned(Tag, tag_id)
            base = base.where(
                select(PaperTag.user_paper_id)
                .where(
                    PaperTag.user_id == self.owner_id,
                    PaperTag.tag_id == tag_id,
                    PaperTag.user_paper_id == UserPaper.id,
                )
                .exists()
            )
        total = await self.db.scalar(select(func.count()).select_from(base.subquery()))
        rows = (
            await self.db.execute(
                base.order_by(UserPaper.saved_at.desc(), UserPaper.id.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        ).all()
        ids = [paper.id for paper, _ in rows]
        if not ids:
            return LibraryPage(
                items=[], page=page, size=size, total=total, pages=ceil(total / size)
            )
        collections = await self._paper_memberships(CollectionPaper, ids)
        tags = await self._paper_memberships(PaperTag, ids)
        documents = {
            doc.user_paper_id: DocumentResult.model_validate(doc)
            for doc in (
                await self.db.scalars(
                    select(Document).where(
                        Document.user_id == self.owner_id,
                        Document.user_paper_id.in_(ids),
                    )
                )
            ).all()
        }
        items = [
            LibraryPaperResult(
                id=paper.id,
                legacy_paper_id=legacy.id,
                title=legacy.title,
                authors=legacy.authors,
                abstract=legacy.abstract,
                source=legacy.source,
                url=legacy.url,
                saved_at=paper.saved_at,
                reading_status=paper.reading_status,
                reading_progress_percent=paper.reading_progress_percent,
                collection_ids=collections[paper.id],
                tag_ids=tags[paper.id],
                document=documents.get(paper.id),
            )
            for paper, legacy in rows
        ]
        return LibraryPage(
            items=items, page=page, size=size, total=total, pages=ceil(total / size)
        )

    async def _paper_memberships(
        self, model: type[CollectionPaper] | type[PaperTag], ids: list[int]
    ) -> dict[int, list[int]]:
        foreign_id = model.collection_id if model is CollectionPaper else model.tag_id
        pairs = await self.db.execute(
            select(model.user_paper_id, foreign_id)
            .where(model.user_id == self.owner_id, model.user_paper_id.in_(ids))
            .order_by(foreign_id)
        )
        memberships: dict[int, list[int]] = defaultdict(list)
        for paper_id, related_id in pairs:
            memberships[paper_id].append(related_id)
        return memberships
