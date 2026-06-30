from fastapi import APIRouter, Depends

from app.auth.api_key import get_current_team
from app.models.chat import ChatCompletionRequest, ChatCompletionResponse
from app.models.team import TeamConfig
from app.routing.router import resolve_route

router = APIRouter()


@router.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completion(
    request: ChatCompletionRequest,
    team: TeamConfig = Depends(get_current_team),
) -> ChatCompletionResponse:
    provider, model = resolve_route(team, request.model)
    return await provider.chat_completion(request, model)
