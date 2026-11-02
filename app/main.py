import os

from fastapi import FastAPI
from app.config.loader import get_config

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


@app.get("/meta/capabilities")
async def capabilities():
    config = get_config()
    providers = sorted({target.provider for team in config.teams.values() for route in team.model_routes.values() for target in route.all_targets()})
    # TODO(v1-provider): derive real provider and streaming flags from registered adapter capabilities.
    # TODO(v1-provider): enable usage history and mutable routing only when their backend contracts exist.
    return {
        "version": "0.1.0",
        "provider_mode": "mock" if providers == ["mock"] else ("mixed" if "mock" in providers else "real"),
        "providers": providers,
        "pricing": {alias: price.model_dump() for alias, price in config.pricing.items()},
        "dev_controls": os.getenv("ENABLE_DEV_CONTROLS", "").lower() == "true",
        "streaming": False,
        "real_providers": any(name != "mock" for name in providers),
        "usage_history": False,
        "config_mutation": False,
    }


app.include_router(health_router)
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(providers_router)
app.include_router(metrics_router)
if os.getenv("ENABLE_DEV_CONTROLS", "").lower() == "true":
    from app.api.dev import router as dev_router
    app.include_router(dev_router)
