import asyncio
import json

import httpx
from fastapi import HTTPException, status
from openai import APIConnectionError, APITimeoutError, APIStatusError


def _ark_response_hint(exc: httpx.HTTPStatusError) -> str:
    """从方舟错误响应体提取简短说明（若有）。"""
    try:
        payload = exc.response.json()
    except (json.JSONDecodeError, ValueError):
        text = (exc.response.text or "").strip()
        return text[:200] if text else ""
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            msg = err.get("message") or err.get("code")
            if msg:
                return str(msg)
        if "message" in payload:
            return str(payload["message"])
    return ""


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
        code = exc.response.status_code
        hint = _ark_response_hint(exc)
        hint_suffix = f"（{hint}）" if hint else ""
        if code == 401:
            return HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "火山方舟 Embedding 鉴权失败（HTTP 401）："
                    "请检查 .env 中 ARK_API_KEY 是否正确、是否已过期"
                    f"{hint_suffix}"
                ),
            )
        if code == 403:
            return HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "火山方舟 Embedding 无权限（HTTP 403）："
                    "请确认 ARK_API_KEY 已开通 Doubao-embedding-vision，"
                    "且 RAG_EMBEDDING_MODEL 为该 Key 可用的推理接入点 ep-xxx；"
                    "勿混用其他产品线或区域的 Key"
                    f"{hint_suffix}"
                ),
            )
        if code == 429:
            return HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Embedding 请求过于频繁，请稍后重试{hint_suffix}",
            )
        if code == 400:
            return HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Embedding 请求参数无效，请检查 RAG_EMBEDDING_MODEL、"
                    "RAG_EMBEDDING_DIMENSIONS 是否与 Doubao-embedding-vision 接入点一致"
                    f"{hint_suffix}"
                ),
            )
        if code >= 500:
            return HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Embedding 服务端错误{hint_suffix}",
            )
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Embedding 服务不可用。"
                "请检查 ARK_API_KEY、RAG_EMBEDDING_BASE_URL、RAG_EMBEDDING_MODEL"
            ),
        )
    if isinstance(exc, APIStatusError) and exc.status_code in (401, 403):
        label = "401" if exc.status_code == 401 else "403"
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"火山方舟 Embedding 鉴权/权限失败（HTTP {label}）："
                "请检查 ARK_API_KEY 与 RAG_EMBEDDING_MODEL（ep-xxx）"
            ),
        )
    if isinstance(exc, APIStatusError) and exc.status_code == 429:
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Embedding 请求过于频繁，请稍后重试",
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
