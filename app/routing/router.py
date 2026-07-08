from fastapi import HTTPException

from app.models.team import ModelRoute, TeamConfig
from app.providers.target import ProviderTarget


def resolve_model_route(team: TeamConfig, model_alias: str) -> ModelRoute:
    """Return the full configured route (primary + fallback chain) for the given alias."""
    if model_alias not in team.allowed_models:
        raise HTTPException(
            status_code=403,
            detail=f"Model '{model_alias}' is not allowed for team '{team.name}'",
        )

    route = team.model_routes.get(model_alias)
    if route is None:
        raise HTTPException(
            status_code=404,
            detail=f"No route configured for model '{model_alias}'",
        )

    return route


def resolve_primary_target(team: TeamConfig, model_alias: str) -> ProviderTarget:
    route = resolve_model_route(team, model_alias)
    return route.primary_target()
