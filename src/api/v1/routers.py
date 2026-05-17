from fastapi import APIRouter

from src.account.router import router as account_router
from src.agent.router import router as agent_router
from src.rag.router import router as rag_router
from src.core.settings import settings

routers = APIRouter(prefix=settings.API_PREFIX)
if settings.DEBUG:
    from src.api.v1.endpoints.test import router as test_router

    routers.include_router(test_router)

routers.include_router(account_router)
routers.include_router(rag_router)
routers.include_router(agent_router)