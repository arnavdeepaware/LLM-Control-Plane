from fastapi import APIRouter, HTTPException

from app.budget.manager import get_spend
from app.config.loader import get_team_by_id
from app.rate_limit.limiter import get_tokens_this_minute

router = APIRouter(prefix="/admin")


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
