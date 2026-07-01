import asyncio
import random

from app.models.chat import ChatCompletionRequest, ChatCompletionResponse
from app.providers.base import BaseProvider
from app.providers.errors import RetryableProviderError

DEFAULT_MAX_RETRIES = 2
# Kept small so the test suite stays fast; still demonstrates real exponential backoff + jitter.
DEFAULT_BASE_DELAY_SECONDS = 0.05
_BACKOFF_MULTIPLIER = 2.5
_JITTER_RATIO = 0.5


def _compute_delay(attempt: int, base_delay: float) -> float:
    delay = base_delay * (_BACKOFF_MULTIPLIER**attempt)
    return delay + random.uniform(0, delay * _JITTER_RATIO)


async def retry_provider_call(
    provider: BaseProvider,
    request: ChatCompletionRequest,
    model: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS,
) -> ChatCompletionResponse:
    """Call provider.chat_completion, retrying RetryableProviderError with exponential backoff + jitter.

    NonRetryableProviderError propagates immediately on the first attempt.
    Pass base_delay=0 in tests to skip real sleeping.
    """
    last_error: RetryableProviderError | None = None

    for attempt in range(max_retries + 1):
        try:
            return await provider.chat_completion(request, model)
        except RetryableProviderError as exc:
            last_error = exc
            if attempt < max_retries:
                await asyncio.sleep(_compute_delay(attempt, base_delay))

    assert last_error is not None
    raise last_error
