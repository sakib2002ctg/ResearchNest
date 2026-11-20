"""Bounded single-instance windows or atomic shared Redis sliding windows."""

import asyncio
import hashlib
import hmac
import math
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from uuid import uuid4

from redis.exceptions import RedisError
from starlette._utils import get_route_path
from starlette.responses import JSONResponse

from app.core.config import settings

SLIDING_WINDOW_SCRIPT = """
local now_parts = redis.call('TIME')
local now = now_parts[1] * 1000 + math.floor(now_parts[2] / 1000)
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
local count = redis.call('ZCARD', KEYS[1])
if count >= limit then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    local retry = math.max(1, math.ceil((tonumber(oldest[2]) + window - now) / 1000))
    return {0, retry}
end
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('PEXPIRE', KEYS[1], window)
return {1, 0}
"""


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after: int = 0


class MemorySlidingWindow:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.entries = OrderedDict()
        self.lock = threading.Lock()

    def check(self, key, limit, window, max_clients):
        now = self.clock()
        with self.lock:
            # Last-use order bounds pruning work and memory. Active entries are
            # never evicted to admit new identities, which would bypass a limit.
            while self.entries:
                first, (_, last_seen) = next(iter(self.entries.items()))
                if last_seen > now - window:
                    break
                del self.entries[first]
            entry = self.entries.get(key)
            if entry is None:
                if len(self.entries) >= max_clients:
                    return Decision(False, max(1, math.ceil(window)))
                queue = deque()
            else:
                queue = entry[0]
            while queue and queue[0] <= now - window:
                queue.popleft()
            if len(queue) >= limit:
                return Decision(False, max(1, math.ceil(queue[0] + window - now)))
            queue.append(now)
            self.entries[key] = (queue, now)
            self.entries.move_to_end(key)
            return Decision(True)


def protected_path(path):
    return any(
        path == prefix or path.startswith(prefix + "/")
        for prefix in ("/api/v1", "/auth", "/papers", "/research")
    )


class RateLimitMiddleware:
    def __init__(self, app, memory=None):
        self.app = app
        self.memory = memory or MemorySlidingWindow()

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or not protected_path(get_route_path(scope))
            or scope["method"] == "OPTIONS"
            or not settings.API_RATE_LIMIT_ENABLED
            or (settings.APP_ENV == "test" and not settings.API_RATE_LIMIT_TEST_ENABLED)
        ):
            return await self.app(scope, receive, send)
        # The trusted ASGI peer is authoritative. Client-controlled X-Forwarded-For
        # and JWT strings cannot rotate the budget or add PII to Redis keys.
        peer = (scope.get("client") or ("unknown", 0))[0]
        digest = hmac.new(
            settings.SECRET_KEY.encode(), str(peer).encode(), hashlib.sha256
        ).hexdigest()
        key = f"researchnest:api-rate:v1:{digest}"
        if settings.REDIS_URL:
            redis = getattr(scope["app"].state, "operational_redis", None)
            try:
                if redis is None:
                    raise RedisError("Rate limiter is not initialized.")
                async with asyncio.timeout(settings.READINESS_TIMEOUT_SECONDS):
                    result = await redis.eval(
                        SLIDING_WINDOW_SCRIPT,
                        1,
                        key,
                        settings.API_RATE_LIMIT_WINDOW_SECONDS * 1000,
                        settings.API_RATE_LIMIT_REQUESTS,
                        uuid4().hex,
                    )
                decision = Decision(bool(int(result[0])), max(0, int(result[1])))
            except (
                RedisError,
                TimeoutError,
                OSError,
                ValueError,
                TypeError,
                IndexError,
            ):
                response = JSONResponse(
                    {"detail": "Request admission is temporarily unavailable."},
                    status_code=503,
                    headers={"Retry-After": "5"},
                )
                return await response(scope, receive, send)
        else:
            decision = self.memory.check(
                key,
                settings.API_RATE_LIMIT_REQUESTS,
                settings.API_RATE_LIMIT_WINDOW_SECONDS,
                settings.API_RATE_LIMIT_MAX_CLIENTS,
            )
        if not decision.allowed:
            response = JSONResponse(
                {"detail": "Too many requests. Please retry later."},
                status_code=429,
                headers={"Retry-After": str(max(1, decision.retry_after))},
            )
            return await response(scope, receive, send)
        await self.app(scope, receive, send)
