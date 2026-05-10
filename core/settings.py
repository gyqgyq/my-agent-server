from pydantic_settings import BaseSettings
from typing import Literal
from functools import lru_cache

class Settings(BaseSettings):
    # -------------------
    # 1. 项目常量（固定不变）
    # -------------------
    PROJECT_NAME: str = "我的FastAPI项目"
    PROJECT_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    TIME_ZONE: str = "Asia/Shanghai"
    
    # 状态常量
    STATUS_ACTIVE: Literal["active"] = "active"
    STATUS_INACTIVE: Literal["inactive"] = "inactive"

    # 分页常量
    DEFAULT_PAGE_SIZE: int = 10
    MAX_PAGE_SIZE: int = 100

    # -------------------
    # 2. 环境变量（密码、密钥、数据库，从 .env 读取）
    # -------------------
    ASYNC_DATABASE_URL: str
    SECRET_KEY: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1
    DEBUG: bool
    class Config:
        env_file = (".env", ".env.prod")  # 自动读 .env 文件

        
@lru_cache()
def get_settings():
    return Settings()

# 全局唯一实例
settings = get_settings()