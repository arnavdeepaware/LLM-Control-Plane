import uuid

from app.models.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Choice,
    Usage,
)
from app.providers.base import BaseProvider


class MockProvider(BaseProvider):
    async def chat_completion(
        self, request: ChatCompletionRequest, model: str
    ) -> ChatCompletionResponse:
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
