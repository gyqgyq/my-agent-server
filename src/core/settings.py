from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
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
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DEBUG: bool
    # 运维探活 `/server-status`：未设置或空字符串时该路由始终 404
    SERVER_STATUS_TOKEN: str | None = None
    # 逗号分隔的浏览器 Origin；空则不加 CORS 中间件（前后端同源或网关处理跨域）
    CORS_ORIGINS: str = ""
    # True：限流等逻辑优先使用 X-Forwarded-For 首段（仅当受信反向代理会剥离/覆盖该头时开启）
    TRUST_PROXY_HEADERS: bool = False

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

    # llm配置
    AGENT_CHAT_API_KEY: str
    # Agent：`init_chat_model` 的模型标识；改后需重启进程
    AGENT_CHAT_MODEL: str = "google_genai:gemini-2.5-flash"
    # 单次 SSE 流式整段 astream 的最长等待（秒），防挂死连接
    AGENT_SSE_TIMEOUT_SECONDS: float = 120.0
    # GET 查询参数上限（URL/代理长度）；长文本请用 POST /chat/stream
    AGENT_GET_MSG_MAX_CHARS: int = 2000
    # POST body message 最大字符数
    AGENT_BODY_MAX_CHARS: int = 32000

    # RAG / pgvector（火山方舟 Doubao-embedding-vision + langchain-postgres PGVector）
    ARK_API_KEY: str
    # 方舟 API 根路径（勿带 /embeddings；勿用 /process 后缀）
    # 方舟 Key: https://ark.cn-beijing.volces.com/api/v3
    RAG_EMBEDDING_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    # 推理接入点 ID 或模型名，如 ep-xxx、doubao-embedding-vision-250615
    RAG_EMBEDDING_MODEL: str
    # vision 模型支持 2048，常用降维 1024（与 PGVector 列维一致）
    RAG_EMBEDDING_DIMENSIONS: int = 1024
    # 入库时并发调用 /embeddings/multimodal 的上限
    RAG_EMBEDDING_MAX_CONCURRENCY: int = 8
    RAG_CHUNK_SIZE: int = 1000
    RAG_CHUNK_OVERLAP: int = 200
    RAG_TOP_K: int = 4
    # similarity：纯相似度；mmr：相关性与多样性平衡（见 langchain MMR）
    RAG_SEARCH_TYPE: Literal["similarity", "mmr"] = "similarity"
    RAG_MMR_FETCH_K: int = 20
    RAG_MMR_LAMBDA_MULT: float = 0.5
    RAG_MAX_UPLOAD_BYTES: int = 5_242_880
    # 文档入库（切分 + 批量 embedding 写入）在线程池中的最长等待（秒）
    RAG_INGEST_TIMEOUT_SECONDS: float = 300.0
    # 单次检索（query embedding + 向量搜索）的最长等待（秒）
    RAG_RETRIEVE_TIMEOUT_SECONDS: float = 60.0
    RAG_VECTOR_COLLECTION: str = "wensu_chunks"

    def parsed_cors_origins(self) -> list[str]:
        raw = self.CORS_ORIGINS.strip()
        if not raw:
            return []
        return [o.strip() for o in raw.split(",") if o.strip()]

    def sync_database_url(self) -> str:
        """PGVector 使用同步 psycopg 连接。"""
        u = self.ASYNC_DATABASE_URL.strip()
        if u.startswith("postgresql+psycopg_async://"):
            return u.replace(
                "postgresql+psycopg_async://",
                "postgresql+psycopg://",
                1,
            )
        if u.startswith("postgresql://"):
            return u.replace("postgresql://", "postgresql+psycopg://", 1)
        return u


@lru_cache()
def get_settings():
    return Settings()

# 全局唯一实例
settings = get_settings()