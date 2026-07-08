# Provider Abstraction

The gateway's provider layer is designed so routing, retries, fallbacks, and metrics can stay provider-agnostic.

## Core pieces

- `BaseProvider` defines the contract every provider implements.
- `ProviderTarget` is the canonical `provider:model` representation used internally.
- `ProviderRegistry` owns provider registration and target validation.
- `MockProvider` is the deterministic reference provider used by tests.

## Provider contract

Providers must:

- expose a `provider_name`
- implement `chat_completion(request, target)`
- return a normalized `ChatCompletionResponse`
- raise typed `ProviderError` subclasses for provider-call failures

Providers may override:

- `validate_target(target)` for provider-specific target checks
- `is_enabled()` for env-gated or optional providers

## Adding a new provider

1. Create a provider class under `app/providers/` that subclasses `BaseProvider`.
2. Set `provider_name` to the provider slug used in config routes.
3. Implement `chat_completion(request, target)` and map transport errors to typed provider errors.
4. Use `normalize_chat_response(...)` so the response shape matches the rest of the gateway.
5. Override `is_enabled()` if the provider depends on optional environment variables.
6. Override `validate_target(target)` if the provider has target-format constraints.
7. Register the provider in `ProviderRegistry` only when it is safe and intended to be available.

## Testing rules

- Do not require real API keys in tests.
- Do not make paid provider calls in tests.
- Keep `MockProvider` as the main reference implementation for routing and resilience tests.
- If a real adapter is added later, test the disabled/no-env path without calling the external API.
