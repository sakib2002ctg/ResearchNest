import logging
from collections import OrderedDict
from time import monotonic

from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.modules.discovery.schemas import DiscoveryPaper, DiscoverySource

logger = logging.getLogger("researchnest.discovery")


class SearchSnapshot(BaseModel):
    items: list[DiscoveryPaper]
    sources: list[DiscoverySource]
    warnings: list[str]


class SearchCache:
    def __init__(self, redis: Redis | None = None, ttl: int = 300):
        self._redis = redis
        self._ttl = ttl
        self._local: OrderedDict[str, tuple[float, SearchSnapshot]] = OrderedDict()

    async def get(self, key: str) -> SearchSnapshot | None:
        if key in self._local:
            expires_at, snapshot = self._local.pop(key)
            if expires_at > monotonic():
                self._local[key] = (expires_at, snapshot)
                return snapshot

        if self._redis is not None:
            try:
                cached = await self._redis.get(key)
                if cached:
                    return SearchSnapshot.model_validate_json(cached)
            except (RedisError, ValidationError):
                logger.warning("Discovery cache read failed.")
        return None

    async def put(self, key: str, snapshot: SearchSnapshot) -> None:
        ttl = min(30, self._ttl) if snapshot.warnings else self._ttl
        self._local[key] = (monotonic() + ttl, snapshot)
        self._local.move_to_end(key)
        if len(self._local) > 64:
            self._local.popitem(last=False)
        if self._redis is not None:
            try:
                await self._redis.set(key, snapshot.model_dump_json(), ex=ttl)
            except RedisError:
                logger.warning("Discovery cache write failed.")

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
