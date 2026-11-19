from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError

from app.models.library import Annotation, Collection, Tag
from app.models.paper import UserPaper
from app.modules.library.dependencies import LibraryDB, Owner
from app.modules.library.documents import router as documents_router
from app.modules.library.repository import LibraryNotFound, LibraryRepository
from app.modules.library.schemas import (
    AnnotationCreate,
    AnnotationResult,
    AnnotationUpdate,
    CollectionCreate,
    CollectionResult,
    CollectionUpdate,
    Identifier,
    LibraryPage,
    ProgressResult,
    ProgressUpdate,
    TagCreate,
    TagResult,
    TagUpdate,
)

router = APIRouter(prefix="/library", tags=["library"])
router.include_router(documents_router)


class LibraryRoute:
    @staticmethod
    async def owned(repo, model, resource_id):
        try:
            return await repo.owned(model, resource_id)
        except LibraryNotFound:
            raise HTTPException(404, "Library item not found.") from None

    @staticmethod
    async def commit(db, *, named=False):
        try:
            await db.commit()
        except IntegrityError as error:
            await db.rollback()
            code = getattr(error.orig, "sqlstate", None) or getattr(
                error.orig, "sqlite_errorcode", None
            )
            if named and code in {"23505", 2067}:
                raise HTTPException(
                    409, "A resource with this name already exists."
                ) from None
            raise

    @staticmethod
    def update(record, payload):
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(record, key, value)


@router.get("/papers")
async def list_papers(
    owner: Owner,
    db: LibraryDB,
    q: str | None = Query(None, max_length=300, pattern=r"^[^\x00]*$"),
    collection_id: Identifier | None = None,
    tag_id: Identifier | None = None,
    page: int = Query(1, ge=1, le=100000),
    size: int = Query(20, ge=1, le=100),
) -> LibraryPage:
    try:
        return await LibraryRepository(db, owner).list_papers(
            q.strip() if q else None, collection_id, tag_id, page, size
        )
    except LibraryNotFound:
        raise HTTPException(404, "Library item not found.") from None


@router.get("/collections")
async def list_collections(owner: Owner, db: LibraryDB) -> list[CollectionResult]:
    return await LibraryRepository(db, owner).named_resources(Collection)


@router.post("/collections", status_code=201)
async def create_collection(
    payload: CollectionCreate,
    owner: Owner,
    db: LibraryDB,
) -> CollectionResult:
    record = Collection(user_id=owner, **payload.model_dump())
    db.add(record)
    await LibraryRoute.commit(db, named=True)
    await db.refresh(record)
    return record


@router.get("/collections/{collection_id}")
async def get_collection(
    collection_id: Identifier,
    owner: Owner,
    db: LibraryDB,
) -> CollectionResult:
    return await LibraryRoute.owned(
        LibraryRepository(db, owner), Collection, collection_id
    )


@router.patch("/collections/{collection_id}")
async def update_collection(
    collection_id: Identifier,
    payload: CollectionUpdate,
    owner: Owner,
    db: LibraryDB,
) -> CollectionResult:
    record = await get_collection(collection_id, owner, db)
    LibraryRoute.update(record, payload)
    await LibraryRoute.commit(db, named=True)
    await db.refresh(record)
    return record


@router.delete("/collections/{collection_id}", status_code=204)
async def delete_collection(collection_id: Identifier, owner: Owner, db: LibraryDB):
    record = await get_collection(collection_id, owner, db)
    await db.delete(record)
    await db.commit()
    return Response(status_code=204)


@router.get("/tags")
async def list_tags(owner: Owner, db: LibraryDB) -> list[TagResult]:
    return await LibraryRepository(db, owner).named_resources(Tag)


@router.post("/tags", status_code=201)
async def create_tag(payload: TagCreate, owner: Owner, db: LibraryDB) -> TagResult:
    record = Tag(user_id=owner, **payload.model_dump())
    db.add(record)
    await LibraryRoute.commit(db, named=True)
    return record


@router.get("/tags/{tag_id}")
async def get_tag(tag_id: Identifier, owner: Owner, db: LibraryDB) -> TagResult:
    return await LibraryRoute.owned(LibraryRepository(db, owner), Tag, tag_id)


@router.patch("/tags/{tag_id}")
async def update_tag(
    tag_id: Identifier,
    payload: TagUpdate,
    owner: Owner,
    db: LibraryDB,
) -> TagResult:
    record = await get_tag(tag_id, owner, db)
    LibraryRoute.update(record, payload)
    await LibraryRoute.commit(db, named=True)
    return record


@router.delete("/tags/{tag_id}", status_code=204)
async def delete_tag(tag_id: Identifier, owner: Owner, db: LibraryDB):
    record = await get_tag(tag_id, owner, db)
    await db.delete(record)
    await db.commit()
    return Response(status_code=204)


async def set_membership(
    model,
    resource_id: int,
    paper_id: int,
    assigned: bool,
    owner: int,
    db: LibraryDB,
) -> Response:
    try:
        await LibraryRepository(db, owner).set_membership(
            model,
            resource_id,
            paper_id,
            assigned,
        )
    except LibraryNotFound:
        raise HTTPException(404, "Library item not found.") from None
    await db.commit()
    return Response(status_code=204)


@router.put("/collections/{collection_id}/papers/{paper_id}", status_code=204)
async def add_to_collection(
    collection_id: Identifier,
    paper_id: Identifier,
    owner: Owner,
    db: LibraryDB,
):
    return await set_membership(Collection, collection_id, paper_id, True, owner, db)


@router.delete("/collections/{collection_id}/papers/{paper_id}", status_code=204)
async def remove_from_collection(
    collection_id: Identifier,
    paper_id: Identifier,
    owner: Owner,
    db: LibraryDB,
):
    return await set_membership(Collection, collection_id, paper_id, False, owner, db)


@router.put("/tags/{tag_id}/papers/{paper_id}", status_code=204)
async def add_tag(
    tag_id: Identifier, paper_id: Identifier, owner: Owner, db: LibraryDB
):
    return await set_membership(Tag, tag_id, paper_id, True, owner, db)


@router.delete("/tags/{tag_id}/papers/{paper_id}", status_code=204)
async def remove_tag(
    tag_id: Identifier,
    paper_id: Identifier,
    owner: Owner,
    db: LibraryDB,
):
    return await set_membership(Tag, tag_id, paper_id, False, owner, db)


@router.patch("/papers/{paper_id}/progress")
async def update_progress(
    paper_id: Identifier,
    payload: ProgressUpdate,
    owner: Owner,
    db: LibraryDB,
) -> ProgressResult:
    record = await LibraryRoute.owned(LibraryRepository(db, owner), UserPaper, paper_id)
    LibraryRoute.update(record, payload)
    await db.commit()
    return record


@router.get("/papers/{paper_id}/annotations")
async def list_annotations(
    paper_id: Identifier,
    owner: Owner,
    db: LibraryDB,
) -> list[AnnotationResult]:
    repo = LibraryRepository(db, owner)
    await LibraryRoute.owned(repo, UserPaper, paper_id)
    return await repo.annotations(paper_id)


@router.post("/papers/{paper_id}/annotations", status_code=201)
async def create_annotation(
    paper_id: Identifier,
    payload: AnnotationCreate,
    owner: Owner,
    db: LibraryDB,
) -> AnnotationResult:
    repo = LibraryRepository(db, owner)
    try:
        await repo.owned(UserPaper, paper_id, lock=True)
    except LibraryNotFound:
        raise HTTPException(404, "Library item not found.") from None
    record = Annotation(user_id=owner, user_paper_id=paper_id, **payload.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.get("/papers/{paper_id}/annotations/{annotation_id}")
async def get_annotation(
    paper_id: Identifier,
    annotation_id: Identifier,
    owner: Owner,
    db: LibraryDB,
) -> AnnotationResult:
    try:
        return await LibraryRepository(db, owner).annotation(paper_id, annotation_id)
    except LibraryNotFound:
        raise HTTPException(404, "Library item not found.") from None


@router.patch("/papers/{paper_id}/annotations/{annotation_id}")
async def update_annotation(
    paper_id: Identifier,
    annotation_id: Identifier,
    payload: AnnotationUpdate,
    owner: Owner,
    db: LibraryDB,
) -> AnnotationResult:
    record = await get_annotation(paper_id, annotation_id, owner, db)
    LibraryRoute.update(record, payload)
    await db.commit()
    await db.refresh(record)
    return record


@router.delete("/papers/{paper_id}/annotations/{annotation_id}", status_code=204)
async def delete_annotation(
    paper_id: Identifier,
    annotation_id: Identifier,
    owner: Owner,
    db: LibraryDB,
):
    record = await get_annotation(paper_id, annotation_id, owner, db)
    await db.delete(record)
    await db.commit()
    return Response(status_code=204)
