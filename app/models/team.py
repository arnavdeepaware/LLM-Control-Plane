from pydantic import BaseModel


class ModelRoute(BaseModel):
    provider: str
    model: str


class RateLimitConfig(BaseModel):
    requests_per_minute: int = 60
    tokens_per_minute: int = 50000


class BudgetConfig(BaseModel):
    daily_usd: float = 5.0
    monthly_usd: float = 50.0


class TeamConfig(BaseModel):
    name: str
    api_key: str
    allowed_models: list[str]
    model_routes: dict[str, ModelRoute]
    rate_limits: RateLimitConfig = RateLimitConfig()
    budgets: BudgetConfig = BudgetConfig()


class GatewayConfig(BaseModel):
    teams: dict[str, TeamConfig]
