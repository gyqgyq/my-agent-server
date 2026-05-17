import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.settings import settings

logger = logging.getLogger(__name__)


def _async_sqlalchemy_url(url: str) -> str:
    u = url.strip()
    if u.startswith("postgresql+psycopg_async://"):
        return u
    if u.startswith("postgresql://"):
        return u.replace("postgresql://", "postgresql+psycopg_async://", 1)
    return u


engine = create_async_engine(
    _async_sqlalchemy_url(settings.ASYNC_DATABASE_URL),
    pool_pre_ping=True,
)

_url = make_url(settings.ASYNC_DATABASE_URL)
logger.info(
    "postgres_engine_initialized",
    extra={
        "host": _url.host,
        "port": _url.port,
        "database": _url.database,
    },
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def ensure_pgvector_extension() -> None:
    """确认 pgvector 已安装（需 DBA 先执行 migrations/001_pgvector.sql）。"""
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
        ).first()
    if row is None:
        raise RuntimeError(
            "PostgreSQL 未启用 pgvector 扩展。"
            "请由具备权限的角色执行 migrations/001_pgvector.sql"
        )
    logger.info("pgvector_extension_ok")


async def postgres_connect() -> None:
    """启动时建连并执行 SELECT 1，成功打 postgres_connected 日志。"""
    try:
        async with engine.connect() as conn:
            one = (await conn.execute(text("SELECT 1"))).scalar_one()
    except Exception:
        logger.exception(
            "postgres_connection_failed",
            extra={
                "host": _url.host,
                "port": _url.port,
                "database": _url.database,
            },
        )
        raise
    logger.info(
        "postgres_connected",
        extra={
            "scalar_one": repr(one),
            "host": _url.host,
            "port": _url.port,
            "database": _url.database,
        },
    )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
