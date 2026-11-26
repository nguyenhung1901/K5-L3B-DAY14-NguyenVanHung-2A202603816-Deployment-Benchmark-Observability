"""Redis-based daily LLM budget with atomic reservation and settlement."""
import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_UP

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = Decimal('0.00015')
PRICE_OUTPUT_PER_1K = Decimal('0.0006')
_NANO_USD = Decimal('1000000000')
# Mock replies are shorter than 512 characters. Reserve an output allowance
# before calling the mock LLM, then settle the difference afterward.
_OUTPUT_ALLOWANCE_TOKENS = 128

_RESERVE_SCRIPT = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local amount = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
if current + amount > limit then
    return 0
end
redis.call('INCRBY', KEYS[1], amount)
redis.call('EXPIREAT', KEYS[1], tonumber(ARGV[3]))
return 1
"""


def _daily_key(api_key: str) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    tomorrow = now.date() + timedelta(days=1)
    next_midnight = datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc)
    fingerprint = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
    return f"day14:budget:{fingerprint}:{now:%Y-%m-%d}", int(next_midnight.timestamp())


def _as_nano_usd(amount: Decimal) -> int:
    return int((amount * _NANO_USD).to_integral_value(rounding=ROUND_UP))


def _cost_nano(input_tokens: int, output_tokens: int) -> int:
    cost = ((PRICE_INPUT_PER_1K * max(input_tokens, 0))
            + (PRICE_OUTPUT_PER_1K * max(output_tokens, 0))) / 1000
    return _as_nano_usd(cost)


def check_budget(api_key: str, question: str) -> tuple[str, int]:
    """Atomically reserve estimated cost; return (day_key, reserved_nano)."""
    key, expires_at = _daily_key(api_key)
    input_estimate = max(1, (len(question) + 3) // 4)
    reserved = _cost_nano(input_estimate, _OUTPUT_ALLOWANCE_TOKENS)
    limit = _as_nano_usd(Decimal(str(settings.daily_budget_usd)))
    try:
        permitted = r.eval(_RESERVE_SCRIPT, 1, key, reserved, limit, expires_at)
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Cost accounting unavailable") from exc
    if not permitted:
        raise HTTPException(status_code=402, detail="Daily budget exceeded")
    return key, reserved


def record_cost(budget_key: str, input_tokens: int, output_tokens: int,
                reserved_nano: int) -> float:
    """Settle the reservation to the measured cost of this mock response."""
    actual_nano = _cost_nano(input_tokens, output_tokens)
    try:
        r.incrby(budget_key, actual_nano - reserved_nano)
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Cost accounting unavailable") from exc
    return actual_nano / 1_000_000_000


def release_budget(budget_key: str, reserved_nano: int) -> None:
    """Refund a reservation when the model call fails."""
    try:
        r.incrby(budget_key, -reserved_nano)
    except redis.RedisError:
        # Preserve the original LLM failure; log/accounting reconciliation
        # would be required for real billing systems.
        pass
