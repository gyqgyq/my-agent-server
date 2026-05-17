import asyncio

import httpx
from fastapi import HTTPException, status
from openai import APIConnectionError, APITimeoutError, APIStatusError


def map_embedding_error(exc: BaseException) -> HTTPException:
    """将向量化/网络错误映射为合适的 HTTP 响应。"""
    if isinstance(exc, asyncio.TimeoutError):
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="向量化超时，请缩小文件或稍后重试",
        )
    if isinstance(exc, httpx.TimeoutException):
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="连接火山方舟 Embedding 超时，请稍后重试",
        )
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="无法连接火山方舟 Embedding 服务，请检查网络与 RAG_EMBEDDING_BASE_URL",
        )
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code == 400:
            return HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Embedding 请求参数无效，请检查 RAG_EMBEDDING_MODEL、"
                    "RAG_EMBEDDING_DIMENSIONS 是否与 Doubao-embedding-vision 接入点一致"
                ),
            )
        if exc.response.status_code >= 500:
            return HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Embedding 服务端错误",
            )
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Embedding 服务不可用。"
                "请检查 ARK_API_KEY、RAG_EMBEDDING_BASE_URL、RAG_EMBEDDING_MODEL"
            ),
        )
    if isinstance(exc, APIStatusError) and exc.status_code == 400:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Embedding 请求参数无效，请检查 RAG_EMBEDDING_MODEL、"
                "RAG_EMBEDDING_DIMENSIONS 是否与方舟接入点一致"
            ),
        )
    if isinstance(exc, APIStatusError) and exc.status_code >= 500:
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Embedding 服务端错误",
        )
    msg = str(exc).lower()
    if "timeout" in msg or "10060" in msg or "connect" in msg:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding 服务网络异常，请检查 ARK_API_KEY 与方舟接入配置",
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="文档向量化失败",
    )
