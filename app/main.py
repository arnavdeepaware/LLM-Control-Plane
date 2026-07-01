from fastapi import FastAPI

from app.api.admin import providers_router, router as admin_router
from app.api.chat import router as chat_router
from app.api.errors import register_exception_handlers
from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.observability.logging import setup_logging
from app.observability.middleware import ObservabilityMiddleware

setup_logging()

app = FastAPI(title="LLM Gateway")
app.add_middleware(ObservabilityMiddleware)
register_exception_handlers(app)


@app.get("/")
async def root():
    return {"name": "LLM Gateway", "version": "0.1.0"}


app.include_router(health_router)
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(providers_router)
app.include_router(metrics_router)
