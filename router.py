from fastapi import APIRouter

from account.router import router as account_router
from core.settings import settings

routers = APIRouter(prefix=settings.API_PREFIX)
if settings.DEBUG:
    from test import router as test_router

    routers.include_router(test_router)
routers.include_router(account_router)