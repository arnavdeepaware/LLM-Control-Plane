import pytest

from app.models.chat import ChatCompletionRequest
from app.providers.errors import ProviderAuthError, ProviderServerError, ProviderTimeoutError
from app.providers.mock_provider import MockProvider
from app.providers.target import ProviderTarget
from app.routing.retry import retry_provider_call

REQUEST = ChatCompletionRequest(model="smart-chat", messages=[{"role": "user", "content": "hello"}])
TARGET = ProviderTarget.from_parts("mock", "mock-smart-chat")


def _counting_wrapper(provider: MockProvider) -> list[str]:
    """Wrap provider.chat_completion to record every model it was called with."""
    calls: list[str] = []
    original = provider.chat_completion

    async def wrapped(request, target):
        calls.append(target.model)
        return await original(request, target)

    provider.chat_completion = wrapped
    return calls


@pytest.mark.asyncio
async def test_retry_succeeds_after_retryable_failures():
    provider = MockProvider()
    provider.queue_failure("mock-smart-chat", "timeout", count=2)

    response = await retry_provider_call(provider, REQUEST, TARGET, max_retries=2, base_delay=0)
    assert response.model_served == "mock:mock-smart-chat"


@pytest.mark.asyncio
async def test_retry_exhausted_raises_retryable_error():
    provider = MockProvider()
    provider.queue_failure("mock-smart-chat", "timeout", count=5)

    with pytest.raises(ProviderTimeoutError):
        await retry_provider_call(provider, REQUEST, TARGET, max_retries=2, base_delay=0)


@pytest.mark.asyncio
async def test_non_retryable_error_is_not_retried():
    provider = MockProvider()
    provider.queue_failure("mock-smart-chat", "auth_error", count=1)
    calls = _counting_wrapper(provider)

    with pytest.raises(ProviderAuthError):
        await retry_provider_call(provider, REQUEST, TARGET, max_retries=2, base_delay=0)

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_successful_first_attempt_makes_one_call():
    provider = MockProvider()
    calls = _counting_wrapper(provider)

    await retry_provider_call(provider, REQUEST, TARGET, max_retries=2, base_delay=0)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_max_retries_bounds_call_count():
    provider = MockProvider()
    provider.queue_failure("mock-smart-chat", "server_error", count=10)
    calls = _counting_wrapper(provider)

    with pytest.raises(ProviderServerError):
        await retry_provider_call(provider, REQUEST, TARGET, max_retries=1, base_delay=0)

    assert len(calls) == 2  # 1 initial attempt + 1 retry
