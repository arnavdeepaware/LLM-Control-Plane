import os
from pathlib import Path

import yaml

from app.models.team import CircuitBreakerConfig, GatewayConfig, PricingConfig, TeamConfig
from app.providers.errors import ProviderError
from app.providers.registry import get_provider_registry

_config: GatewayConfig | None = None


class ConfigValidationError(ValueError):
    pass


def load_config(path: Path | None = None) -> GatewayConfig:
    global _config
    if path is None:
        path = Path(__file__).parent / "teams.yaml"
    with open(path) as f:
        raw = yaml.safe_load(f)
    config = GatewayConfig(**raw)
    for team_id, team in config.teams.items():
        team.team_id = team_id
    validate_config(config)
    _config = config
    return _config


def validate_config(config: GatewayConfig) -> None:
    registry = get_provider_registry()

    for team_id, team in config.teams.items():
        allowed_models = set(team.allowed_models)
        configured_routes = set(team.model_routes.keys())

        missing_routes = sorted(allowed_models - configured_routes)
        if missing_routes:
            raise ConfigValidationError(
                f"Team '{team_id}' is missing model_routes for allowed model(s): {', '.join(missing_routes)}"
            )

        extra_routes = sorted(configured_routes - allowed_models)
        if extra_routes:
            raise ConfigValidationError(
                f"Team '{team_id}' has model_routes not present in allowed_models: {', '.join(extra_routes)}"
            )

        for model_alias, route in team.model_routes.items():
            if model_alias not in config.pricing:
                raise ConfigValidationError(f"No pricing configured for model '{model_alias}'")

            for target in route.all_targets():
                try:
                    registry.validate_target(target)
                except (ProviderError, ValueError) as exc:
                    raise ConfigValidationError(
                        f"Invalid provider target for team '{team_id}' model '{model_alias}': {exc}"
                    ) from exc


def reset_config() -> None:
    """Clear the cached config so the next get_config() call reloads from disk."""
    global _config
    _config = None


def get_config() -> GatewayConfig:
    if _config is None:
        return load_config()
    return _config


def get_team_by_api_key(api_key: str) -> TeamConfig | None:
    config = get_config()
    for team in config.teams.values():
        if team.api_key == api_key:
            return team
    return None


def get_team_by_id(team_id: str) -> TeamConfig | None:
    config = get_config()
    return config.teams.get(team_id)


def is_model_allowed(team: TeamConfig, model_alias: str) -> bool:
    return model_alias in team.allowed_models


def get_pricing(model_alias: str) -> PricingConfig:
    config = get_config()
    pricing = config.pricing.get(model_alias)
    if pricing is None:
        raise KeyError(f"No pricing configured for model '{model_alias}'")
    return pricing


def get_circuit_breaker_config() -> CircuitBreakerConfig:
    return get_config().circuit_breaker


def get_redis_url() -> str:
    """Centralized env access for the Redis connection string. Other modules must not read os.environ directly."""
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")
