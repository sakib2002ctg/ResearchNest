from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import delete, select

from app.models.assistant import Conversation
from app.models.audit_log import AuditLog
from app.models.library import Collection
from app.modules.ai.gateway import AIProviderGateway
from app.modules.ai.quota import usage_stats
from app.modules.ai.repository import conversation_data, conversation_for_owner, history
from app.modules.ai.schemas import ID, ConversationCreate, Question
from app.modules.ai.service import send_message
from app.modules.library.dependencies import LibraryDB, Owner
from app.modules.rag.retrieval import scoped_papers


def private_headers(response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"


router = APIRouter(
    prefix="/conversations",
    tags=["AI conversations"],
    dependencies=[Depends(private_headers)],
)
usage_router = APIRouter(
    prefix="/ai", tags=["AI usage"], dependencies=[Depends(private_headers)]
)


@router.post("", status_code=201)
async def create_conversation(body: ConversationCreate, owner: Owner, db: LibraryDB):
    row = Conversation(user_id=owner, **body.model_dump())
    # This also validates empty collections, and rejects mixed/foreign paper IDs.
    await scoped_papers(db, owner, row)
    if body.scope_type == "collection":
        await db.scalar(
            select(Collection.id)
            .where(
                Collection.id == body.scope_collection_id, Collection.user_id == owner
            )
            .with_for_update()
        )
    db.add(row)
    await db.flush()
    db.add(
        AuditLog(
            user_id=owner,
            action="ai.conversation.created",
            resource_type="conversation",
            resource_id=str(row.id),
        )
    )
    await db.commit()
    return conversation_data(row)


@router.get("")
async def list_conversations(
    owner: Owner,
    db: LibraryDB,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
):
    return [
        conversation_data(c)
        for c in await db.scalars(
            select(Conversation)
            .where(Conversation.user_id == owner)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ]


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: ID, owner: Owner, db: LibraryDB):
    return await history(
        db, owner, await conversation_for_owner(db, owner, conversation_id)
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: ID, owner: Owner, db: LibraryDB):
    await conversation_for_owner(db, owner, conversation_id)
    await db.execute(
        delete(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == owner
        )
    )
    db.add(
        AuditLog(
            user_id=owner,
            action="ai.conversation.deleted",
            resource_type="conversation",
            resource_id=str(conversation_id),
        )
    )
    await db.commit()


def get_gateway(request: Request):
    return request.app.state.ai_gateway


@router.post("/{conversation_id}/messages")
async def post_message(
    conversation_id: ID,
    body: Question,
    owner: Owner,
    db: LibraryDB,
    gateway: Annotated[AIProviderGateway, Depends(get_gateway)],
):
    return await send_message(db, owner, conversation_id, body, gateway)


@usage_router.get("/usage")
async def get_usage(owner: Owner, db: LibraryDB):
    return await usage_stats(db, owner)
