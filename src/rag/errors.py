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
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Embedding 服务不可用。"
                "请检查 ARK_API_KEY、RAG_EMBEDDING_BASE_URL、RAG_EMBEDDING_MODEL"
            ),
        )
    if isinstance(exc, APIStatusError) and exc.status_code >= 500:
        detail = "Embedding 服务端错误"
        if exc.status_code == 500 and "/process/embeddings" in str(exc.request.url):
            detail = (
                "RAG_EMBEDDING_BASE_URL 配置错误：勿使用 /process 后缀，"
                "LAS 请用 https://operator.las.cn-beijing.volces.com/api/v1"
            )
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
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
