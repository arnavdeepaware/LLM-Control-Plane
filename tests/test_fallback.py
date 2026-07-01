import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routing import circuit_breaker
from app.routing import retry as retry_module
from app.routing import router as router_module

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    """Retry backoff runs for real through the HTTP endpoint; skip the actual wait so
    these tests stay fast and don't depend on wall-clock timing."""

    async def instant_sleep(_seconds):
        return None

    monkeypatch.setattr(retry_module.asyncio, "sleep", instant_sleep)

ALPHA_HEADERS = {"Authorization": "Bearer alpha-secret-key"}
SMART_CHAT_BODY = {
    "model": "smart-chat",
    "messages": [{"role": "user", "content": "Hello gateway"}],
}

# smart-chat route (teams.yaml): primary mock:mock-smart-chat, fallback mock:mock-backup-chat.
# retry default max_retries=2 -> 3 attempts before a target is considered exhausted.


def _track_calls(monkeypatch) -> list[str]:
    """Record every model the shared mock provider is actually called with."""
    mock_provider = router_module._provider_registry["mock"]
    calls: list[str] = []
    original = mock_provider.chat_completion

    async def tracking(request, model):
        calls.append(model)
        return await original(request, model)

    monkeypatch.setattr(mock_provider, "chat_completion", tracking)
    return calls


def test_primary_success_returns_no_fallback():
    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["fallback_used"] is False
    assert body["model_served"] == "mock:mock-smart-chat"
    assert body["provider"] == "mock"


def test_primary_failure_triggers_fallback():
    mock_provider = router_module._provider_registry["mock"]
    mock_provider.queue_failure("mock-smart-chat", "timeout", count=3)  # exhausts all 3 attempts

    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["fallback_used"] is True
    assert body["model_served"] == "mock:mock-backup-chat"
    assert body["provider"] == "mock"
    # core response shape stays intact even on the fallback path
    assert len(body["choices"]) == 1
    assert "usage" in body


def test_all_providers_failing_returns_503():
    mock_provider = router_module._provider_registry["mock"]
    mock_provider.queue_failure("mock-smart-chat", "server_error", count=3)
    mock_provider.queue_failure("mock-backup-chat", "server_error", count=1)  # fallbacks get one attempt

    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)
    assert response.status_code == 503
    assert response.json()["error"] == "no_provider_available"


def test_non_retryable_error_does_not_trigger_fallback(monkeypatch):
    calls = _track_calls(monkeypatch)
    mock_provider = router_module._provider_registry["mock"]
    mock_provider.queue_failure("mock-smart-chat", "auth_error", count=1)

    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)
    assert response.status_code == 502
    assert response.json()["error"] == "provider_error"
    assert calls == ["mock-smart-chat"]  # fallback was never attempted


def test_open_circuit_skips_primary(monkeypatch):
    calls = _track_calls(monkeypatch)
    for _ in range(5):  # teams.yaml failure_threshold is 5
        circuit_breaker.record_failure("mock", "mock-smart-chat")

    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["fallback_used"] is True
    assert body["model_served"] == "mock:mock-backup-chat"
    assert calls == ["mock-backup-chat"]  # primary was skipped entirely, not even attempted


def test_circuit_recovers_after_cooldown_via_half_open_success(monkeypatch):
    calls = _track_calls(monkeypatch)
    for _ in range(5):
        circuit_breaker.record_failure("mock", "mock-smart-chat")
    circuit_breaker.get_state("mock", "mock-smart-chat").opened_at = time.time() - 61  # cooldown_seconds is 60

    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)

    assert response.status_code == 200
    assert response.json()["fallback_used"] is False  # half-open test request hit the primary directly
    assert calls == ["mock-smart-chat"]
    assert circuit_breaker.get_state("mock", "mock-smart-chat").state == "closed"


def test_rate_limited_request_does_not_call_any_provider(monkeypatch):
    calls = _track_calls(monkeypatch)
    for _ in range(60):  # team_alpha requests_per_minute is 60 (teams.yaml)
        client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)
    calls.clear()

    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)
    assert response.status_code == 429
    assert calls == []
