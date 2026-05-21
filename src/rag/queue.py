from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import redis.asyncio as aioredis

from src.core.settings import settings


@dataclass(frozen=True, slots=True)
class IngestJob:
    document_id: int
    work_id: int
    user_id: int
    storage_path: str
    filename: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> IngestJob:
        data = json.loads(raw)
        return cls(
            document_id=int(data["document_id"]),
            work_id=int(data["work_id"]),
            user_id=int(data["user_id"]),
            storage_path=str(data["storage_path"]),
            filename=str(data["filename"]),
        )


async def enqueue_ingest(redis: aioredis.Redis, job: IngestJob) -> None:
    await redis.lpush(settings.RAG_INGEST_QUEUE_KEY, job.to_json())


async def dequeue_ingest(
    redis: aioredis.Redis,
    *,
    timeout_seconds: int = 2,
) -> IngestJob | None:
    result = await redis.brpop(settings.RAG_INGEST_QUEUE_KEY, timeout=timeout_seconds)
    if result is None:
        return None
    _, payload = result
    return IngestJob.from_json(payload)
