from fastapi import APIRouter

from core.settings import settings
from test import router as test_router

routers = APIRouter(prefix=settings.API_PREFIX)
routers.include_router(test_router)