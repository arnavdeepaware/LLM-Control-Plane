import time
from dataclasses import dataclass

from app.config.loader import get_pricing
from app.models.chat import Usage
from app.models.team import TeamConfig
from app.redis_client import get_redis


def _daily_key(team_id: str) -> str:
    day = time.strftime("%Y-%m-%d", time.gmtime())
    return f"budget:{team_id}:{day}"


def _monthly_key(team_id: str) -> str:
    month = time.strftime("%Y-%m", time.gmtime())
    return f"budget:{team_id}:{month}"


def estimate_cost(usage: Usage, model_alias: str) -> float:
    """Deterministic cost from configured per-1k-token prices for the requested model alias."""
    pricing = get_pricing(model_alias)
    input_cost = usage.input_tokens / 1000 * pricing.input_price_per_1k
    output_cost = usage.output_tokens / 1000 * pricing.output_price_per_1k
    return input_cost + output_cost


@dataclass
class BudgetStatus:
    allowed: bool
    scope: str = ""
    limit_usd: float = 0.0
    spent_usd: float = 0.0


async def get_spend(team_id: str) -> tuple[float, float]:
    """Return (daily_spend_usd, monthly_spend_usd) for a team."""
    redis_client = get_redis()
    daily_raw, monthly_raw = await redis_client.mget(_daily_key(team_id), _monthly_key(team_id))
    daily = float(daily_raw) if daily_raw is not None else 0.0
    monthly = float(monthly_raw) if monthly_raw is not None else 0.0
    return daily, monthly


async def check_budget(team: TeamConfig) -> BudgetStatus:
    """Block before the provider call if the team has already hit its daily or monthly cap."""
    daily_spend, monthly_spend = await get_spend(team.team_id)

    if daily_spend >= team.budgets.daily_usd:
        return BudgetStatus(
            allowed=False,
            scope="daily",
            limit_usd=team.budgets.daily_usd,
            spent_usd=daily_spend,
        )

    if monthly_spend >= team.budgets.monthly_usd:
        return BudgetStatus(
            allowed=False,
            scope="monthly",
            limit_usd=team.budgets.monthly_usd,
            spent_usd=monthly_spend,
        )

    return BudgetStatus(allowed=True)


async def record_spend(team: TeamConfig, cost_usd: float) -> None:
    """Record spend after a successful provider response. Never call this on failure."""
    redis_client = get_redis()
    daily_key = _daily_key(team.team_id)
    monthly_key = _monthly_key(team.team_id)

    await redis_client.incrbyfloat(daily_key, cost_usd)
    await redis_client.expire(daily_key, 2 * 24 * 60 * 60)

    await redis_client.incrbyfloat(monthly_key, cost_usd)
    await redis_client.expire(monthly_key, 32 * 24 * 60 * 60)
