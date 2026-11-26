import redis
from app.config import settings


def get_redis_client() -> redis.Redis:
    return redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1.0,
        socket_timeout=1.0,
    )


class RedisProxy:
    """Proxy lazy-connect để không lỗi khi import nếu Redis chưa sẵn sàng."""
    def __getattr__(self, name):
        client = get_redis_client()
        return getattr(client, name)


r = RedisProxy()


def redis_healthy() -> bool:
    try:
        client = get_redis_client()
        return bool(client.ping())
    except Exception:
        return False
