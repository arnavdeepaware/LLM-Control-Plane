import pytest
from fastapi.testclient import TestClient

from app.budget.manager import _daily_key
from app.main import app
from app.observability.metrics import REGISTRY
from app.providers.registry import get_provider_registry
from app.routing import circuit_breaker
from app.routing import retry as retry_module

client = TestClient(app)

ALPHA_HEADERS = {"Authorization": "Bearer alpha-secret-key"}
BETA_HEADERS = {"Authorization": "Bearer beta-secret-key"}

SMART_CHAT_BODY = {
    "model": "smart-chat",
    "messages": [{"role": "user", "content": "Hello gateway"}],
}

CHEAP_CHAT_BODY = {
    "model": "cheap-chat",
    "messages": [{"role": "user", "content": "Hello gateway"}],
}


@pytest.fixture(autouse=True)
def no_real_retry_sleep(monkeypatch):
    async def instant_sleep(_seconds):
        return None

    monkeypatch.setattr(retry_module.asyncio, "sleep", instant_sleep)


def test_health_endpoint_integration():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_endpoint_integration():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "# HELP llm_gateway_requests_total" in response.text
    assert "# TYPE llm_gateway_request_latency_seconds histogram" in response.text


def test_valid_chat_request_integration():
    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["model_requested"] == "smart-chat"
    assert body["model_served"] == "mock:mock-smart-chat"
    assert body["provider"] == "mock"
    assert body["fallback_used"] is False
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["usage"]["total_tokens"] == body["usage"]["input_tokens"] + body["usage"]["output_tokens"]


def test_auth_and_model_rejection_paths_integration():
    missing_auth = client.post("/v1/chat/completions", json=SMART_CHAT_BODY)
    invalid_auth = client.post(
        "/v1/chat/completions",
        json=SMART_CHAT_BODY,
        headers={"Authorization": "Bearer wrong-key"},
    )
    disallowed_model = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=BETA_HEADERS)
    unknown_model = client.post(
        "/v1/chat/completions",
        json={**SMART_CHAT_BODY, "model": "unknown-chat"},
        headers=ALPHA_HEADERS,
    )

    assert missing_auth.status_code == 401
    assert invalid_auth.status_code == 401
    assert disallowed_model.status_code == 403
    assert unknown_model.status_code == 403


def test_rate_limit_integration():
    for _ in range(20):
        response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=BETA_HEADERS)
        assert response.status_code == 200

    response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=BETA_HEADERS)

    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert response.json()["error"] == "rate_limit_exceeded"


@pytest.mark.asyncio
async def test_budget_blocking_integration(fake_redis):
    await fake_redis.set(_daily_key("team_alpha"), "5.00")

    response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)

    assert response.status_code == 402
    assert response.json()["error"] == "budget_exceeded"


def test_fallback_used_path_integration():
    mock_provider = get_provider_registry().require("mock")
    mock_provider.queue_failure("mock-smart-chat", "server_error", count=3)

    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["fallback_used"] is True
    assert body["model_served"] == "mock:mock-backup-chat"


def test_all_providers_failed_path_integration():
    mock_provider = get_provider_registry().require("mock")
    mock_provider.queue_failure("mock-smart-chat", "server_error", count=3)
    mock_provider.queue_failure("mock-backup-chat", "server_error", count=1)

    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)

    assert response.status_code == 503
    assert response.json()["error"] == "no_provider_available"


def test_circuit_open_primary_skips_to_fallback_integration():
    for _ in range(5):
        circuit_breaker.record_failure("mock", "mock-smart-chat")

    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)

    assert response.status_code == 200
    assert response.json()["fallback_used"] is True
    assert response.json()["model_served"] == "mock:mock-backup-chat"


def test_metrics_exposed_after_gateway_traffic_integration():
    mock_provider = get_provider_registry().require("mock")
    mock_provider.queue_failure("mock-smart-chat", "server_error", count=1)

    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)
    assert response.status_code == 200

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    for metric_name in [
        "llm_gateway_requests_total",
        "llm_gateway_retries_total",
        "llm_gateway_provider_errors_total",
        "llm_gateway_tokens_total",
        "llm_gateway_cost_usd_total",
    ]:
        assert metric_name in metrics_response.text

    assert REGISTRY.get_sample_value(
        "llm_gateway_retries_total",
        {"provider": "mock", "model_requested": "smart-chat"},
    )
