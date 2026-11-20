"""Offline closed-loop ASGI sanity benchmark, not a production capacity claim."""

import argparse
import asyncio
import json
import math
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


async def benchmark_app(app, *, samples=120, concurrency=8, paths=None, headers=None):
    paths = paths or ["/health", "/about", "/api/v1/users/me"]
    durations = []
    gate = asyncio.Semaphore(concurrency)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://benchmark.invalid", headers=headers
    ) as client:
        for path in paths:
            response = await client.get(path)
            response.raise_for_status()

        async def one(index):
            async with gate:
                start = time.perf_counter()
                response = await client.get(paths[index % len(paths)])
                response.raise_for_status()
                durations.append((time.perf_counter() - start) * 1000)

        started = time.perf_counter()
        await asyncio.gather(*(one(index) for index in range(samples)))
        elapsed = time.perf_counter() - started
    ordered = sorted(durations)

    def percentile(p):
        return ordered[max(0, math.ceil(len(ordered) * p) - 1)]

    return {
        "kind": "offline_in_process_asgi_smoke",
        "samples": samples,
        "concurrency": concurrency,
        "paths": paths,
        "duration_seconds": round(elapsed, 4),
        "latency_ms": {
            "p50": round(percentile(0.5), 3),
            "p95": round(percentile(0.95), 3),
            "max": round(max(ordered), 3),
        },
        "requests_per_second": round(samples / elapsed, 2),
        "p95_target_ms": 500,
        "passed": percentile(0.95) < 500,
        "limitations": "Local ASGI and SQLite auth reads; excludes network, TLS, "
        "PostgreSQL, disk ingestion, external discovery and AI latency.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=120)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not 20 <= args.samples <= 10000 or not 1 <= args.concurrency <= 32:
        parser.error("Use 20–10000 samples and concurrency 1–32.")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.config import settings
    from app.core.security import create_access_token
    from app.core.time import utc_now
    from app.database.database import get_db
    from app.main import app
    from app.models.session import Session as UserSession
    from app.models.user import User

    if settings.APP_ENV != "test":
        parser.error("Run this isolated offline harness with APP_ENV=test.")
    scratch = BACKEND_ROOT / ".cache"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="latency-", dir=scratch) as directory:
        engine = create_engine(f"sqlite:///{Path(directory) / 'bench.sqlite'}")
        # Isolated fixture schema only; deployments always use Alembic.
        User.__table__.create(engine)
        UserSession.__table__.create(engine)
        factory = sessionmaker(engine)
        with factory() as db:
            user = User(
                username="latency-fixture",
                email="latency@example.com",
                hashed_password="not-used-for-login",
            )
            db.add(user)
            db.flush()
            session = UserSession(
                user_id=user.id,
                token_jti=str(uuid4()),
                expires_at=utc_now() + timedelta(minutes=5),
            )
            db.add(session)
            db.commit()
            token = create_access_token(
                {"sub": str(user.id), "sid": session.id, "jti": session.token_jti}
            )

        def isolated_db():
            with factory() as db:
                yield db

        prior = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = isolated_db
        try:
            report = asyncio.run(
                benchmark_app(
                    app,
                    samples=args.samples,
                    concurrency=args.concurrency,
                    headers={"Authorization": f"Bearer {token}"},
                )
            )
        finally:
            if prior is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = prior
            engine.dispose()
    formatted = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(formatted + "\n", encoding="utf-8")
    print(formatted)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
