"""Redis 业务 key 统一入口：命名约定为「域:实体:标识…」，避免魔法字符串散落。"""

from __future__ import annotations

# 认证 refresh token 存储（值为 user_id 字符串）
NS_AUTH_REFRESH = "auth:refresh"

# 全局限流「上次请求时间」
NS_RL_LAST_SEEN = "rl:last_seen"


def refresh_token_storage_key(digest_hex: str) -> str:
    """refresh_token 经 SHA-256 十六进制 digest 后的存储 key。"""
    return f"{NS_AUTH_REFRESH}:{digest_hex}"


def rate_limit_last_seen_key(client_key: str) -> str:
    """按客户端标识（如 IP）区分限流窗口的 key。"""
    return f"{NS_RL_LAST_SEEN}:{client_key}"
