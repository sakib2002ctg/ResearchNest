from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import case, func, select, update

from app.core.config import settings
from app.core.time import utc_now
from app.models.assistant import AIUsage
from app.models.user import User


async def lock_owner(db, owner):
    # PostgreSQL row lock; SQLite's UPDATE takes a writer lock for offline tests.
    result = await db.execute(
        update(User).where(User.id == owner).values(username=User.username)
    )
    if result.rowcount != 1:
        raise HTTPException(404, "Account not found.")


async def usage_stats(db, owner):
    now = utc_now()
    charged = case(
        (
            AIUsage.status == "completed",
            AIUsage.prompt_tokens + AIUsage.completion_tokens,
        ),
        else_=AIUsage.reserved_tokens,
    )
    windows = {}
    for label, delta, requests, tokens in (
        (
            "hourly",
            timedelta(hours=1),
            settings.AI_HOURLY_REQUEST_LIMIT,
            settings.AI_HOURLY_TOKEN_LIMIT,
        ),
        (
            "daily",
            timedelta(days=1),
            settings.AI_DAILY_REQUEST_LIMIT,
            settings.AI_DAILY_TOKEN_LIMIT,
        ),
    ):
        count, total = (
            await db.execute(
                select(
                    func.count(AIUsage.id), func.coalesce(func.sum(charged), 0)
                ).where(AIUsage.user_id == owner, AIUsage.created_at >= now - delta)
            )
        ).one()
        windows[label] = {
            "requests": count,
            "tokens": total,
            "request_limit": requests,
            "token_limit": tokens,
            "remaining_requests": max(0, requests - count),
            "remaining_tokens": max(0, tokens - total),
        }
    active = await db.scalar(
        select(func.count(AIUsage.id)).where(
            AIUsage.user_id == owner,
            AIUsage.status == "pending",
            AIUsage.created_at >= now - timedelta(seconds=60),
        )
    )
    return {
        **windows,
        "active_requests": active,
        "window_type": "rolling",
        "max_concurrent_requests": settings.AI_MAX_CONCURRENT_REQUESTS,
    }


async def enforce_quota(db, owner, reserved):
    # Caller holds the durable per-user lock before counting and inserting.
    await db.execute(
        update(AIUsage)
        .where(
            AIUsage.user_id == owner,
            AIUsage.status == "pending",
            AIUsage.created_at < utc_now() - timedelta(seconds=60),
        )
        .values(status="failed")
    )
    stats = await usage_stats(db, owner)
    if stats["active_requests"] >= settings.AI_MAX_CONCURRENT_REQUESTS:
        raise HTTPException(
            429,
            "An AI request is already running. Please wait.",
            headers={"Retry-After": "10"},
        )
    if any(
        stats[w]["remaining_requests"] < 1 or stats[w]["remaining_tokens"] < reserved
        for w in ("hourly", "daily")
    ):
        raise HTTPException(
            429,
            "AI fair-use quota reached. Please try again later.",
            headers={"Retry-After": "60"},
        )
