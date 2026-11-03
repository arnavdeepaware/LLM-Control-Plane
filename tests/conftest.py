import pytest
from fakeredis.aioredis import FakeRedis

from app.config.loader import reset_config
from app.providers.registry import reset_provider_registry
from app.redis_client import reset_redis, set_redis
from app.routing import circuit_breaker


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """Swap the Redis singleton for a fresh in-memory fake before every test."""
    monkeypatch.setenv("TEAM_API_KEYS_JSON", '{"team_alpha":"alpha-secret-key","team_beta":"beta-secret-key"}')
    monkeypatch.setenv("ADMIN_CONTROL_TOKEN", "local-admin-token")
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "local-session-secret-change-me")
    monkeypatch.setenv("ADMIN_COOKIE_SECURE", "false")
    monkeypatch.delenv("PUBLIC_DEMO", raising=False)
    reset_config()
    reset_provider_registry()
    circuit_breaker.reset_circuits()
    client = FakeRedis(decode_responses=True)
    set_redis(client)
    yield client
    reset_redis()
    reset_provider_registry()
