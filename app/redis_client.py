import redis.asyncio as redis

from app.config.loader import get_redis_url

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(get_redis_url(), decode_responses=True)
    return _client


def set_redis(client: redis.Redis) -> None:
    """Override the singleton client. Used by tests to inject a fake client."""
    global _client
    _client = client


def reset_redis() -> None:
    """Clear the singleton so the next get_redis() call re-reads REDIS_URL."""
    global _client
    _client = None
