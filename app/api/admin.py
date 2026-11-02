from fastapi import APIRouter, HTTPException

from app.budget.manager import get_spend
from app.config.loader import get_config, get_team_by_id
from app.rate_limit.limiter import get_tokens_this_minute
from app.routing import circuit_breaker

router = APIRouter(prefix="/admin")
providers_router = APIRouter()


@router.get("/teams")
async def list_teams():
    return {"teams": [
        {
            "team_id": team.team_id,
            "name": team.name,
            "allowed_models": team.allowed_models,
            "rate_limits": team.rate_limits.model_dump(),
            "budgets": team.budgets.model_dump(),
        }
        for team in get_config().teams.values()
    ]}


@router.get("/teams/{team_id}/usage")
async def get_team_usage(team_id: str):
    team = get_team_by_id(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail=f"Unknown team '{team_id}'")

    daily_spend, monthly_spend = await get_spend(team_id)
    tokens_this_minute = await get_tokens_this_minute(team_id)

    return {
        "team_id": team_id,
        "rate_limits": {
            "requests_per_minute": team.rate_limits.requests_per_minute,
            "tokens_per_minute": team.rate_limits.tokens_per_minute,
        },
        "tokens_this_minute": tokens_this_minute,
        "spend": {
            "daily_usd": daily_spend,
            "monthly_usd": monthly_spend,
        },
        "budgets": {
            "daily_usd": team.budgets.daily_usd,
            "monthly_usd": team.budgets.monthly_usd,
        },
    }


@router.get("/teams/{team_id}/limits")
async def get_team_limits(team_id: str):
    team = get_team_by_id(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail=f"Unknown team '{team_id}'")

    return {
        "team_id": team_id,
        "rate_limits": {
            "requests_per_minute": team.rate_limits.requests_per_minute,
            "tokens_per_minute": team.rate_limits.tokens_per_minute,
        },
        "budgets": {
            "daily_usd": team.budgets.daily_usd,
            "monthly_usd": team.budgets.monthly_usd,
        },
    }


def _configured_provider_targets() -> list[tuple[str, str]]:
    """Every (provider, model) pair reachable via any team's primary or fallback routes."""
    seen: set[tuple[str, str]] = set()
    targets: list[tuple[str, str]] = []
    for team in get_config().teams.values():
        for route in team.model_routes.values():
            for target in route.all_targets():
                key = (target.provider, target.model)
                if key not in seen:
                    seen.add(key)
                    targets.append(key)
    return targets


@providers_router.get("/providers/health")
async def get_providers_health():
    providers = []
    for provider_name, model_name in _configured_provider_targets():
        state = circuit_breaker.get_state(provider_name, model_name)
        providers.append(
            {
                "provider": provider_name,
                "model": model_name,
                "circuit_state": state.state,
                "recent_failures": len(state.failures),
                "last_failure_at": state.failures[-1] if state.failures else None,
            }
        )

    return {"providers": providers}
