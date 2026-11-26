"""Redis client shared by readiness, rate limiting and cost guard."""
import redis

from app.config import settings

# Do not connect or ping during module import: /health must work without Redis.
r = redis.Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=0.5,
    socket_timeout=0.5,
)


def redis_healthy() -> bool:
    try:
        return bool(r.ping())
    except redis.RedisError:
        return False
