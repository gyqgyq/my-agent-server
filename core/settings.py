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
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DEBUG: bool

    # -------------------
    # 3. 数据库配置（从 .env 读取）
    # -------------------
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    REDIS_PASSWORD: str
    # 连接阶段超时（秒），便于尽快失败而不是长时间挂起
    REDIS_SOCKET_CONNECT_TIMEOUT: float = 5.0
    # 空闲连接超过该秒数后，下次使用前先 PING，避免远端/NAT 已掐断的半开连接导致 10054
    REDIS_HEALTH_CHECK_INTERVAL: float = 30.0
    # TCP keepalive，减轻长空闲被中间设备回收的概率
    REDIS_SOCKET_KEEPALIVE: bool = True
    # True：Ping 失败时不阻断启动，app.state.redis 为 None（仅适合本地/非 Redis 关键路径）
    REDIS_OPTIONAL: bool = False

    # 日志（LOG_FORMAT=json 适合生产采集；本地默认 text）
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "text"


    class Config:
        env_file = (".env")  # 自动读 .env 文件
        # env_file = (".env", ".env.prod")  # 自动读 .env 文件

        
@lru_cache()
def get_settings():
    return Settings()

# 全局唯一实例
settings = get_settings()