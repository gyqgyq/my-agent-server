import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi import __version__ as fastapi_version
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.core.logging_config import setup_logging
from src.core.settings import settings
from src.core.middleware import my_middleware
from src.api.v1.routers import routers
from src.db.postgres import engine, postgres_connect
from src.db.redis import redis_connect

logger = logging.getLogger(__name__)

_hello_payload: dict[str, str] | None = None
_hello_init_lock = asyncio.Lock()


class HelloResponse(BaseModel):
    message: str


class ServerStatusResponse(BaseModel):
    """供运维探活；字段名与历史 JSON 保持一致（连字符）。"""

    server_status: str = Field(serialization_alias="server-status")
    fastapi_version: str = Field(serialization_alias="fastapi-version")
    python_version: str = Field(serialization_alias="python-version")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings)
    await postgres_connect()
    app.state.redis = await redis_connect()
    yield
    await engine.dispose()
    r = app.state.redis
    if r is not None:
        await r.aclose()


app = FastAPI(
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)
my_middleware(app)

_origins = settings.parsed_cors_origins()
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(routers)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", extra={"path": request.url.path})
    if settings.DEBUG:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc), "type": type(exc).__name__},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "内部服务器错误"},
    )


@app.get("/server-status", include_in_schema=False)
def server_status(
    token: Annotated[str | None, Query()] = None,
) -> ServerStatusResponse:
    expected = (settings.SERVER_STATUS_TOKEN or "").strip()
    if not expected or token != expected:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    return ServerStatusResponse(
        server_status="程序正常运行",
        fastapi_version=fastapi_version,
        python_version=sys.version,
    )


@app.get("/")
async def root() -> HelloResponse:
    """首页演示：首次请求异步等待 5 秒（不阻塞事件循环），后续命中内存缓存。"""
    global _hello_payload
    async with _hello_init_lock:
        if _hello_payload is None:
            await asyncio.sleep(5)
            _hello_payload = {"message": "Hello World"}
    return HelloResponse.model_validate(_hello_payload)
