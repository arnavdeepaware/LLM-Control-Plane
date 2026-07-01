from dataclasses import dataclass

from fastapi import HTTPException

from app.models.team import ModelRoute, TeamConfig
from app.providers.base import BaseProvider
from app.providers.mock_provider import MockProvider

# Registry maps provider name → provider instance
_provider_registry: dict[str, BaseProvider] = {
    "mock": MockProvider(),
}


@dataclass
class ProviderTarget:
    provider_name: str
    model_name: str

    @classmethod
    def parse(cls, target: str) -> "ProviderTarget":
        """Parse a 'provider:model' string into a ProviderTarget."""
        parts = target.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid provider target format: '{target}' (expected 'provider:model')")
        return cls(provider_name=parts[0], model_name=parts[1])


def get_provider(provider_name: str) -> BaseProvider:
    provider = _provider_registry.get(provider_name)
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail=f"Provider '{provider_name}' is not registered",
        )
    return provider


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


def resolve_route(team: TeamConfig, model_alias: str) -> tuple[BaseProvider, str]:
    """Return (provider_instance, resolved_model_name) for the given alias's primary target."""
    route = resolve_model_route(team, model_alias)
    return get_provider(route.provider), route.model
