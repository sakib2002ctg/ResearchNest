"""Outer ASGI response boundary; headers also cover failures and denied requests."""

import uuid

from starlette._utils import get_route_path
from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.logging import logger


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started = False

        async def secured_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Permissions-Policy"] = (
                    "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
                )
                headers["X-Request-ID"] = request_id
                if settings.APP_ENV == "production" and settings.HSTS_ENABLED:
                    headers["Strict-Transport-Security"] = (
                        f"max-age={settings.HSTS_MAX_AGE}"
                    )
                if get_route_path(scope).startswith(
                    ("/api/v1", "/auth", "/papers", "/research")
                ) or any(
                    key.lower() == b"authorization" for key, _ in scope["headers"]
                ):
                    headers["Cache-Control"] = "private, no-store"
                started = True
            await send(message)

        try:
            await self.app(scope, receive, secured_send)
        except Exception as error:
            # SQL/provider exception repr/tracebacks may contain credentials or
            # private text. The type and correlation ID are sufficient here.
            logger.error(
                "Request failed.",
                extra={"request_id": request_id, "error_type": type(error).__name__},
            )
            if started:
                # The response cannot be replaced after headers are sent. Abort
                # with a constant error and suppress the original context so the
                # ASGI server cannot print private parser/SQL/provider messages.
                raise RuntimeError("Response stream interrupted.") from None
            response = JSONResponse(
                {"detail": "Internal Server Error"}, status_code=500
            )
            await response(scope, receive, secured_send)
