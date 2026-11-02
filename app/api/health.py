from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config.loader import get_config
from app.redis_client import get_redis
from app.observability.metrics import READINESS

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready():
    try:
        get_config()
    except Exception:
        READINESS.set(0)
        return JSONResponse(status_code=503, content={"status": "unavailable", "dependencies": {"redis": "unknown"}, "error": "configuration_unavailable"})
    try:
        await get_redis().ping()
    except Exception:
        READINESS.set(0)
        return JSONResponse(status_code=503, content={"status": "unavailable", "dependencies": {"redis": "unavailable"}, "error": "dependency_unavailable"})
    READINESS.set(1)
    return {"status": "ok", "dependencies": {"redis": "ok"}}
