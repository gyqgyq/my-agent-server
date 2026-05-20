import asyncio
import json
import logging
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, field_validator

from src.core.security import CurrentUserIdDep
from src.core.settings import settings
from src.db.postgres import SessionDep
from src.agent.tools import get_weather
from src.rag import service as rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@lru_cache(maxsize=1)
def _get_agent():
    """首次请求时再建 agent；改环境变量后需重启进程使 lru_cache 失效。"""
    model = init_chat_model(
        settings.AGENT_CHAT_MODEL,
        api_key=settings.AGENT_CHAT_API_KEY,
    )
    return create_agent(
        model=model,
        tools=[get_weather],
        system_prompt="",
    )


def _to_json_safe(obj: Any) -> Any:
    """将 LangGraph chunk（含 BaseMessage）转为可 json.dumps 的结构。"""
    if isinstance(obj, BaseMessage):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_safe(v) for v in obj]
    return obj


def _sse_error_event(exc: BaseException) -> str:
    """对客户端暴露的错误文案：生产不泄露异常串。"""
    if isinstance(exc, TimeoutError):
        detail = "生成超时，请缩短输入或稍后重试"
    else:
        detail = (
            f"{type(exc).__name__}: {exc}"
            if settings.DEBUG
            else "生成失败，请稍后重试"
        )
    line = json.dumps({"event": "error", "detail": detail}, ensure_ascii=False)
    return f"data: {line}\n\n"


class AgentStreamBody(BaseModel):
    """POST 流式对话正文（推荐生产使用，避免 GET URL 长度与 query 进日志问题）。"""

    message: str = Field(..., min_length=1)
    work_id: int = Field(..., ge=1, description="当前激活作品（知识库）ID")

    @field_validator("message")
    @classmethod
    def message_ok(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("不能为空或仅空白")
        if len(s) > settings.AGENT_BODY_MAX_CHARS:
            raise ValueError(f"消息长度不能超过 {settings.AGENT_BODY_MAX_CHARS} 字符")
        return s


async def _agent_sse(
    request: Request,
    text: str,
    *,
    user_id: int,
    work_id: int,
    combined_system: str,
) -> AsyncIterator[str]:
    agent = _get_agent()
    log_extra = {
        "user_id": user_id,
        "work_id": work_id,
        "path": str(request.url.path),
    }
    logger.info("agent_sse_start", extra=log_extra)
    try:
        async with asyncio.timeout(settings.AGENT_SSE_TIMEOUT_SECONDS):
            # updates：节点结束后的整块状态（易呈现「一段话一次性」）；
            # messages：模型 token/分片流（AIMessageChunk.content 多为增量）。
            async for chunk in agent.astream(
                {
                    "messages": [
                        SystemMessage(content=combined_system),
                        HumanMessage(content=text),
                    ]
                },
                stream_mode=["messages", "updates"],
                version="v2",
            ):
                if await request.is_disconnected():
                    logger.info("agent_sse_client_disconnected", extra=log_extra)
                    break
                line = json.dumps(_to_json_safe(chunk), ensure_ascii=False)
                yield f"data: {line}\n\n"
    except TimeoutError:
        logger.warning("agent_sse_timeout", extra=log_extra)
        yield _sse_error_event(TimeoutError())
    except Exception as exc:
        logger.exception("agent_sse_failed", extra=log_extra)
        yield _sse_error_event(exc)
    finally:
        yield "data: [DONE]\n\n"
        logger.info("agent_sse_end", extra=log_extra)


@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    body: AgentStreamBody,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """SSE（POST）：JWT + JSON `{\"message\": \"...\", \"work_id\": 1}`；先 RAG 检索再生成。"""
    work, retrieved = await rag_service.retrieve_for_user(
        session, user_id, body.work_id, body.message
    )
    combined = rag_service.build_combined_system_prompt(
        work.title, body.message, retrieved
    )
    logger.info(
        "agent_rag_retrieved",
        extra={
            "user_id": user_id,
            "work_id": body.work_id,
            "retrieved_chunks": len(retrieved),
        },
    )
    return StreamingResponse(
        _agent_sse(
            request,
            body.message,
            user_id=user_id,
            work_id=body.work_id,
            combined_system=combined,
        ),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
