from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.documents.processing import DocumentProcessor


class DocumentDispatcher:
    """Redis queue with bounded local dispatch and durable database recovery."""

    queue_name = "researchnest:documents:jobs:v1"
    stale_job_after = timedelta(minutes=10)

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        processor: DocumentProcessor,
        redis: Redis | None = None,
        local_capacity: int = 100,
        poll_interval: float = 2.0,
    ) -> None:
        self.session_factory = session_factory
        self.processor = processor
        self.redis = redis
        self.local_queue: asyncio.Queue[int] = asyncio.Queue(maxsize=local_capacity)
        self.poll_interval = max(0.5, poll_interval)
        self._tasks: list[asyncio.Task] = []
        self._closed = asyncio.Event()
        self._local_ids: set[int] = set()

    def _local_put(self, job_id: int) -> None:
        if job_id in self._local_ids:
            return
        try:
            self.local_queue.put_nowait(job_id)
            self._local_ids.add(job_id)
        except asyncio.QueueFull:
            return

    async def enqueue(self, job_id: int) -> None:
        if self.redis is not None:
            try:
                await self.redis.lpush(self.queue_name, str(job_id))
                return
            except RedisError:
                pass
        self._local_put(job_id)

    async def start(self, workers: int = 1) -> None:
        if self._tasks:
            return
        self._closed.clear()
        self._tasks = [
            asyncio.create_task(self._worker()) for _ in range(max(1, min(workers, 4)))
        ]
        self._tasks.append(asyncio.create_task(self._poll()))

    async def close(self) -> None:
        self._closed.set()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks = []

    async def _worker(self) -> None:
        while not self._closed.is_set():
            try:
                job_id = await asyncio.wait_for(
                    self._next_job(), timeout=self.poll_interval
                )
            except asyncio.TimeoutError:
                continue
            try:
                await self.processor.process_job(job_id)
            except Exception:
                continue

    async def _next_job(self) -> int:
        if not self.local_queue.empty():
            job_id = self.local_queue.get_nowait()
            self._local_ids.discard(job_id)
            return job_id
        if self.redis is not None:
            try:
                item = await self.redis.brpop(
                    self.queue_name, timeout=max(1, int(self.poll_interval))
                )
                if item:
                    job_id = int(item[1])
                    if 0 < job_id <= 2_147_483_647:
                        return job_id
            except (RedisError, TypeError, ValueError):
                pass
        job_id = await self.local_queue.get()
        self._local_ids.discard(job_id)
        return job_id

    async def _poll(self) -> None:
        while not self._closed.is_set():
            try:
                async with self.session_factory() as db:
                    from app.models.document_intelligence import ProcessingJob

                    now = datetime.now(UTC)
                    recover_before = now - self.stale_job_after
                    # Include stale running leases. Processor claim uses the
                    # same lease bound and serializes duplicate enqueues via row lock.
                    jobs = (
                        await db.scalars(
                            select(ProcessingJob.id)
                            .where(
                                or_(
                                    ProcessingJob.status == "queued",
                                    (ProcessingJob.status == "running")
                                    & or_(
                                        ProcessingJob.started_at.is_(None),
                                        ProcessingJob.started_at <= recover_before,
                                    ),
                                )
                            )
                            .order_by(ProcessingJob.created_at)
                            .limit(20)
                        )
                    ).all()
                for job_id in jobs:
                    self._local_put(job_id)
            except Exception:
                pass
            await asyncio.sleep(self.poll_interval)
