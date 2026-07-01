from fastapi.testclient import TestClient

from app.main import app
from app.observability.request_context import generate_request_id

client = TestClient(app)

ALPHA_HEADERS = {"Authorization": "Bearer alpha-secret-key"}

CHEAP_CHAT_BODY = {
    "model": "cheap-chat",
    "messages": [{"role": "user", "content": "Hello gateway"}],
}


def test_request_id_format():
    assert generate_request_id().startswith("req_")


def test_request_id_is_unique():
    assert generate_request_id() != generate_request_id()


def test_response_includes_x_request_id_header():
    response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)
    assert "x-request-id" in response.headers
    assert response.headers["x-request-id"].startswith("req_")


def test_custom_request_id_is_propagated():
    headers = {**ALPHA_HEADERS, "X-Request-ID": "req_custom123"}
    response = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=headers)
    assert response.headers["x-request-id"] == "req_custom123"


def test_request_id_is_unique_per_request():
    r1 = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)
    r2 = client.post("/v1/chat/completions", json=CHEAP_CHAT_BODY, headers=ALPHA_HEADERS)
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]
