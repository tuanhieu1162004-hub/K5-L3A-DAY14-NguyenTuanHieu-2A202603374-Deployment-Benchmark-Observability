"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, nên kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)
"""


from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import r

WINDOW_MS = 60_000

# Dùng đồng hồ Redis và thực hiện toàn bộ kiểm tra trong một thao tác.
take_slot = r.register_script("""
local time = redis.call('TIME')
local now = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)
local window = tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
local limit = tonumber(ARGV[2])
if limit <= 0 then
    return math.ceil(window / 1000)
end
if redis.call('ZCARD', KEYS[1]) >= limit then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    return math.ceil((tonumber(oldest[2]) + window - now) / 1000)
end
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('PEXPIRE', KEYS[1], window)
return 0
""")


def check_rate_limit(key: str) -> None:
    fingerprint = sha256(key.encode("utf-8")).hexdigest()
    try:
        retry_after = take_slot(
            keys=[f"agent:rate:{fingerprint}"],
            args=[WINDOW_MS, settings.rate_limit_per_minute, uuid4().hex],
        )
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable") from exc

    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
