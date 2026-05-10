from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from core.settings import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

security = HTTPBearer(auto_error=False)


class AuthTokenError(Exception):
    """JWT 校验失败（过期或无效）。"""


class AuthTokenExpired(AuthTokenError):
    """访问令牌已过期。"""


class AuthTokenInvalid(AuthTokenError):
    """访问令牌无效或载荷不符合约定。"""


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_token(
    user_id: int,
    *,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """签发访问令牌。默认有效期为 ACCESS_TOKEN_EXPIRE_MINUTES。"""
    expire = _now_utc() + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "user_id": user_id,
        "iat": _now_utc(),
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """解码并校验签名与 exp；失败时抛出 jwt 异常。"""
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[ALGORITHM],
    )


def verify_token(token: str) -> int:
    """
    校验令牌并返回 user_id。
    抛出 AuthTokenExpired / AuthTokenInvalid，便于在非 FastAPI 上下文中处理。
    """
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError as exc:
        raise AuthTokenExpired("访问令牌已过期") from exc
    except InvalidTokenError as exc:
        raise AuthTokenInvalid("访问令牌无效") from exc

    user_id = payload.get("user_id")
    if not isinstance(user_id, int):
        raise AuthTokenInvalid("令牌中缺少有效的 user_id")

    return user_id


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_id(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(security),
    ],
) -> int:
    """从 Authorization: Bearer 中解析并校验 JWT，返回 user_id。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("未提供有效的 Bearer 令牌")

    try:
        return verify_token(credentials.credentials)
    except AuthTokenExpired:
        raise _unauthorized("令牌已过期") from None
    except AuthTokenInvalid:
        raise _unauthorized("令牌无效") from None


async def get_current_user_id_optional(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(security),
    ],
) -> int | None:
    """同上，但未携带令牌时返回 None，不抛 401。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    try:
        return verify_token(credentials.credentials)
    except AuthTokenError:
        return None
