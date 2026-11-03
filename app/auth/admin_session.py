import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

from fastapi import Cookie, HTTPException

ADMIN_COOKIE_NAME = "llm_admin_session"
LOCAL_ADMIN_TOKEN = "local-admin-token"
LOCAL_SESSION_SECRET = "local-session-secret-change-me"


@dataclass(frozen=True)
class AdminSettings:
    control_token: str
    session_secret: str
    ttl_seconds: int
    cookie_secure: bool


def get_admin_settings() -> AdminSettings:
    token = os.environ.get("ADMIN_CONTROL_TOKEN", "")
    secret = os.environ.get("ADMIN_SESSION_SECRET", "")
    if not token or not secret:
        raise ValueError("ADMIN_CONTROL_TOKEN and ADMIN_SESSION_SECRET are required")
    try:
        ttl = int(os.environ.get("ADMIN_SESSION_TTL_SECONDS", "28800"))
    except ValueError as exc:
        raise ValueError("ADMIN_SESSION_TTL_SECONDS must be an integer") from exc
    if ttl < 60:
        raise ValueError("ADMIN_SESSION_TTL_SECONDS must be at least 60")
    secure = os.environ.get("ADMIN_COOKIE_SECURE", "false").lower() == "true"
    if os.environ.get("PUBLIC_DEMO", "false").lower() == "true":
        if token == LOCAL_ADMIN_TOKEN or secret == LOCAL_SESSION_SECRET:
            raise ValueError("Public demo requires non-default admin credentials")
        if len(token) < 16 or len(secret) < 32:
            raise ValueError("Public demo admin credentials are too short")
        if not secure:
            raise ValueError("Public demo requires secure admin cookies")
    return AdminSettings(token, secret, ttl, secure)


def validate_admin_token(authorization: str | None) -> AdminSettings:
    settings = get_admin_settings()
    parts = authorization.split() if authorization else []
    if len(parts) != 2 or parts[0].lower() != "bearer" or not hmac.compare_digest(parts[1], settings.control_token):
        raise HTTPException(status_code=401, detail="Invalid admin access code", headers={"WWW-Authenticate": "Bearer"})
    return settings


def _encode(payload: dict, secret: str) -> str:
    data = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}.{signature}"


def create_admin_session(settings: AdminSettings, now: int | None = None) -> tuple[str, int]:
    expires_at = (now or int(time.time())) + settings.ttl_seconds
    return _encode({"exp": expires_at, "purpose": "admin"}, settings.session_secret), expires_at


def verify_admin_session(token: str | None, now: int | None = None) -> int:
    if not token:
        raise HTTPException(status_code=401, detail="Admin session required")
    try:
        data, supplied_signature = token.split(".", 1)
        settings = get_admin_settings()
        expected_signature = hmac.new(settings.session_secret.encode(), data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError
        padded = data + "=" * (-len(data) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        expires_at = int(payload["exp"])
        if payload.get("purpose") != "admin" or expires_at <= (now or int(time.time())):
            raise ValueError
        return expires_at
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, binascii.Error):
        raise HTTPException(status_code=401, detail="Invalid or expired admin session") from None


async def require_admin_session(llm_admin_session: str | None = Cookie(default=None)) -> int:
    return verify_admin_session(llm_admin_session)
