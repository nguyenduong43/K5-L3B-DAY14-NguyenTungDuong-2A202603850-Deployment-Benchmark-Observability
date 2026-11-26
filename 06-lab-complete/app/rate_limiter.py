import time
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r


def check_rate_limit(key: str) -> None:
    now = time.time()
    window = 60.0
    limit = settings.rate_limit_per_minute
    redis_key = f"ratelimit:{key}"

    try:
        # Xóa các request cũ ngoài window 60s
        r.zremrangebyscore(redis_key, 0, now - window)
        count = r.zcard(redis_key)

        if count >= limit:
            oldest = r.zrange(redis_key, 0, 0, withscores=True)
            retry_after = int(oldest[0][1] + window - now) + 1 if oldest else int(window)
            if retry_after <= 0:
                retry_after = 1
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )

        pipe = r.pipeline()
        pipe.zadd(redis_key, {f"{now}:{count}": now})
        pipe.expire(redis_key, int(window) + 10)
        pipe.execute()
    except HTTPException:
        raise
    except Exception:
        pass
