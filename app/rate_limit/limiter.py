import time
from dataclasses import dataclass

from app.models.team import TeamConfig
from app.redis_client import get_redis

# KEYS[1] = bucket hash key
# ARGV[1] = refill rate (tokens/sec), ARGV[2] = capacity, ARGV[3] = now (epoch seconds, float)
# Returns {allowed (0/1), tokens_remaining (int), retry_after_seconds (int)}
_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])

if tokens == nil then
    tokens = capacity
    ts = now
end

local elapsed = math.max(0, now - ts)
tokens = math.min(capacity, tokens + elapsed * rate)

local allowed = 0
local retry_after = 0

if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
else
    retry_after = math.ceil((1 - tokens) / rate)
end

redis.call('HSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, math.ceil(capacity / rate) * 2)

return {allowed, math.floor(tokens), retry_after}
"""


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


async def check_rate_limit(team: TeamConfig) -> RateLimitResult:
    """Consume one request token from the team's rpm bucket."""
    capacity = team.rate_limits.requests_per_minute
    rate = capacity / 60.0
    key = f"rate:{team.team_id}:rpm"

    redis_client = get_redis()
    allowed, remaining, retry_after = await redis_client.eval(
        _TOKEN_BUCKET_LUA, 1, key, rate, capacity, time.time()
    )
    return RateLimitResult(
        allowed=bool(allowed),
        remaining=int(remaining),
        retry_after_seconds=int(retry_after),
    )


async def record_tokens(team: TeamConfig, total_tokens: int) -> None:
    """Track tokens consumed in the current minute window (visibility only, not enforced)."""
    minute_bucket = time.strftime("%Y%m%d%H%M", time.gmtime())
    key = f"rate:{team.team_id}:tpm:{minute_bucket}"

    redis_client = get_redis()
    await redis_client.incrby(key, total_tokens)
    await redis_client.expire(key, 120)


async def get_tokens_this_minute(team_id: str) -> int:
    minute_bucket = time.strftime("%Y%m%d%H%M", time.gmtime())
    key = f"rate:{team_id}:tpm:{minute_bucket}"
    redis_client = get_redis()
    value = await redis_client.get(key)
    return int(value) if value is not None else 0
