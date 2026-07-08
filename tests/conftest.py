import pytest
from fakeredis.aioredis import FakeRedis

from app.config.loader import reset_config
from app.providers.registry import reset_provider_registry
from app.redis_client import reset_redis, set_redis
from app.routing import circuit_breaker


@pytest.fixture(autouse=True)
def fake_redis():
    """Swap the Redis singleton for a fresh in-memory fake before every test."""
    reset_config()
    reset_provider_registry()
    circuit_breaker.reset_circuits()
    client = FakeRedis(decode_responses=True)
    set_redis(client)
    yield client
    reset_redis()
    reset_provider_registry()
