import asyncio
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError

from app.modules.documents.queue import DocumentDispatcher

pytestmark = pytest.mark.anyio


async def test_redis_receives_only_job_identifier(factory):
    redis = AsyncMock()
    dispatcher = DocumentDispatcher(factory, AsyncMock(), redis)
    await dispatcher.enqueue(12)
    redis.lpush.assert_awaited_once_with(dispatcher.queue_name, "12")


async def test_redis_failure_falls_back_to_bounded_deduplicated_local_queue(factory):
    redis = AsyncMock()
    redis.lpush.side_effect = ConnectionError("Unavailable")
    dispatcher = DocumentDispatcher(factory, AsyncMock(), redis, local_capacity=1)
    await dispatcher.enqueue(7)
    await dispatcher.enqueue(7)
    await dispatcher.enqueue(8)
    assert dispatcher.local_queue.qsize() == 1
    assert await dispatcher._next_job() == 7


async def test_worker_runs_queued_job_and_closes_tasks(factory):
    processor = AsyncMock()
    processed = asyncio.Event()

    async def process(job_id):
        assert job_id == 9
        processed.set()

    processor.process_job.side_effect = process
    dispatcher = DocumentDispatcher(factory, processor, poll_interval=0.5)
    await dispatcher.enqueue(9)
    await dispatcher.start()
    try:
        await asyncio.wait_for(processed.wait(), timeout=2)
        assert processor.process_job.await_count == 1
        await dispatcher.start()
        assert len(dispatcher._tasks) == 2
    finally:
        await dispatcher.close()
    assert dispatcher._tasks == []
