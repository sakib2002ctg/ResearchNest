"""Structured stdout records suitable for deployment log collection."""

import json
import logging
from datetime import UTC, datetime


class SafeJSONFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "request_id",
            "method",
            "route",
            "status",
            "duration_ms",
            "error_type",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        # exc_info's repr may embed SQL parameters, bearer secrets or text.
        # Never append traceback/local variables/provider response payloads.
        if record.exc_info:
            payload["error_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False)


logger = logging.getLogger("researchnest")
if not any(
    getattr(handler, "researchnest_handler", False) for handler in logger.handlers
):
    handler = logging.StreamHandler()
    handler.researchnest_handler = True
    handler.setFormatter(SafeJSONFormatter())
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False
for outbound_logger in ("httpx", "httpcore"):
    logging.getLogger(outbound_logger).setLevel(logging.WARNING)
