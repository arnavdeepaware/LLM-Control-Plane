from fastapi.testclient import TestClient

from app.main import app

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


def test_valid_request_returns_200():
    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)
    assert response.status_code == 200


def test_missing_auth_returns_401():
    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY)
    assert response.status_code == 401


def test_malformed_auth_returns_401():
    response = client.post(
        "/v1/chat/completions",
        json=SMART_CHAT_BODY,
        headers={"Authorization": "Token alpha-secret-key"},
    )
    assert response.status_code == 401


def test_invalid_key_returns_401():
    response = client.post(
        "/v1/chat/completions",
        json=SMART_CHAT_BODY,
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert response.status_code == 401


def test_disallowed_model_returns_403():
    # team_beta is not allowed smart-chat
    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=BETA_HEADERS)
    assert response.status_code == 403


def test_unknown_model_returns_403():
    body = {**SMART_CHAT_BODY, "model": "nonexistent-model"}
    response = client.post("/v1/chat/completions", json=body, headers=ALPHA_HEADERS)
    assert response.status_code == 403


def test_response_shape_is_correct():
    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["model_requested"] == "smart-chat"
    assert data["model_served"] == "mock:mock-smart-chat"
    assert data["provider"] == "mock"
    assert data["fallback_used"] is False
    assert data["object"] == "chat.completion"
    assert data["id"].startswith("chatcmpl_mock_")
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert "usage" in data


def test_usage_tokens_are_positive():
    response = client.post("/v1/chat/completions", json=SMART_CHAT_BODY, headers=ALPHA_HEADERS)
    usage = response.json()["usage"]
    assert usage["input_tokens"] > 0
    assert usage["output_tokens"] > 0
    assert usage["total_tokens"] == usage["input_tokens"] + usage["output_tokens"]


def test_cheap_chat_works_for_alpha():
    response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)
    assert response.status_code == 200
    assert response.json()["model_served"] == "mock:mock-cheap-chat"


def test_cheap_chat_works_for_beta():
    response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=BETA_HEADERS)
    assert response.status_code == 200
    assert response.json()["model_served"] == "mock:mock-cheap-chat"
