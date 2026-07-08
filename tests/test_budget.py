import pytest
from fastapi.testclient import TestClient

from app.budget.manager import _daily_key, _monthly_key, estimate_cost
from app.main import app
from app.models.chat import Usage
from app.providers.registry import get_provider_registry

client = TestClient(app)

ALPHA_HEADERS = {"Authorization": "Bearer alpha-secret-key"}
CHEAP_CHAT_BODY = {
    "model": "cheap-chat",
    "messages": [{"role": "user", "content": "Hello gateway"}],
}

# cheap-chat pricing: input $0.001/1k, output $0.002/1k (app/config/teams.yaml).
# MockProvider returns input_tokens = word count (2 for "Hello gateway"), output_tokens = 20.
EXPECTED_COST = (2 / 1000 * 0.001) + (20 / 1000 * 0.002)


def test_estimate_cost_is_deterministic():
    usage = Usage(input_tokens=2, output_tokens=20, total_tokens=22)
    assert estimate_cost(usage, "cheap-chat") == pytest.approx(EXPECTED_COST)


def test_spend_increments_after_successful_request(fake_redis):
    response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)
    assert response.status_code == 200

    daily_spend = client.get("/admin/teams/team_alpha/usage").json()["spend"]["daily_usd"]
    assert daily_spend == pytest.approx(EXPECTED_COST)


@pytest.mark.asyncio
async def test_daily_budget_exceeded_blocks_request(fake_redis):
    # team_alpha's daily cap is $5.00 (teams.yaml) — seed spend at the cap.
    await fake_redis.set(_daily_key("team_alpha"), "5.00")

    response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)
    assert response.status_code == 402
    body = response.json()
    assert body["error"] == "budget_exceeded"


@pytest.mark.asyncio
async def test_monthly_budget_exceeded_blocks_request(fake_redis):
    # team_alpha's monthly cap is $50.00 (teams.yaml) — seed spend at the cap, daily left untouched.
    await fake_redis.set(_monthly_key("team_alpha"), "50.00")

    response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)
    assert response.status_code == 402
    body = response.json()
    assert body["error"] == "budget_exceeded"


@pytest.mark.asyncio
async def test_budget_exceeded_does_not_call_provider(fake_redis, monkeypatch):
    mock_provider = get_provider_registry().require("mock")
    call_count = 0
    original_chat_completion = mock_provider.chat_completion

    async def counting_chat_completion(request, target):
        nonlocal call_count
        call_count += 1
        return await original_chat_completion(request, target)

    monkeypatch.setattr(mock_provider, "chat_completion", counting_chat_completion)

    await fake_redis.set(_daily_key("team_alpha"), "5.00")
    response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)

    assert response.status_code == 402
    assert call_count == 0


def test_failed_provider_call_does_not_record_spend(monkeypatch):
    mock_provider = get_provider_registry().require("mock")

    async def failing_chat_completion(request, target):
        raise RuntimeError("simulated provider failure")

    monkeypatch.setattr(mock_provider, "chat_completion", failing_chat_completion)

    with pytest.raises(RuntimeError):
        client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)

    daily_spend = client.get("/admin/teams/team_alpha/usage").json()["spend"]["daily_usd"]
    assert daily_spend == 0.0
