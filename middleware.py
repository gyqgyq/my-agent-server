import asyncio
import logging
import time
from typing import Any

from fastapi import FastAPI, Request
from redis.exceptions import RedisError

from database.redis_keys import rate_limit_last_seen_key
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

access_logger = logging.getLogger("app.access")
rate_limit_logger = logging.getLogger("app.rate_limit")


def _rate_limit_client_key(request: Request) -> str:
    """在反向代理后优先使用 X-Forwarded-For 的第一个地址（需上游网关剥离不可信链）。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        part = forwarded.split(",")[0].strip()
        if part:
            return part
    if request.client is not None:
        return request.client.host
    return "unknown"


# 原子：读上次时间 → 未过间隔则拒绝；否则 SET 时间戳并 EX（空闲键自动过期）
_RL_LAST_SEEN_LUA = """
local last = redis.call('GET', KEYS[1])
local time = redis.call('TIME')
local now = tonumber(time[1]) + tonumber(time[2])/1000000
local min_iv = tonumber(ARGV[2])
local ex = tonumber(ARGV[3])
if last then
  last = tonumber(last)
  local elapsed = now - last
  if elapsed < min_iv then
    local retry = math.floor(min_iv - elapsed) + 1
    if retry < 1 then retry = 1 end
    return {0, retry}
  end
end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ex)
return {1, 0}
"""


class RateLimitMiddleware(BaseHTTPMiddleware):
    """最小间隔限流：有 Redis 时多 worker/多副本一致；无 Redis 时退化为进程内字典。"""

    def __init__(
        self,
        app: ASGIApp,
        *,
        min_interval_seconds: float = 1.0,
        max_tracked_clients: int = 50000,
        stale_after_seconds: float | None = None,
        included_paths: frozenset[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._min_interval = min_interval_seconds
        self._max_tracked = max_tracked_clients
        self._stale_after = stale_after_seconds or max(min_interval_seconds * 10.0, 60.0)
        self._included_paths = included_paths or frozenset()
        self._last_seen: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._ops_since_cleanup = 0
        self._redis_script: Any = None

    def _evict_if_needed(self, now: float) -> None:
        threshold = now - self._stale_after
        stale = [k for k, t in self._last_seen.items() if t < threshold]
        for k in stale:
            del self._last_seen[k]
        while len(self._last_seen) > self._max_tracked:
            self._last_seen.pop(next(iter(self._last_seen)))

    async def _redis_allow(self, r: Any, client_key: str, now: float) -> tuple[bool, int]:
        if self._redis_script is None:
            self._redis_script = r.register_script(_RL_LAST_SEEN_LUA)
        ex = max(int(self._stale_after), 1)
        raw = await self._redis_script(
            keys=[rate_limit_last_seen_key(client_key)],
            args=[str(now), str(self._min_interval), str(ex)],
        )
        allowed, retry_after = int(raw[0]), int(raw[1])
        return allowed == 1, retry_after

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path not in self._included_paths:
            return await call_next(request)

        client_key = _rate_limit_client_key(request)
        now = time.time()
        r = getattr(request.app.state, "redis", None)

        if r is not None:
            try:
                ok, retry_after = await self._redis_allow(r, client_key, now)
            except RedisError as e:
                rate_limit_logger.warning(
                    "rate_limit_redis_error",
                    extra={"error": str(e), "client_key": client_key},
                )
                ok, retry_after = True, 0
            if not ok:
                rate_limit_logger.warning(
                    "rate_limit_exceeded",
                    extra={
                        "client_key": client_key,
                        "path": request.url.path,
                        "method": request.method,
                    },
                )
                return JSONResponse(
                    status_code=429,
                    content={"detail": "超过访问限制"},
                    headers={"Retry-After": str(retry_after)},
                )
            return await call_next(request)

        async with self._lock:
            self._ops_since_cleanup += 1
            if self._ops_since_cleanup >= 256 or len(self._last_seen) > self._max_tracked:
                self._ops_since_cleanup = 0
                self._evict_if_needed(now)

            last = self._last_seen.get(client_key, 0.0)
            elapsed = now - last
            if elapsed < self._min_interval:
                retry_after = max(1, int(self._min_interval - elapsed) + 1)
                rate_limit_logger.warning(
                    "rate_limit_exceeded",
                    extra={
                        "client_key": client_key,
                        "path": request.url.path,
                        "method": request.method,
                    },
                )
                return JSONResponse(
                    status_code=429,
                    content={"detail": "超过访问限制"},
                    headers={"Retry-After": str(retry_after)},
                )

            self._last_seen[client_key] = now

        return await call_next(request)

def my_middleware(app: FastAPI) -> None:
    """访问日志：仅 path，不打 query（避免 token 出现在 URL）。"""

    @app.middleware("http")
    async def access_log_middleware(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        client = request.client
        extra: dict[str, Any] = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }
        if client is not None:
            extra["client_ip"] = client.host
        msg = "http_request"
        if response.status_code >= 500:
            access_logger.error(msg, extra=extra)
        else:
            access_logger.info(msg, extra=extra)
        return response

    app.add_middleware(
        RateLimitMiddleware,
        min_interval_seconds=1.0,
        max_tracked_clients=50000,
        included_paths=frozenset({"/", "/api/test/send_token"}),
    )









