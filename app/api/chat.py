from fastapi import APIRouter, Depends, HTTPException

from app.auth.api_key import get_current_team
from app.budget.manager import check_budget, estimate_cost, record_spend
from app.models.chat import ChatCompletionRequest, ChatCompletionResponse
from app.models.team import TeamConfig
from app.rate_limit.limiter import check_rate_limit, record_tokens
from app.routing.fallback import resilient_chat_completion
from app.routing.router import resolve_model_route

router = APIRouter()


@router.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completion(
    request: ChatCompletionRequest,
    team: TeamConfig = Depends(get_current_team),
) -> ChatCompletionResponse:
    resolve_model_route(team, request.model)  # fail fast on disallowed/unknown model before touching Redis

    rate_limit_result = await check_rate_limit(team)
    if not rate_limit_result.allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": (
                    f"Team {team.team_id} exceeded "
                    f"{team.rate_limits.requests_per_minute} requests per minute."
                ),
                "retry_after_seconds": rate_limit_result.retry_after_seconds,
            },
            headers={"Retry-After": str(rate_limit_result.retry_after_seconds)},
        )

    budget_status = await check_budget(team)
    if not budget_status.allowed:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "budget_exceeded",
                "message": (
                    f"Team {team.team_id} reached its {budget_status.scope} budget of "
                    f"${budget_status.limit_usd:.2f}."
                ),
            },
        )

    response = await resilient_chat_completion(request, team, request.model)

    cost = estimate_cost(response.usage, request.model)
    await record_spend(team, cost)
    await record_tokens(team, response.usage.total_tokens)

    return response
