from fastapi import HTTPException
from sqlalchemy import select

from app.models.assistant import Conversation, Message, MessageCitation
from app.models.paper import UserPaper


async def conversation_for_owner(db, owner, conversation_id):
    row = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == owner
        )
    )
    if row is None:
        raise HTTPException(404, "Conversation not found.")
    return row


def conversation_data(row):
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "title",
            "scope_type",
            "scope_paper_ids",
            "scope_collection_id",
            "project_id",
            "language",
            "created_at",
            "updated_at",
        )
    }


async def message_data(db, owner, row):
    citations = list(
        await db.scalars(
            select(MessageCitation)
            .join(
                UserPaper,
                (UserPaper.id == MessageCitation.user_paper_id)
                & (UserPaper.user_id == owner),
            )
            .where(
                MessageCitation.message_id == row.id, MessageCitation.user_id == owner
            )
            .order_by(MessageCitation.id)
        )
    )
    fields = (
        "id",
        "user_paper_id",
        "document_id",
        "chunk_id",
        "paper_title",
        "page_number",
        "section_heading",
        "quoted_snippet",
        "relevance_score",
    )
    return {
        **{
            key: getattr(row, key)
            for key in (
                "id",
                "role",
                "content",
                "evidence_status",
                "interpretation",
                "missing_information",
                "follow_up_questions",
                "model_used",
                "provider_used",
                "created_at",
            )
        },
        "citations": [{key: getattr(c, key) for key in fields} for c in citations],
    }


async def history(db, owner, conversation):
    rows = list(
        await db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id, Message.user_id == owner)
            .order_by(Message.id)
        )
    )
    return {
        **conversation_data(conversation),
        "messages": [await message_data(db, owner, row) for row in rows],
    }
