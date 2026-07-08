from app.providers.base import BaseProvider
from app.providers.errors import ProviderUnavailableError
from app.providers.mock_provider import MockProvider
from app.providers.target import ProviderTarget


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, BaseProvider] = {}
        self.register(MockProvider())

    def register(self, provider: BaseProvider) -> None:
        if not provider.provider_name or not provider.provider_name.strip():
            raise ValueError("Provider must define a non-empty provider_name")
        self._providers[provider.provider_name] = provider

    def get(self, provider_name: str) -> BaseProvider | None:
        return self._providers.get(provider_name)

    def require(self, provider_name: str) -> BaseProvider:
        provider = self.get(provider_name)
        if provider is None:
            raise ProviderUnavailableError(f"Provider '{provider_name}' is not registered", provider=provider_name)
        return provider

    def validate_target(self, target: ProviderTarget) -> None:
        provider = self.require(target.provider)
        if not provider.is_enabled():
            raise ProviderUnavailableError(f"Provider '{target.provider}' is disabled", provider=target.provider)
        provider.validate_target(target)


_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def reset_provider_registry() -> None:
    global _registry
    _registry = None
