import pytest
from fakeredis.aioredis import FakeRedis

from app.config.loader import reset_config
from app.redis_client import reset_redis, set_redis


@pytest.fixture(autouse=True)
def fake_redis():
    """Swap the Redis singleton for a fresh in-memory fake before every test."""
    reset_config()
    client = FakeRedis(decode_responses=True)
    set_redis(client)
    yield client
    reset_redis()
