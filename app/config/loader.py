from pathlib import Path

import yaml

from app.models.team import GatewayConfig, TeamConfig

_config: GatewayConfig | None = None


def load_config(path: Path | None = None) -> GatewayConfig:
    global _config
    if path is None:
        path = Path(__file__).parent / "teams.yaml"
    with open(path) as f:
        raw = yaml.safe_load(f)
    _config = GatewayConfig(**raw)
    return _config


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


def is_model_allowed(team: TeamConfig, model_alias: str) -> bool:
    return model_alias in team.allowed_models
