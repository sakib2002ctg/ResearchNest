"""Bounded readiness checks; no credentials, paths or exception bodies escape."""

import asyncio
import os
import tempfile
import threading
import time
from concurrent.futures import Future
from pathlib import Path

from sqlalchemy import text

from app.core.config import settings

VERSION = "2.0.0"
_PROBE_CREATION_LOCK = threading.Lock()


def storage_writable(root):
    root = Path(root)
    filename = None
    success = False
    try:
        root.mkdir(parents=True, exist_ok=True)
        if not root.is_dir() or root.is_symlink() or root.is_junction():
            return False
        descriptor, filename = tempfile.mkstemp(prefix=".readiness-", dir=root)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(b"researchnest-readiness\n")
            handle.flush()
            os.fsync(handle.fileno())
        success = True
    except (OSError, ValueError):
        success = False
    finally:
        if filename is not None:
            try:
                Path(filename).unlink(missing_ok=True)
            except OSError:
                success = False
    return success


async def database_ready(app):
    async with app.state.discovery_session_factory() as db:
        await db.execute(text("SELECT 1"))
    return True


async def redis_ready(app):
    redis = getattr(app.state, "operational_redis", None)
    return redis is not None and bool(await redis.ping())


class StorageProbe:
    """At most one potentially blocked filesystem thread for this application.

    A request timeout cannot stop a kernel/NFS write. Reusing a concurrent future
    keeps later readiness requests from exhausting the shared executor, including
    when an app is accessed through different test/client event loops.
    """

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.future = None
        self.inflight_roots = None
        self.cached_roots = None
        self.cached_result = False
        self.cached_at = float("-inf")

    def result_or_future(self, roots):
        with self.lock:
            if (
                self.cached_roots == roots
                and self.clock() - self.cached_at
                < settings.READINESS_STORAGE_CACHE_SECONDS
            ):
                return self.cached_result
            if self.future is not None and not self.future.done():
                # Never report the old root's result for a changed configuration.
                return self.future if self.inflight_roots == roots else False
            future = Future()
            self.future = future
            self.inflight_roots = roots
            threading.Thread(
                target=self._run,
                args=(roots, future),
                name="researchnest-storage-probe",
                daemon=True,
            ).start()
            return future

    def _run(self, roots, future):
        try:
            result = all(storage_writable(root) for root in roots)
        except Exception:
            result = False
        with self.lock:
            self.cached_roots = roots
            self.cached_result = result
            self.cached_at = self.clock()
        future.set_result(result)


async def storage_ready(app):
    with _PROBE_CREATION_LOCK:
        probe = getattr(app.state, "readiness_storage_probe", None)
        if probe is None:
            probe = StorageProbe()
            app.state.readiness_storage_probe = probe
    result = probe.result_or_future(
        (settings.PDF_STORAGE_ROOT, settings.ASSET_STORAGE_ROOT)
    )
    if isinstance(result, bool):
        return result
    return await asyncio.shield(asyncio.wrap_future(result))


async def bounded_check(probe):
    try:
        async with asyncio.timeout(settings.READINESS_TIMEOUT_SECONDS):
            return "ok" if await probe() else "unavailable"
    except Exception:
        return "unavailable"


async def readiness(app):
    names = ["database", "storage"]
    probes = [lambda: database_ready(app), lambda: storage_ready(app)]
    if settings.REDIS_URL:
        names.append("redis")
        probes.append(lambda: redis_ready(app))
    results = await asyncio.gather(*(bounded_check(probe) for probe in probes))
    checks = dict(zip(names, results))
    checks.setdefault("redis", "disabled")
    healthy = all(value != "unavailable" for value in checks.values())
    return {
        "status": "ok" if healthy else "degraded",
        "version": VERSION,
        "checks": checks,
    }, (200 if healthy else 503)
