"""Local development controls. This router is registered only when explicitly enabled."""

import hmac
import os
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.budget.manager import _daily_key, _monthly_key, get_spend
from app.config.loader import get_config, get_team_by_id
from app.providers.mock_provider import MockProvider
from app.providers.registry import get_provider_registry
from app.redis_client import get_redis
from app.routing import circuit_breaker

router = APIRouter(prefix="/dev", tags=["development"])


def require_dev_token(x_dev_control_token: str | None = Header(default=None)) -> None:
    configured = os.getenv("DEV_CONTROL_TOKEN", "")
    if not configured or not x_dev_control_token or not hmac.compare_digest(x_dev_control_token, configured):
        raise HTTPException(status_code=403, detail="Invalid development control token")


def _mock() -> MockProvider:
    provider = get_provider_registry().get("mock")
    if not isinstance(provider, MockProvider):
        raise HTTPException(status_code=503, detail="Mock provider unavailable")
    return provider


class FailureRequest(BaseModel):
    provider: Literal["mock"]
    model: str
    mode: Literal["timeout", "rate_limit", "server_error", "auth_error"]
    count: int = Field(ge=1, le=100)


class SpendRequest(BaseModel):
    daily_usd: float = Field(ge=0, allow_inf_nan=False)
    monthly_usd: float = Field(ge=0, allow_inf_nan=False)


class ResetRequest(BaseModel):
    scopes: list[Literal["failures", "circuits", "rate_limits", "budgets"]] = Field(min_length=1)
    teams: list[str] | None = Field(default=None, min_length=1)


def _target_models(teams: list[str] | None = None) -> set[str]:
    config = get_config()
    selected = [config.teams[team_id] for team_id in teams] if teams is not None else config.teams.values()
    return {target.model for team in selected for route in team.model_routes.values() for target in route.all_targets() if target.provider == "mock"}


@router.get("/state", dependencies=[Depends(require_dev_token)])
async def state():
    config = get_config()
    return {
        "queued_failures": _mock().queued_failures(),
        "circuits": [
            {"provider": provider, "model": model, "state": circuit_breaker.get_state(provider, model).state}
            for provider, model in sorted({(target.provider, target.model) for team in config.teams.values() for route in team.model_routes.values() for target in route.all_targets()})
        ],
        "spend": {team_id: dict(zip(("daily_usd", "monthly_usd"), await get_spend(team_id))) for team_id in config.teams},
    }


@router.post("/failures", dependencies=[Depends(require_dev_token)])
async def queue_failures(body: FailureRequest):
    if body.model not in _target_models():
        raise HTTPException(status_code=404, detail="Unknown configured mock target")
    _mock().queue_failure(body.model, body.mode, body.count)
    return {"queued_failures": _mock().queued_failures()}


@router.post("/teams/{team_id}/spend", dependencies=[Depends(require_dev_token)])
async def set_spend(team_id: str, body: SpendRequest):
    if get_team_by_id(team_id) is None:
        raise HTTPException(status_code=404, detail="Unknown team")
    redis = get_redis()
    await redis.set(_daily_key(team_id), body.daily_usd, ex=2 * 86400)
    await redis.set(_monthly_key(team_id), body.monthly_usd, ex=32 * 86400)
    return {"team_id": team_id, "daily_usd": body.daily_usd, "monthly_usd": body.monthly_usd}


@router.post("/reset", dependencies=[Depends(require_dev_token)])
async def reset(body: ResetRequest):
    config = get_config()
    teams = list(config.teams) if body.teams is None else body.teams
    if any(team_id not in config.teams for team_id in teams):
        raise HTTPException(status_code=404, detail="Unknown team")
    models = _target_models(teams)
    if "failures" in body.scopes:
        provider = _mock()
        if body.teams is None:
            provider.clear_failures()
        else:
            for model in models:
                provider._fail_queue.pop(model, None)
    if "circuits" in body.scopes:
        # Targets shared by several teams share one circuit and are reset together.
        if body.teams is None:
            circuit_breaker.reset_circuits()
        else:
            for model in models:
                circuit_breaker._circuits.pop(f"mock:{model}", None)
    redis = get_redis()
    keys: list[str] = []
    for team_id in teams:
        if "rate_limits" in body.scopes:
            keys.extend([key async for key in redis.scan_iter(match=f"rate:{team_id}:*")])
        if "budgets" in body.scopes:
            keys.extend([key async for key in redis.scan_iter(match=f"budget:{team_id}:*")])
    if keys:
        await redis.delete(*keys)
    return {"reset": body.scopes, "teams": teams}
