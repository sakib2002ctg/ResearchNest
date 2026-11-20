"""Safe request telemetry: route templates, never raw URLs/query parameters."""

import time

from app.core.logging import logger


class LoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        start = time.perf_counter()
        status = 500

        async def observed_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, observed_send)
        finally:
            route = scope.get("route")
            logger.info(
                "http.request",
                extra={
                    "request_id": scope.get("state", {}).get("request_id"),
                    "method": scope["method"],
                    "route": getattr(route, "path", "<unmatched>"),
                    "status": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 3),
                },
            )
