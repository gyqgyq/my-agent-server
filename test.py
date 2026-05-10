from typing import Annotated

from fastapi import APIRouter, Depends

from auth import create_token, get_current_user_id

router = APIRouter()

@router.get("/send_token")
async def send_token():
    data = {
        "user_id": 1,
    }
    token = create_token(data["user_id"])
    return {"data": token}



@router.get("/get_user_id")
async def get_token(user_id: Annotated[int, Depends(get_current_user_id)]):
    """需在请求头携带 `Authorization: Bearer <JWT>`；过期或无效时返回 401，而不是 500。"""
    return {"data": user_id}
