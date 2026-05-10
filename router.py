from fastapi import APIRouter

from test import router as test_router

routers = APIRouter()

routers.include_router(test_router, prefix="/test", tags=["测试"])