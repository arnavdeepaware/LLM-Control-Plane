import logging

from fastapi import Header, HTTPException

from app.config.loader import get_team_by_api_key
from app.models.team import TeamConfig
from app.observability.metrics import AUTH_ATTEMPTS
from app.observability.request_context import set_team_id

logger = logging.getLogger("app.auth")


def _reject(result: str, message: str) -> None:
    AUTH_ATTEMPTS.labels(result=result, team_id="unknown").inc()
    logger.info("team_authentication", extra={"extra_fields": {"auth_result": result, "team_id": ""}})
    raise HTTPException(status_code=401, detail=message, headers={"WWW-Authenticate": "Bearer"})


async def get_current_team(authorization: str = Header(default=None)) -> TeamConfig:
    if not authorization:
        _reject("missing", "Missing authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        _reject("malformed", "Invalid authorization format")

    token = parts[1]
    team = get_team_by_api_key(token)
    if team is None:
        _reject("invalid", "Invalid API key")

    set_team_id(team.team_id)
    AUTH_ATTEMPTS.labels(result="success", team_id=team.team_id).inc()
    logger.info("team_authentication", extra={"extra_fields": {"auth_result": "success", "team_id": team.team_id}})
    return team
