import textwrap

import pytest

from app.config.loader import ConfigValidationError, load_config
from app.models.chat import ChatCompletionRequest
from app.providers.errors import (
    ProviderAuthError,
    ProviderConfigurationError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.mock_provider import MockProvider
from app.providers.registry import ProviderRegistry, get_provider_registry
from app.providers.target import ProviderTarget


REQUEST = ChatCompletionRequest(model="smart-chat", messages=[{"role": "user", "content": "Hello gateway"}])


def test_provider_target_parses_valid_string():
    target = ProviderTarget.from_string("mock:mock-smart-chat")
    assert target.provider == "mock"
    assert target.model == "mock-smart-chat"
    assert target.to_string() == "mock:mock-smart-chat"


@pytest.mark.parametrize(
    "value",
    ["mock", "mock:", ":model", " mock:model", "mock:model ", " : ", ""],
)
def test_provider_target_rejects_invalid_strings(value):
    with pytest.raises(ValueError):
        ProviderTarget.from_string(value)


def test_provider_registry_lookup_returns_mock_provider():
    provider = get_provider_registry().require("mock")
    assert provider.provider_name == "mock"


def test_provider_registry_missing_provider_raises():
    with pytest.raises(ProviderUnavailableError):
        get_provider_registry().require("missing-provider")


@pytest.mark.asyncio
async def test_mock_provider_returns_normalized_success_response():
    provider = MockProvider()
    target = ProviderTarget.from_parts("mock", "mock-smart-chat")

    response = await provider.chat_completion(REQUEST, target)

    assert response.provider == "mock"
    assert response.model_served == "mock:mock-smart-chat"
    assert response.model_requested == "smart-chat"
    assert response.fallback_used is False
    assert response.usage.total_tokens == response.usage.input_tokens + response.usage.output_tokens


@pytest.mark.asyncio
async def test_mock_provider_failure_modes_are_typed():
    provider = MockProvider()
    target = ProviderTarget.from_parts("mock", "mock-smart-chat")
    provider.queue_failure("mock-smart-chat", "timeout", count=1)

    with pytest.raises(ProviderTimeoutError):
        await provider.chat_completion(REQUEST, target)


@pytest.mark.asyncio
async def test_mock_provider_rejects_wrong_provider_target():
    provider = MockProvider()
    wrong_target = ProviderTarget.from_parts("other", "mock-smart-chat")

    with pytest.raises(ProviderConfigurationError):
        await provider.chat_completion(REQUEST, wrong_target)


def test_registry_validates_target():
    registry = ProviderRegistry()
    registry.validate_target(ProviderTarget.from_parts("mock", "mock-smart-chat"))


def test_config_validation_rejects_unknown_provider(tmp_path):
    config_path = tmp_path / "teams.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            pricing:
              smart-chat:
                input_price_per_1k: 0.005
                output_price_per_1k: 0.015
            teams:
              team_alpha:
                name: Team Alpha
                allowed_models:
                  - smart-chat
                model_routes:
                  smart-chat:
                    provider: missing
                    model: missing-model
            """
        )
    )

    with pytest.raises(ConfigValidationError):
        load_config(config_path)


def test_config_validation_requires_pricing_for_routed_model(tmp_path):
    config_path = tmp_path / "teams.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            pricing: {}
            teams:
              team_alpha:
                name: Team Alpha
                allowed_models:
                  - smart-chat
                model_routes:
                  smart-chat:
                    provider: mock
                    model: mock-smart-chat
            """
        )
    )

    with pytest.raises(ConfigValidationError):
        load_config(config_path)


def test_config_validation_requires_routes_for_allowed_models(tmp_path):
    config_path = tmp_path / "teams.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            pricing:
              smart-chat:
                input_price_per_1k: 0.005
                output_price_per_1k: 0.015
            teams:
              team_alpha:
                name: Team Alpha
                allowed_models:
                  - smart-chat
                model_routes: {}
            """
        )
    )

    with pytest.raises(ConfigValidationError):
        load_config(config_path)
