import jwt
from datetime import datetime, timedelta, timezone
from core.settings import settings

def create_token(user_id: int) -> str:
    return jwt.encode(
        {
            "user_id": user_id,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.JWT_SECRET,
        algorithm="HS256",
    )

def verify_token(token: str) -> int:
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=["HS256"],
    )["user_id"]
