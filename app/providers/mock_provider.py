import uuid

from app.models.chat import ChatCompletionRequest, ChatCompletionResponse
from app.providers.base import BaseProvider
from app.providers.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
)
from app.providers.target import ProviderTarget

_FAILURE_MODES = {
    "timeout": ProviderTimeoutError,
    "rate_limit": ProviderRateLimitError,
    "server_error": ProviderServerError,
    "auth_error": ProviderAuthError,
}


class MockProvider(BaseProvider):
    """Deterministic test double. Queue failures per model with queue_failure()."""

    provider_name = "mock"

    def __init__(self):
        self._fail_queue: dict[str, list[str]] = {}

    def queue_failure(self, model: str, mode: str, count: int = 1) -> None:
        """Make the next `count` call(s) to `model` raise the typed error for `mode`."""
        if mode not in _FAILURE_MODES:
            raise ValueError(f"Unknown failure mode: '{mode}' (expected one of {list(_FAILURE_MODES)})")
        self._fail_queue.setdefault(model, []).extend([mode] * count)

    def queued_failures(self) -> dict[str, list[str]]:
        return {model: list(modes) for model, modes in self._fail_queue.items() if modes}

    def clear_failures(self) -> None:
        self._fail_queue.clear()

    async def chat_completion(
        self, request: ChatCompletionRequest, target: ProviderTarget
    ) -> ChatCompletionResponse:
        self.validate_target(target)

        queue = self._fail_queue.get(target.model)
        if queue:
            mode = queue.pop(0)
            raise _FAILURE_MODES[mode](
                f"mock {mode} failure for model '{target.model}'",
                provider=self.provider_name,
            )

        input_tokens = sum(len(m.content.split()) for m in request.messages)
        output_tokens = 20

        response_text = (
            f"Mock response from {target.model} for alias '{request.model}'. "
            f"Received {len(request.messages)} message(s)."
        )

        return self.normalize_chat_response(
            request=request,
            target=target,
            content=response_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_id=f"chatcmpl_mock_{uuid.uuid4().hex[:12]}",
        )
