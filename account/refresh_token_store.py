from __future__ import annotations

import hashlib

import redis.asyncio as redis

REFRESH_KEY_PREFIX = "auth:refresh:"


def refresh_redis_key(refresh_token: str) -> str:
    digest = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
    return f"{REFRESH_KEY_PREFIX}{digest}"


async def save_refresh(
    r: redis.Redis,
    *,
    refresh_token: str,
    user_id: int,
    ttl_seconds: int,
) -> None:
    await r.setex(refresh_redis_key(refresh_token), ttl_seconds, str(user_id))


async def get_user_id_for_refresh(r: redis.Redis, refresh_token: str) -> int | None:
    raw = await r.get(refresh_redis_key(refresh_token))
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


async def delete_refresh(r: redis.Redis, refresh_token: str) -> None:
    await r.delete(refresh_redis_key(refresh_token))
