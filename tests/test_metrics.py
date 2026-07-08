from fastapi.testclient import TestClient

from app.main import app
from app.observability.metrics import REGISTRY
from app.providers.registry import get_provider_registry

client = TestClient(app)

ALPHA_HEADERS = {"Authorization": "Bearer alpha-secret-key"}
BETA_HEADERS = {"Authorization": "Bearer beta-secret-key"}

CHEAP_CHAT_BODY = {
    "model": "cheap-chat",
    "messages": [{"role": "user", "content": "Hello gateway"}],
}

SMART_CHAT_BODY = {
    "model": "smart-chat",
    "messages": [{"role": "user", "content": "Hello gateway"}],
}


def get_metric_value(name: str, labels: dict) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_metrics_endpoint_returns_200():
    response = client.get("/metrics")
    assert response.status_code == 200


def test_metrics_endpoint_returns_prometheus_format():
    response = client.get("/metrics")
    assert "# HELP" in response.text
    assert "# TYPE" in response.text


def test_metrics_endpoint_contains_gateway_metric_names():
    response = client.get("/metrics")
    for name in [
        "llm_gateway_requests_total",
        "llm_gateway_request_latency_seconds",
        "llm_gateway_provider_errors_total",
        "llm_gateway_fallbacks_total",
        "llm_gateway_retries_total",
        "llm_gateway_rate_limited_total",
        "llm_gateway_budget_blocked_total",
        "llm_gateway_tokens_total",
        "llm_gateway_cost_usd_total",
        "llm_gateway_circuit_state",
    ]:
        assert name in response.text


def test_successful_request_increments_request_counter():
    before = get_metric_value(
        "llm_gateway_requests_total",
        {"team_id": "team_alpha", "model_requested": "cheap-chat", "status_code": "200"},
    )
    client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)
    after = get_metric_value(
        "llm_gateway_requests_total",
        {"team_id": "team_alpha", "model_requested": "cheap-chat", "status_code": "200"},
    )
    assert after == before + 1


def test_successful_request_records_latency():
    before = get_metric_value(
        "llm_gateway_request_latency_seconds_count",
        {"team_id": "team_alpha", "model_requested": "cheap-chat"},
    )
    client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)
    after = get_metric_value(
        "llm_gateway_request_latency_seconds_count",
        {"team_id": "team_alpha", "model_requested": "cheap-chat"},
    )
    assert after == before + 1


def test_rate_limited_request_increments_rate_limited_counter():
    before = get_metric_value("llm_gateway_rate_limited_total", {"team_id": "team_beta"})
    for _ in range(21):
        client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=BETA_HEADERS)
    after = get_metric_value("llm_gateway_rate_limited_total", {"team_id": "team_beta"})
    assert after > before


def test_budget_blocked_request_increments_budget_counter(monkeypatch):
    import app.budget.manager as budget_manager

    async def fake_check_budget(team):
        return budget_manager.BudgetStatus(allowed=False, scope="daily", limit_usd=5.0, spent_usd=5.0)

    monkeypatch.setattr("app.api.chat.check_budget", fake_check_budget)

    before = get_metric_value("llm_gateway_budget_blocked_total", {"team_id": "team_alpha"})
    response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)
    assert response.status_code == 402
    after = get_metric_value("llm_gateway_budget_blocked_total", {"team_id": "team_alpha"})
    assert after == before + 1


def test_fallback_increments_fallback_counter():
    mock_provider = get_provider_registry().require("mock")
    mock_provider.queue_failure("mock-smart-chat", "server_error", count=3)

    before = get_metric_value(
        "llm_gateway_fallbacks_total", {"team_id": "team_alpha", "model_requested": "smart-chat"}
    )
    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)
    assert response.status_code == 200
    assert response.json()["fallback_used"] is True
    after = get_metric_value(
        "llm_gateway_fallbacks_total", {"team_id": "team_alpha", "model_requested": "smart-chat"}
    )
    assert after == before + 1


def test_provider_error_increments_error_counter():
    mock_provider = get_provider_registry().require("mock")
    mock_provider.queue_failure("mock-smart-chat", "auth_error", count=1)

    before = get_metric_value(
        "llm_gateway_provider_errors_total",
        {"provider": "mock", "model_requested": "smart-chat", "error_type": "ProviderAuthError"},
    )
    client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)
    after = get_metric_value(
        "llm_gateway_provider_errors_total",
        {"provider": "mock", "model_requested": "smart-chat", "error_type": "ProviderAuthError"},
    )
    assert after == before + 1


def test_tokens_counter_incremented_on_success():
    before_input = get_metric_value(
        "llm_gateway_tokens_total",
        {"team_id": "team_alpha", "model_requested": "cheap-chat", "token_type": "input"},
    )
    response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)
    usage = response.json()["usage"]
    after_input = get_metric_value(
        "llm_gateway_tokens_total",
        {"team_id": "team_alpha", "model_requested": "cheap-chat", "token_type": "input"},
    )
    assert after_input == before_input + usage["input_tokens"]


def test_cost_counter_incremented_on_success():
    before = get_metric_value(
        "llm_gateway_cost_usd_total", {"team_id": "team_alpha", "model_requested": "cheap-chat"}
    )
    client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)
    after = get_metric_value(
        "llm_gateway_cost_usd_total", {"team_id": "team_alpha", "model_requested": "cheap-chat"}
    )
    assert after > before


def test_retry_increments_retry_counter(monkeypatch):
    import app.routing.retry as retry_module

    async def instant_sleep(_seconds):
        return None

    monkeypatch.setattr(retry_module.asyncio, "sleep", instant_sleep)

    mock_provider = get_provider_registry().require("mock")
    mock_provider.queue_failure("mock-smart-chat", "server_error", count=1)

    before = get_metric_value(
        "llm_gateway_retries_total", {"provider": "mock", "model_requested": "smart-chat"}
    )
    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)
    assert response.status_code == 200
    after = get_metric_value(
        "llm_gateway_retries_total", {"provider": "mock", "model_requested": "smart-chat"}
    )
    assert after == before + 1


def test_circuit_breaker_gauge_updates():
    from app.routing import circuit_breaker

    circuit_breaker.record_failure("mock", "gauge-test-model")
    circuit_breaker.record_failure("mock", "gauge-test-model")
    circuit_breaker.record_failure("mock", "gauge-test-model")
    circuit_breaker.record_failure("mock", "gauge-test-model")
    circuit_breaker.record_failure("mock", "gauge-test-model")

    value = get_metric_value("llm_gateway_circuit_state", {"provider": "mock", "model": "gauge-test-model"})
    assert value == 1.0

    circuit_breaker.record_success("mock", "gauge-test-model")
    value = get_metric_value("llm_gateway_circuit_state", {"provider": "mock", "model": "gauge-test-model"})
    assert value == 0.0
