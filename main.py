import sys
import time
import hashlib
from functools import lru_cache

from fastapi import FastAPI, Query, Request, Response, status, UploadFile, File
from fastapi import __version__ as fastapi_version
from fastapi.responses import FileResponse

from core.settings import settings
# from router import routers

app = FastAPI(
    debug=settings.DEBUG,
)
# app.include_router(routers)


# @app.get("favicon.ico", include_in_schema=False)
# async def favicon():
#     return FileResponse("static/favicon.ico", media_type="image/x-icon")

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

