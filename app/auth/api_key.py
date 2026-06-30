from fastapi import Header, HTTPException

from app.config.loader import get_team_by_api_key
from app.models.team import TeamConfig


async def get_current_team(authorization: str = Header(default=None)) -> TeamConfig:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")

    token = authorization.removeprefix("Bearer ")
    team = get_team_by_api_key(token)
    if team is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return team
