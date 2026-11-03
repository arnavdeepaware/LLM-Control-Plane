import hmac
import json
import os
from pathlib import Path

import yaml

from app.models.team import CircuitBreakerConfig, GatewayConfig, PricingConfig, TeamConfig
from app.providers.errors import ProviderError
from app.providers.registry import get_provider_registry

_config: GatewayConfig | None = None
_team_api_keys: dict[str, str] | None = None


class ConfigValidationError(ValueError):
    pass


def load_config(path: Path | None = None) -> GatewayConfig:
    global _config, _team_api_keys
    if path is None:
        path = Path(__file__).parent / "teams.yaml"
    with open(path) as f:
        raw = yaml.safe_load(f)
    config = GatewayConfig(**raw)
    for team_id, team in config.teams.items():
        team.team_id = team_id
    validate_config(config)
    _team_api_keys = _load_team_api_keys(config)
    _config = config
    return _config


def _load_team_api_keys(config: GatewayConfig) -> dict[str, str]:
    raw = os.environ.get("TEAM_API_KEYS_JSON")
    if not raw:
        raise ConfigValidationError("TEAM_API_KEYS_JSON is required")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigValidationError("TEAM_API_KEYS_JSON must be valid JSON") from exc
    if not isinstance(parsed, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in parsed.items()):
        raise ConfigValidationError("TEAM_API_KEYS_JSON must be a string-to-string object")

    configured = set(config.teams)
    supplied = set(parsed)
    missing = sorted(configured - supplied)
    unknown = sorted(supplied - configured)
    if missing:
        raise ConfigValidationError(f"Missing API key for team(s): {', '.join(missing)}")
    if unknown:
        raise ConfigValidationError(f"API keys supplied for unknown team(s): {', '.join(unknown)}")
    if any(not value.strip() for value in parsed.values()):
        raise ConfigValidationError("Team API keys must not be empty")
    if len(set(parsed.values())) != len(parsed):
        raise ConfigValidationError("Team API keys must be unique")
    if os.environ.get("PUBLIC_DEMO", "false").lower() == "true":
        local_defaults = {"alpha-secret-key", "beta-secret-key"}
        if any(value in local_defaults or len(value) < 16 for value in parsed.values()):
            raise ConfigValidationError("Public demo requires non-default team API keys of at least 16 characters")
    return parsed


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
    global _config, _team_api_keys
    _config = None
    _team_api_keys = None


def get_config() -> GatewayConfig:
    if _config is None:
        return load_config()
    return _config


def get_team_by_api_key(api_key: str) -> TeamConfig | None:
    config = get_config()
    keys = _team_api_keys or _load_team_api_keys(config)
    matched_team_id: str | None = None
    for team_id, configured_key in keys.items():
        if hmac.compare_digest(api_key, configured_key):
            matched_team_id = team_id
    return config.teams.get(matched_team_id) if matched_team_id else None


def get_team_by_id(team_id: str) -> TeamConfig | None:
    config = get_config()
    return config.teams.get(team_id)


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
