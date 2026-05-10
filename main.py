import sys
import time
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI, Request, Response, status
from fastapi import __version__ as fastapi_version

from core.logging_config import setup_logging
from core.settings import settings
from middleware import my_middleware
from router import routers


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings)
    yield


app = FastAPI(
    debug=settings.DEBUG,
    lifespan=lifespan,
)
my_middleware(app)
app.include_router(routers, prefix=settings.API_PREFIX)


# 程序运行状态检查
@app.get("/server-status", include_in_schema=False)
async def server_status(response: Response, token: str | None = None):
    if token == 'TTT':
        return {
            "server-status": "程序正常运行",
            "fastapi-version": fastapi_version,
            "python-version": sys.version_info,
        }
    else:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"detail": "Not Found"}

@lru_cache(maxsize=5)
def get_data():
    time.sleep(5)
    return {"message": "Hello World"}

@app.get("/")
async def root():
    return get_data()

