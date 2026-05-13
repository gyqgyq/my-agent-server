import logging

import bcrypt
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from account.models import User
from database.postgres import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account", tags=["账户"])


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
