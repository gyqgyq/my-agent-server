import logging
import time
from typing import Any

from fastapi import FastAPI, Request

access_logger = logging.getLogger("app.access")


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
