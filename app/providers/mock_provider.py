import uuid

from app.models.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Choice,
    Usage,
)
from app.providers.base import BaseProvider
from app.providers.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
)

_FAILURE_MODES = {
    "timeout": ProviderTimeoutError,
    "rate_limit": ProviderRateLimitError,
    "server_error": ProviderServerError,
    "auth_error": ProviderAuthError,
}


class MockProvider(BaseProvider):
    """Deterministic test double. Queue failures per model with queue_failure()."""

    def __init__(self):
        self._fail_queue: dict[str, list[str]] = {}

    def queue_failure(self, model: str, mode: str, count: int = 1) -> None:
        """Make the next `count` call(s) to `model` raise the typed error for `mode`."""
        if mode not in _FAILURE_MODES:
            raise ValueError(f"Unknown failure mode: '{mode}' (expected one of {list(_FAILURE_MODES)})")
        self._fail_queue.setdefault(model, []).extend([mode] * count)

    def clear_failures(self, model: str | None = None) -> None:
        if model is None:
            self._fail_queue.clear()
        else:
            self._fail_queue.pop(model, None)

    async def chat_completion(
        self, request: ChatCompletionRequest, model: str
    ) -> ChatCompletionResponse:
        queue = self._fail_queue.get(model)
        if queue:
            mode = queue.pop(0)
            raise _FAILURE_MODES[mode](f"mock {mode} failure for model '{model}'", provider="mock")

        input_tokens = sum(len(m.content.split()) for m in request.messages)
        output_tokens = 20

        response_text = (
            f"Mock response from {model} for alias '{request.model}'. "
            f"Received {len(request.messages)} message(s)."
        )

        return ChatCompletionResponse(
            id=f"chatcmpl_mock_{uuid.uuid4().hex[:12]}",
            model_requested=request.model,
            model_served=f"mock:{model}",
            provider="mock",
            fallback_used=False,
            choices=[
                Choice(
                    index=0,
                    message=ChatMessage(role="assistant", content=response_text),
                    finish_reason="stop",
                )
            ],
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
        )
