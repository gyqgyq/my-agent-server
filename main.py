import sys
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, status
from fastapi import __version__ as fastapi_version
from pydantic import BaseModel, Field

from core.logging_config import setup_logging
from core.settings import settings
from middleware import my_middleware
from router import routers


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
    yield


app = FastAPI(
    debug=settings.DEBUG,
    lifespan=lifespan,
)
my_middleware(app)
app.include_router(routers)


@lru_cache(maxsize=5)
def get_data() -> dict[str, str]:
    time.sleep(5)
    return {"message": "Hello World"}


@app.get("/server-status", include_in_schema=False)
def server_status(
    token: Annotated[str | None, Query()] = None,
) -> ServerStatusResponse:
    if token == "TTT":
        return ServerStatusResponse(
            server_status="程序正常运行",
            fastapi_version=fastapi_version,
            python_version=sys.version,
        )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


@app.get("/")
def root() -> HelloResponse:
    return HelloResponse.model_validate(get_data())

