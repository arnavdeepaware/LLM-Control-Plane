from fastapi.testclient import TestClient

from app.main import app
from app.routing import router as router_module

client = TestClient(app)

ALPHA_HEADERS = {"Authorization": "Bearer alpha-secret-key"}
BETA_HEADERS = {"Authorization": "Bearer beta-secret-key"}

CHEAP_CHAT_BODY = {
    "model": "cheap-chat",
    "messages": [{"role": "user", "content": "Hello gateway"}],
}

# team_beta is configured with requests_per_minute: 20 (the lowest limit), so it's
# the cheapest team to drive over its limit in a test.
BETA_RPM = 20


def test_within_limit_returns_200():
    for _ in range(BETA_RPM):
        response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=BETA_HEADERS)
        assert response.status_code == 200


def test_exceeding_limit_returns_429():
    for _ in range(BETA_RPM):
        client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=BETA_HEADERS)

    response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=BETA_HEADERS)
    assert response.status_code == 429


def test_429_includes_retry_after_header_and_body():
    for _ in range(BETA_RPM):
        client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=BETA_HEADERS)

    response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=BETA_HEADERS)
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    body = response.json()
    assert body["error"] == "rate_limit_exceeded"
    assert "retry_after_seconds" in body
    assert body["retry_after_seconds"] > 0


def test_rate_limited_team_does_not_block_other_team():
    for _ in range(BETA_RPM):
        client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=BETA_HEADERS)

    # beta is now rate limited; alpha (independent bucket) should still succeed.
    blocked = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=BETA_HEADERS)
    assert blocked.status_code == 429

    still_ok = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)
    assert still_ok.status_code == 200


def test_rate_limited_request_does_not_call_provider(monkeypatch):
    mock_provider = router_module._provider_registry["mock"]
    call_count = 0
    original_chat_completion = mock_provider.chat_completion

    async def counting_chat_completion(request, model):
        nonlocal call_count
        call_count += 1
        return await original_chat_completion(request, model)

    monkeypatch.setattr(mock_provider, "chat_completion", counting_chat_completion)

    for _ in range(BETA_RPM):
        client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=BETA_HEADERS)
    assert call_count == BETA_RPM

    response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=BETA_HEADERS)
    assert response.status_code == 429
    assert call_count == BETA_RPM
