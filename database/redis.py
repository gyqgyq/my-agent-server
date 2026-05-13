import logging

import redis.asyncio as redis
from redis.exceptions import ConnectionError, TimeoutError as RedisTimeoutError

from core.settings import settings

logger = logging.getLogger(__name__)

redis_pool = redis.ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD,
    encoding="utf-8",
    decode_responses=True,
    socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
    health_check_interval=settings.REDIS_HEALTH_CHECK_INTERVAL,
    socket_keepalive=settings.REDIS_SOCKET_KEEPALIVE,
    # 半开连接上首次读写失败时自动断开并重试一次（与 health_check 配合）
    retry_on_error=[ConnectionError],
)


async def redis_connect() -> redis.Redis | None:
    """建立 Redis 客户端并 Ping；REDIS_OPTIONAL 时失败返回 None 且不抛错。"""
    redis_client = redis.Redis(connection_pool=redis_pool)
    try:
        sig = await redis_client.ping()
        logger.info("redis_connected", extra={"ping": repr(sig)})
        return redis_client
    except (ConnectionError, RedisTimeoutError, OSError) as e:
        await redis_client.aclose()
        if settings.REDIS_OPTIONAL:
            logger.warning(
                "redis_unavailable_continuing",
                extra={
                    "error": str(e),
                    "host": settings.REDIS_HOST,
                    "port": settings.REDIS_PORT,
                },
            )
            return None
        logger.exception(
            "redis_connection_failed",
            extra={"host": settings.REDIS_HOST, "port": settings.REDIS_PORT},
        )
        raise
    except Exception:
        await redis_client.aclose()
        raise
