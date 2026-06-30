from abc import ABC, abstractmethod

from app.models.chat import ChatCompletionRequest, ChatCompletionResponse


class BaseProvider(ABC):
    @abstractmethod
    async def chat_completion(
        self, request: ChatCompletionRequest, model: str
    ) -> ChatCompletionResponse: ...
