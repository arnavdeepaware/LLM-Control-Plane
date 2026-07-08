from pydantic import BaseModel, Field

from app.providers.target import ProviderTarget


class FallbackTarget(BaseModel):
    provider: str
    model: str

    def to_provider_target(self) -> ProviderTarget:
        return ProviderTarget.from_parts(self.provider, self.model)


class ModelRoute(BaseModel):
    provider: str
    model: str
    fallbacks: list[FallbackTarget] = Field(default_factory=list)

    def primary_target(self) -> ProviderTarget:
        return ProviderTarget.from_parts(self.provider, self.model)

    def fallback_targets(self) -> list[ProviderTarget]:
        return [fallback.to_provider_target() for fallback in self.fallbacks]

    def all_targets(self) -> list[ProviderTarget]:
        return [self.primary_target(), *self.fallback_targets()]


class RateLimitConfig(BaseModel):
    requests_per_minute: int = 60
    tokens_per_minute: int = 50000


class BudgetConfig(BaseModel):
    daily_usd: float = 5.0
    monthly_usd: float = 50.0


class PricingConfig(BaseModel):
    input_price_per_1k: float
    output_price_per_1k: float


class CircuitBreakerConfig(BaseModel):
    failure_threshold: int = 5
    window_seconds: int = 60
    cooldown_seconds: int = 30


class TeamConfig(BaseModel):
    team_id: str = ""
    name: str
    api_key: str
    allowed_models: list[str]
    model_routes: dict[str, ModelRoute]
    rate_limits: RateLimitConfig = Field(default_factory=RateLimitConfig)
    budgets: BudgetConfig = Field(default_factory=BudgetConfig)


class GatewayConfig(BaseModel):
    teams: dict[str, TeamConfig]
    pricing: dict[str, PricingConfig] = Field(default_factory=dict)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
