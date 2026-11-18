from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError

from app.modules.discovery.cache import SearchCache, SearchSnapshot
from app.modules.discovery.schemas import DiscoveryPaper


@pytest.fixture
def anyio_backend():
    return "asyncio"


def snapshot(warnings=None):
    return SearchSnapshot(
        items=[DiscoveryPaper(title="A verified paper", source="crossref")],
        sources=["crossref"],
        warnings=warnings or [],
    )


@pytest.mark.anyio
async def test_redis_shares_snapshots_across_local_caches():
    redis = AsyncMock()
    expected = snapshot()
    first = SearchCache(redis)
    await first.put("test:key", expected)
    redis.set.assert_awaited_once_with("test:key", expected.model_dump_json(), ex=300)

    redis.get.return_value = redis.set.await_args.args[1].encode()
    second = SearchCache(redis)
    assert await second.get("test:key") == expected
    await second.close()
    redis.aclose.assert_awaited_once()


@pytest.mark.anyio
async def test_cache_serves_local_results_when_redis_is_down():
    redis = AsyncMock()
    redis.get.side_effect = ConnectionError("mock failure")
    redis.set.side_effect = ConnectionError("mock failure")
    cache = SearchCache(redis)
    assert await cache.get("test:key") is None
    expected = snapshot(["pubmed"])
    await cache.put("test:key", expected)
    assert await cache.get("test:key") == expected
    redis.set.assert_awaited_once_with("test:key", expected.model_dump_json(), ex=30)
