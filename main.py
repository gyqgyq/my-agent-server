import sys
import time
from functools import lru_cache

from fastapi import FastAPI, Response, status
from fastapi import __version__ as fastapi_version

from core.settings import settings
from router import routers

app = FastAPI(
    debug=settings.DEBUG,
)
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

