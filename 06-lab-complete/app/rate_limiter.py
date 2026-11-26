"""Atomic sliding-window rate limiter shared across all workers via Redis."""
import hashlib
import uuid

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

_WINDOW_MS = 60_000
_RATE_SCRIPT = """
local ts = redis.call('TIME')
local now_ms = tonumber(ts[1]) * 1000 + math.floor(tonumber(ts[2]) / 1000)
local window_ms = tonumber(ARGV[1])
local max_requests = tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now_ms - window_ms)
local count = redis.call('ZCARD', KEYS[1])
if count >= max_requests then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    local retry = math.max(1, math.ceil((tonumber(oldest[2]) + window_ms - now_ms) / 1000))
    return {0, retry}
end
redis.call('ZADD', KEYS[1], now_ms, ARGV[3])
redis.call('PEXPIRE', KEYS[1], window_ms + 1000)
return {1, 0}
"""


def check_rate_limit(api_key: str) -> None:
    """Limit each API key to RATE_LIMIT_PER_MINUTE requests in 60 seconds."""
    fingerprint = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
    redis_key = f"day14:rate:{fingerprint}"
    try:
        allowed, retry_seconds = r.eval(
            _RATE_SCRIPT, 1, redis_key, _WINDOW_MS,
            max(1, settings.rate_limit_per_minute), str(uuid.uuid4()),
        )
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable") from exc
    if not int(allowed):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(int(retry_seconds))},
        )
