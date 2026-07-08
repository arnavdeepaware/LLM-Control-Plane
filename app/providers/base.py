from abc import ABC, abstractmethod
import uuid

from app.models.chat import ChatCompletionRequest, ChatCompletionResponse
from app.models.chat import ChatMessage, Choice, Usage
from app.providers.errors import ProviderConfigurationError
from app.providers.target import ProviderTarget


class BaseProvider(ABC):
    provider_name: str = ""

    def validate_target(self, target: ProviderTarget) -> None:
        if target.provider != self.provider_name:
            raise ProviderConfigurationError(
                f"Provider target '{target.to_string()}' does not match provider '{self.provider_name}'",
                provider=self.provider_name,
            )

    def is_enabled(self) -> bool:
        return True

    def normalize_chat_response(
        self,
        request: ChatCompletionRequest,
        target: ProviderTarget,
        content: str,
        input_tokens: int,
        output_tokens: int,
        response_id: str | None = None,
    ) -> ChatCompletionResponse:
        self.validate_target(target)

        return ChatCompletionResponse(
            id=response_id or f"chatcmpl_{self.provider_name}_{uuid.uuid4().hex[:12]}",
            model_requested=request.model,
            model_served=target.to_string(),
            provider=target.provider,
            fallback_used=False,
            choices=[
                Choice(
                    index=0,
                    message=ChatMessage(role="assistant", content=content),
                    finish_reason="stop",
                )
            ],
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
        )

    @abstractmethod
    async def chat_completion(
        self, request: ChatCompletionRequest, target: ProviderTarget
    ) -> ChatCompletionResponse: ...
