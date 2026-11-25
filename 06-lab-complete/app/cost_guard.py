"""
Cost guard (tiêu chí 8).

Yêu cầu:
  • Cộng dồn chi phí LLM (tính theo token) vào Redis
  • Tổng chi phí vượt DAILY_BUDGET_USD (hoặc MONTHLY_BUDGET_USD) → HTTP 402
"""

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import r

# Giá theo phần tỷ USD trên mỗi token để Redis cộng chính xác bằng số nguyên.
NANO_USD_PER_INPUT_TOKEN = 150
NANO_USD_PER_OUTPUT_TOKEN = 600
NANO_USD_PER_USD = 1_000_000_000


def _daily_key() -> str:
    return f"agent:cost:{datetime.now(timezone.utc).date().isoformat()}"


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    try:
        used = int(r.get(_daily_key()) or 0)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Cost guard unavailable") from exc

    budget = Decimal(str(settings.daily_budget_usd)) * NANO_USD_PER_USD
    if used >= budget:
        raise HTTPException(status_code=402, detail="Daily budget exhausted")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = input_tokens * NANO_USD_PER_INPUT_TOKEN + output_tokens * NANO_USD_PER_OUTPUT_TOKEN
    key = _daily_key()
    try:
        with r.pipeline() as transaction:
            transaction.incrby(key, cost)
            transaction.expire(key, 172_800)
            transaction.execute()
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Cost guard unavailable") from exc
    return cost / NANO_USD_PER_USD
