from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.providers.errors import ProviderError

# Fallback error slugs for routes that still raise HTTPException with a plain
# string detail (e.g. auth, routing). Routes that need a specific machine-readable
# code should raise HTTPException(detail={"error": "...", "message": "..."}) instead.
_STATUS_ERROR_SLUGS = {
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    503: "service_unavailable",
}


def _error_body(exc: HTTPException) -> dict:
    if isinstance(exc.detail, dict) and "error" in exc.detail and "message" in exc.detail:
        return exc.detail
    slug = _STATUS_ERROR_SLUGS.get(exc.status_code, "error")
    return {"error": slug, "message": str(exc.detail)}


def register_exception_handlers(app: FastAPI) -> None:
    """Ensure every HTTPException across the API returns the same {error, message} envelope."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc), headers=exc.headers)

    @app.exception_handler(ProviderError)
    async def provider_error_handler(request: Request, exc: ProviderError) -> JSONResponse:
        # Reaches here only for non-retryable errors (e.g. provider auth failure) that the
        # resilience layer deliberately did not retry or fall back from.
        return JSONResponse(
            status_code=502,
            content={"error": "provider_error", "message": exc.message},
        )
