import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import and_, select

from app.core.config import settings
from app.core.time import utc_now
from app.models.assistant import AIUsage, Message, MessageCitation
from app.models.audit_log import AuditLog
from app.models.document_intelligence import DocumentChunk
from app.models.library import Document
from app.models.paper import UserPaper
from app.models.research_paper import ResearchPaper
from app.models.user_preference import UserPreference
from app.modules.ai.gateway import Generation, system_prompt
from app.modules.ai.quota import enforce_quota, lock_owner
from app.modules.ai.repository import conversation_for_owner, message_data
from app.modules.rag.retrieval import retrieve, scoped_papers, verify_citations


def insufficient(language):
    return (
        "The selected documents do not contain enough evidence to answer this question."
        if language == "en"
        else "এই প্রশ্নের উত্তর দেওয়ার জন্য নির্বাচিত নথিতে পর্যাপ্ত প্রমাণ নেই।"
    )


async def send_message(db, owner, conversation_id, question, gateway):
    request_id = str(question.request_id)
    fingerprint = hashlib.sha256(
        f"{conversation_id}:{question.provider}:{question.content}".encode()
    ).hexdigest()
    conversation = await conversation_for_owner(db, owner, conversation_id)
    paper_ids = await scoped_papers(db, owner, conversation)
    language = conversation.language
    # Reserve a conservative bounded input before retrieval/embedding or inference.
    # 5 passages x 1600 chars + titles + a 2000-char question, including UTF-8.
    reserved = 60000 + settings.AI_MAX_COMPLETION_TOKENS
    await db.rollback()
    await lock_owner(db, owner)
    conversation = await conversation_for_owner(db, owner, conversation_id)
    prior = await db.scalar(
        select(AIUsage).where(
            AIUsage.user_id == owner, AIUsage.request_id == request_id
        )
    )
    if prior:
        if prior.request_fingerprint != fingerprint:
            raise HTTPException(
                409, "Request ID was already used for a different question."
            )
        answer = await db.scalar(
            select(Message).where(
                Message.user_id == owner,
                Message.conversation_id == conversation_id,
                Message.request_id == request_id,
                Message.role == "assistant",
            )
        )
        if prior.status == "completed" and answer:
            return await message_data(db, owner, answer)
        raise HTTPException(
            409,
            "This request is already pending or failed. Use a new request ID to retry.",
        )
    consent = bool(
        await db.scalar(
            select(UserPreference.allow_external_ai).where(
                UserPreference.user_id == owner
            )
        )
    )
    provider = gateway.route(question.provider, consent)
    await enforce_quota(db, owner, reserved)
    usage = AIUsage(
        user_id=owner,
        conversation_id=conversation_id,
        request_id=request_id,
        request_fingerprint=fingerprint,
        feature="rag_chat",
        provider=provider.name,
        model_name=provider.model,
        reserved_tokens=reserved,
        status="pending",
    )
    db.add(usage)
    await db.commit()
    try:
        conversation = await conversation_for_owner(db, owner, conversation_id)
        paper_ids = await scoped_papers(db, owner, conversation)
        passages = await retrieve(db, owner, paper_ids, question.content)
        messages = [
            {"role": "system", "content": system_prompt(language)},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": question.content,
                        "passages": [p.prompt_data() for p in passages],
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        prompt_bound = sum(len(m["content"].encode()) for m in messages) + 512
        if prompt_bound > 60000:
            raise HTTPException(413, "AI context exceeds the allowed size.")
        await db.rollback()
        # Re-read consent immediately before any possible cloud dispatch.
        consent = bool(
            await db.scalar(
                select(UserPreference.allow_external_ai).where(
                    UserPreference.user_id == owner
                )
            )
        )
        provider = gateway.route(question.provider, consent)
        await db.rollback()
        result = (
            await gateway.generate(
                provider, messages, [p.prompt_data() for p in passages]
            )
            if passages
            else None
        )
        generation = result.generation if result else Generation()
        try:
            verified = verify_citations(generation, passages)
        except ValueError:
            generation, verified = Generation(), []
        if not verified:
            generation = Generation(missing_information=insufficient(language))
        # Reauthorize after inference: indexing/retries, membership and deletion
        # may have changed while the provider was running. Never persist stale evidence.
        await lock_owner(db, owner)
        conversation = await conversation_for_owner(db, owner, conversation_id)
        current_papers = await scoped_papers(db, owner, conversation)
        for passage, quote in verified:
            current = await db.scalar(
                select(DocumentChunk.id)
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
                        UserPaper.id == Document.user_paper_id,
                        UserPaper.user_id == owner,
                    ),
                )
                .join(
                    ResearchPaper,
                    and_(
                        ResearchPaper.id == UserPaper.legacy_paper_id,
                        ResearchPaper.owner_id == owner,
                    ),
                )
                .where(
                    DocumentChunk.id == passage.chunk_id,
                    DocumentChunk.user_id == owner,
                    DocumentChunk.page_number == passage.page_number,
                    DocumentChunk.section_heading == passage.section_heading,
                    DocumentChunk.content.contains(quote, autoescape=True),
                    Document.id == passage.document_id,
                    Document.user_paper_id == passage.user_paper_id,
                    ResearchPaper.title == passage.paper_title,
                    Document.user_paper_id.in_(current_papers),
                )
            )
            if current is None:
                raise HTTPException(
                    409, "Sources changed during generation. Please retry."
                )
        status = (
            "insufficient_evidence"
            if not verified
            else (
                "partial_interpretation" if generation.interpretation else "supported"
            )
        )
        evidence = "\n\n".join(
            f"“{quote}” [{p.paper_title}, p. {p.page_number}]" for p, quote in verified
        )
        followups = generation.follow_up_questions or (
            ["What evidence is missing?", "Compare the cited passages."]
            if language == "en"
            else ["কোন প্রমাণ অনুপস্থিত?", "উদ্ধৃত অংশগুলো তুলনা করুন।"]
        )
        db.add(
            Message(
                user_id=owner,
                conversation_id=conversation_id,
                request_id=request_id,
                role="user",
                content=question.content,
                evidence_status="insufficient_evidence",
            )
        )
        answer = Message(
            user_id=owner,
            conversation_id=conversation_id,
            request_id=request_id,
            role="assistant",
            content=evidence or insufficient(language),
            evidence_status=status,
            interpretation=generation.interpretation,
            missing_information=generation.missing_information,
            follow_up_questions=followups,
            model_used=result.model if result else "no-evidence",
            provider_used=result.provider if result else "offline",
        )
        db.add(answer)
        await db.flush()
        for passage, quote in verified:
            db.add(
                MessageCitation(
                    user_id=owner,
                    message_id=answer.id,
                    user_paper_id=passage.user_paper_id,
                    document_id=passage.document_id,
                    chunk_id=passage.chunk_id,
                    paper_title=passage.paper_title,
                    page_number=passage.page_number,
                    section_heading=passage.section_heading,
                    quoted_snippet=quote,
                    relevance_score=passage.relevance_score,
                )
            )
        usage = await db.scalar(
            select(AIUsage).where(
                AIUsage.user_id == owner, AIUsage.request_id == request_id
            )
        )
        usage.status = "completed"
        usage.provider, usage.model_name = answer.provider_used, answer.model_used
        # Missing usage metrics are charged the conservative reserved bounds.
        usage.prompt_tokens = (
            result.prompt_tokens
            if result and result.prompt_tokens is not None
            else prompt_bound
        )
        usage.completion_tokens = (
            result.completion_tokens
            if result and result.completion_tokens is not None
            else (settings.AI_MAX_COMPLETION_TOKENS if result else 0)
        )
        conversation.updated_at = utc_now()
        db.add(
            AuditLog(
                user_id=owner,
                action="ai.generation.completed",
                resource_type="conversation",
                resource_id=str(conversation_id),
                details={"provider": usage.provider, "evidence_status": status},
            )
        )
        await db.commit()
        return await message_data(db, owner, answer)
    except BaseException:
        await db.rollback()
        usage = await db.scalar(
            select(AIUsage).where(
                AIUsage.user_id == owner, AIUsage.request_id == request_id
            )
        )
        if usage and usage.status == "pending":
            usage.status = "failed"
            db.add(
                AuditLog(
                    user_id=owner,
                    action="ai.generation.failed",
                    resource_type="conversation",
                    resource_id=str(conversation_id),
                )
            )
            await db.commit()
        raise
