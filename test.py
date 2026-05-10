from fastapi import APIRouter

from auth import CurrentUserIdDep, create_token
from pydantic import BaseModel

router = APIRouter(prefix="/test", tags=["测试"])


class TokenResponse(BaseModel):
    data: str


class UserIdResponse(BaseModel):
    data: int


@router.get("/send_token")
def send_token() -> TokenResponse:
    token = create_token(1)
    return TokenResponse(data=token)


@router.get("/get_user_id")
def get_user_id(user_id: CurrentUserIdDep) -> UserIdResponse:
    """需在请求头携带 `Authorization: Bearer <JWT>`；过期或无效时返回 401，而不是 500。"""
    return UserIdResponse(data=user_id)
