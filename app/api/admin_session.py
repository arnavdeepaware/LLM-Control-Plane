from fastapi import APIRouter, Cookie, Header, Response

from app.auth.admin_session import (
    ADMIN_COOKIE_NAME,
    create_admin_session,
    get_admin_settings,
    validate_admin_token,
    verify_admin_session,
)

router = APIRouter(prefix="/admin/session")


@router.post("")
async def login(response: Response, authorization: str | None = Header(default=None)):
    settings = validate_admin_token(authorization)
    token, expires_at = create_admin_session(settings)
    response.set_cookie(
        ADMIN_COOKIE_NAME,
        token,
        max_age=settings.ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return {"authenticated": True, "expires_at": expires_at}


@router.get("")
async def session_status(llm_admin_session: str | None = Cookie(default=None)):
    return {"authenticated": True, "expires_at": verify_admin_session(llm_admin_session)}


@router.delete("")
async def logout(response: Response):
    response.delete_cookie(ADMIN_COOKIE_NAME, path="/")
    return {"authenticated": False}


@router.get("/verify", status_code=204)
async def verify(llm_admin_session: str | None = Cookie(default=None)):
    verify_admin_session(llm_admin_session)
    return Response(status_code=204)
