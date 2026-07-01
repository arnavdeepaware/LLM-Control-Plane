from dataclasses import dataclass

from fastapi import HTTPException

from app.models.chat import ChatCompletionRequest, ChatCompletionResponse
from app.models.team import TeamConfig
from app.observability.metrics import FALLBACK_COUNT, PROVIDER_ERRORS, RETRY_COUNT
from app.providers.errors import NonRetryableProviderError, ProviderError, RetryableProviderError
from app.routing import circuit_breaker
from app.routing.retry import DEFAULT_BASE_DELAY_SECONDS, DEFAULT_MAX_RETRIES, retry_provider_call
from app.routing.router import get_provider, resolve_model_route


@dataclass
class _Target:
    provider_name: str
    model_name: str
    is_primary: bool


async def resilient_chat_completion(
    request: ChatCompletionRequest,
    team: TeamConfig,
    model_alias: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS,
) -> ChatCompletionResponse:
    """Call the primary provider (with retries), falling back through the configured chain.

    Circuit-open targets are skipped. A non-retryable error stops immediately without
    trying further targets. If every target is unavailable or fails, raises HTTPException(503).
    """
    route = resolve_model_route(team, model_alias)
    targets = [_Target(route.provider, route.model, is_primary=True)] + [
        _Target(fb.provider, fb.model, is_primary=False) for fb in route.fallbacks
    ]

    last_error: ProviderError | None = None

    for target in targets:
        if not circuit_breaker.is_available(target.provider_name, target.model_name):
            continue

        provider = get_provider(target.provider_name)

        try:
            if target.is_primary:
                response = await retry_provider_call(
                    provider,
                    request,
                    target.model_name,
                    max_retries=max_retries,
                    base_delay=base_delay,
                    on_retry=lambda: RETRY_COUNT.labels(
                        provider=target.provider_name, model_requested=model_alias
                    ).inc(),
                )
            else:
                response = await provider.chat_completion(request, target.model_name)
        except NonRetryableProviderError as exc:
            circuit_breaker.record_failure(target.provider_name, target.model_name)
            PROVIDER_ERRORS.labels(
                provider=target.provider_name, model_requested=model_alias, error_type=type(exc).__name__
            ).inc()
            raise
        except RetryableProviderError as exc:
            circuit_breaker.record_failure(target.provider_name, target.model_name)
            PROVIDER_ERRORS.labels(
                provider=target.provider_name, model_requested=model_alias, error_type=type(exc).__name__
            ).inc()
            last_error = exc
            continue

        circuit_breaker.record_success(target.provider_name, target.model_name)
        response.fallback_used = not target.is_primary
        if response.fallback_used:
            FALLBACK_COUNT.labels(team_id=team.team_id, model_requested=model_alias).inc()
        return response

    message = f"All providers failed for model '{model_alias}'"
    if last_error is not None:
        message += f": {last_error.message}"
    raise HTTPException(status_code=503, detail={"error": "no_provider_available", "message": message})
