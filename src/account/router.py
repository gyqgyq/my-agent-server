import logging
import secrets
from typing import Annotated, Literal

import bcrypt
import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.account.models import User
from src.account.refresh_token_store import (
    delete_refresh,
    get_user_id_for_refresh,
    save_refresh,
)
from src.core.security import create_token
from src.core.settings import settings
from src.db.postgres import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account", tags=["账户"])

# 用户不存在时仍执行 checkpw，降低与「存在但密码错误」的时序差异
_DUMMY_PW = b"0" * 32
_DUMMY_HASH = bcrypt.hashpw(_DUMMY_PW, bcrypt.gensalt(rounds=12))

_LOGIN_FAIL = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="用户名或密码错误",
)


def require_redis(request: Request) -> redis.Redis:
    r = getattr(request.app.state, "redis", None)
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="会话存储不可用，无法完成登录或令牌刷新",
        )
    return r


RedisDep = Annotated[redis.Redis, Depends(require_redis)]


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    refresh_token: str


def _access_expires_in_seconds() -> int:
    return int(settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60)


def _refresh_ttl_seconds() -> int:
    return int(settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400)


async def _issue_token_pair(r: redis.Redis, user_id: int) -> TokenOut:
    access = create_token(user_id)
    refresh = secrets.token_urlsafe(32)
    await save_refresh(
        r,
        refresh_token=refresh,
        user_id=user_id,
        ttl_seconds=_refresh_ttl_seconds(),
    )
    return TokenOut(
        access_token=access,
        token_type="bearer",
        expires_in=_access_expires_in_seconds(),
        refresh_token=refresh,
    )


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=72)

    @field_validator("username", "password")
    @classmethod
    def strip_nonempty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("不能为空或仅空白")
        return s


class RegisterOut(BaseModel):
    id: int
    username: str


class LoginIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=72)

    @field_validator("username", "password")
    @classmethod
    def strip_nonempty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("不能为空或仅空白")
        return s


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)

    @field_validator("refresh_token")
    @classmethod
    def strip_nonempty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("不能为空或仅空白")
        return s


class LogoutIn(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)

    @field_validator("refresh_token")
    @classmethod
    def strip_nonempty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("不能为空或仅空白")
        return s


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, session: SessionDep) -> RegisterOut:
    dup = await session.scalar(
        select(User.id).where(User.username == body.username).limit(1)
    )
    if dup is not None:
        logger.info(
            "user_register_username_taken",
            extra={"username": body.username, "error": "用户名已存在"},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )

    pw_bytes = body.password.encode("utf-8")
    hashed = bcrypt.hashpw(pw_bytes, bcrypt.gensalt(rounds=12))
    user = User(
        username=body.username,
        password=hashed.decode("utf-8"),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        err_msg = str(exc.orig) if exc.orig is not None else str(exc)
        logger.info(
            "user_register_username_taken",
            extra={"username": body.username, "error": err_msg},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        ) from None
    await session.refresh(user)
    logger.info(
        "user_registered",
        extra={"user_id": user.id, "username": user.username},
    )
    return RegisterOut(id=user.id, username=user.username)


@router.post("/login")
async def login(
    body: LoginIn,
    session: SessionDep,
    r: RedisDep,
) -> TokenOut:
    user = await session.scalar(
        select(User).where(User.username == body.username).limit(1)
    )
    pw_bytes = body.password.encode("utf-8")
    if user is None:
        bcrypt.checkpw(pw_bytes, _DUMMY_HASH)
        logger.info("user_login_failed", extra={"reason": "bad_credential"})
        raise _LOGIN_FAIL from None
    if not bcrypt.checkpw(pw_bytes, user.password.encode("utf-8")):
        logger.info("user_login_failed", extra={"reason": "bad_credential"})
        raise _LOGIN_FAIL from None

    out = await _issue_token_pair(r, user.id)
    logger.info("user_login_ok", extra={"user_id": user.id})
    return out


@router.post("/refresh")
async def refresh_tokens(body: RefreshIn, r: RedisDep) -> TokenOut:
    user_id = await get_user_id_for_refresh(r, body.refresh_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌无效或已过期",
        ) from None
    await delete_refresh(r, body.refresh_token)
    out = await _issue_token_pair(r, user_id)
    logger.info("user_token_refreshed", extra={"user_id": user_id})
    return out


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutIn, r: RedisDep) -> Response:
    await delete_refresh(r, body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
