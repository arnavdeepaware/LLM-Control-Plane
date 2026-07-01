import logging
import time

from app.observability.metrics import REQUEST_COUNT, REQUEST_LATENCY
from app.observability.request_context import (
    generate_request_id,
    get_model_requested,
    get_team_id,
    set_model_requested,
    set_request_id,
    set_team_id,
)

logger = logging.getLogger("app.observability")

# Metrics/latency are only meaningful for routes that resolve a team (chat, admin);
# skip infrastructure endpoints so team_id="" doesn't pollute the series.
_METRIC_EXEMPT_PATHS = {"/metrics", "/health", "/"}


class ObservabilityMiddleware:
    """Plain ASGI middleware (not BaseHTTPMiddleware) so contextvars set by the
    endpoint stay visible here — BaseHTTPMiddleware runs the inner app in a
    separate task, which would isolate any contextvar writes from the handler.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        incoming_request_id = headers.get(b"x-request-id", b"").decode() or None
        request_id = incoming_request_id or generate_request_id()
        set_request_id(request_id)
        set_team_id("")
        set_model_requested("")

        path = scope["path"]
        status_code = 0
        start = time.perf_counter()

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers_list = message.setdefault("headers", [])
                headers_list.append((b"x-request-id", request_id.encode()))
            await send(message)

        await self.app(scope, receive, send_wrapper)

        latency_seconds = time.perf_counter() - start

        if path not in _METRIC_EXEMPT_PATHS:
            team_id = get_team_id()
            model_requested = get_model_requested()
            REQUEST_COUNT.labels(
                team_id=team_id, model_requested=model_requested, status_code=str(status_code)
            ).inc()
            REQUEST_LATENCY.labels(team_id=team_id, model_requested=model_requested).observe(latency_seconds)

        logger.info(
            "request_completed",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "team_id": get_team_id(),
                    "model_requested": get_model_requested(),
                    "path": path,
                    "status_code": status_code,
                    "latency_ms": round(latency_seconds * 1000, 2),
                }
            },
        )
