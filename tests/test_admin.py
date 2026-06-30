from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ALPHA_HEADERS = {"Authorization": "Bearer alpha-secret-key"}
CHEAP_CHAT_BODY = {
    "model": "cheap-chat",
    "messages": [{"role": "user", "content": "Hello gateway"}],
}


def test_usage_endpoint_returns_200_with_expected_fields():
    client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)

    response = client.get("/admin/teams/team_alpha/usage")
    assert response.status_code == 200
    body = response.json()
    assert body["team_id"] == "team_alpha"
    assert body["rate_limits"]["requests_per_minute"] == 60
    assert body["tokens_this_minute"] > 0
    assert body["spend"]["daily_usd"] > 0
    assert body["budgets"]["daily_usd"] == 5.00


def test_limits_endpoint_matches_config():
    response = client.get("/admin/teams/team_beta/limits")
    assert response.status_code == 200
    body = response.json()
    assert body["team_id"] == "team_beta"
    assert body["rate_limits"]["requests_per_minute"] == 20
    assert body["rate_limits"]["tokens_per_minute"] == 10000
    assert body["budgets"]["daily_usd"] == 1.00
    assert body["budgets"]["monthly_usd"] == 20.00


def test_unknown_team_usage_returns_404():
    response = client.get("/admin/teams/team_nonexistent/usage")
    assert response.status_code == 404


def test_unknown_team_limits_returns_404():
    response = client.get("/admin/teams/team_nonexistent/limits")
    assert response.status_code == 404
