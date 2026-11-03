import hmac

import pytest
from fastapi.testclient import TestClient

from app.auth.admin_session import create_admin_session, get_admin_settings, verify_admin_session
from app.config.loader import ConfigValidationError, get_config, reset_config
from app.main import app

ALPHA = {"Authorization": "Bearer alpha-secret-key"}


@pytest.mark.parametrize(
    ("headers", "message"),
    [
        ({}, "Missing authorization header"),
        ({"Authorization": "Token alpha-secret-key"}, "Invalid authorization format"),
        ({"Authorization": "Bearer"}, "Invalid authorization format"),
        ({"Authorization": "Bearer wrong-key"}, "Invalid API key"),
    ],
)
def test_team_authentication_rejections_are_standard(headers, message):
    response = TestClient(app).get("/v1/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"error": "unauthorized", "message": message}


def test_team_identity_is_sanitized_and_has_no_redis_side_effect(fake_redis):
    response = TestClient(app).get("/v1/me", headers=ALPHA)
    assert response.status_code == 200
    assert response.json() == {
        "team_id": "team_alpha",
        "name": "Team Alpha",
        "allowed_models": ["smart-chat", "cheap-chat"],
        "rate_limits": {"requests_per_minute": 60, "tokens_per_minute": 50000},
        "budgets": {"daily_usd": 5.0, "monthly_usd": 50.0},
    }
    assert "key" not in response.text.lower()


def test_rejected_authentication_stops_before_chat_dependencies(monkeypatch):
    called = False

    async def should_not_run(_team):
        nonlocal called
        called = True
        raise AssertionError("rate limiting must not run")

    monkeypatch.setattr("app.api.chat.check_rate_limit", should_not_run)
    response = TestClient(app).post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer wrong-key"},
        json={"model": "smart-chat", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 401
    assert called is False


def test_authentication_logs_and_metrics_do_not_expose_key(caplog):
    client = TestClient(app)
    secret = "credential-that-must-not-appear"
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {secret}"}).status_code == 401
    metrics = client.get("/metrics").text
    assert secret not in caplog.text
    assert secret not in metrics
    assert 'result="invalid",team_id="unknown"' in metrics


def test_key_lookup_checks_every_configured_key(monkeypatch):
    calls = []
    original = hmac.compare_digest

    def recording(candidate, configured):
        calls.append(configured)
        return original(candidate, configured)

    monkeypatch.setattr("app.config.loader.hmac.compare_digest", recording)
    response = TestClient(app).get("/v1/me", headers=ALPHA)
    assert response.status_code == 200
    assert calls == ["alpha-secret-key", "beta-secret-key"]


@pytest.mark.parametrize(
    "mapping",
    [
        "",
        "not-json",
        '{"team_alpha":"alpha-secret-key"}',
        '{"team_alpha":"alpha-secret-key","team_beta":"beta-secret-key","unknown":"x"}',
        '{"team_alpha":"","team_beta":"beta-secret-key"}',
        '{"team_alpha":"same","team_beta":"same"}',
    ],
)
def test_team_key_configuration_rejects_invalid_mappings(monkeypatch, mapping):
    if mapping:
        monkeypatch.setenv("TEAM_API_KEYS_JSON", mapping)
    else:
        monkeypatch.delenv("TEAM_API_KEYS_JSON")
    reset_config()
    with pytest.raises(ConfigValidationError):
        get_config()


def test_admin_session_login_protects_data_and_logout_clears_cookie():
    client = TestClient(app)
    assert client.get("/admin/teams").status_code == 401
    invalid = client.post("/admin/session", headers={"Authorization": "Bearer wrong"})
    assert invalid.status_code == 401

    login = client.post("/admin/session", headers={"Authorization": "Bearer local-admin-token"})
    assert login.status_code == 200
    assert login.json()["authenticated"] is True
    assert "HttpOnly" in login.headers["set-cookie"]
    assert "SameSite=strict" in login.headers["set-cookie"]
    assert client.get("/admin/teams").status_code == 200
    assert client.get("/providers/health").status_code == 200

    logout = client.delete("/admin/session")
    assert logout.json() == {"authenticated": False}
    assert client.get("/admin/teams").status_code == 401


def test_admin_session_rejects_tampering_and_expiry():
    settings = get_admin_settings()
    token, expires_at = create_admin_session(settings, now=1000)
    assert verify_admin_session(token, now=expires_at - 1) == expires_at
    with pytest.raises(Exception) as expired:
        verify_admin_session(token, now=expires_at)
    assert expired.value.status_code == 401
    with pytest.raises(Exception) as tampered:
        verify_admin_session(token + "x", now=1001)
    assert tampered.value.status_code == 401


def test_public_demo_rejects_local_admin_defaults(monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO", "true")
    monkeypatch.setenv("ADMIN_COOKIE_SECURE", "true")
    with pytest.raises(ValueError, match="non-default"):
        get_admin_settings()


def test_public_demo_rejects_local_team_defaults(monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO", "true")
    reset_config()
    with pytest.raises(ConfigValidationError, match="non-default"):
        get_config()
