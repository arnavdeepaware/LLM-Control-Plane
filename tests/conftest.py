import pytest
from fakeredis.aioredis import FakeRedis

from app.config.loader import reset_config
from app.redis_client import reset_redis, set_redis
from app.routing import circuit_breaker
from app.routing.router import _provider_registry


@pytest.fixture(autouse=True)
def fake_redis():
    """Swap the Redis singleton for a fresh in-memory fake before every test."""
    reset_config()
    circuit_breaker.reset_circuits()
    _provider_registry["mock"].clear_failures()
    client = FakeRedis(decode_responses=True)
    set_redis(client)
    yield client
    reset_redis()
