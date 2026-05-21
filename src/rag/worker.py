from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.settings import settings
from src.db.postgres import SessionLocal
from src.rag import ingest_pipeline, queue, storage
from src.rag.errors import map_embedding_error
from src.rag.ingest import split_text_with_chapters
from src.rag.models import Document, Work
from src.rag.queue import IngestJob
from src.rag.service import _delete_document_vectors

logger = logging.getLogger(__name__)


def _error_message_for_doc(exc: BaseException) -> str:
    http_exc = map_embedding_error(exc)
    return str(exc) if settings.DEBUG else http_exc.detail


async def recover_pending_ingest_jobs(redis: aioredis.Redis) -> None:
    """启动时将仍为 pending 且落盘文件存在的文档重新入队。"""
    async with SessionLocal() as session:
        result = await session.execute(
            select(Document)
            .where(Document.status == "pending")
            .options(selectinload(Document.work))
        )
        docs = result.scalars().all()

    for doc in docs:
        work = doc.work
        if work is None:
            continue
        path = storage.document_storage_path(
            work.user_id, doc.work_id, doc.id, doc.filename
        )
        if not path.is_file():
            logger.warning(
                "pending_document_missing_file",
                extra={"document_id": doc.id, "path": str(path)},
            )
            continue
        job = IngestJob(
            document_id=doc.id,
            work_id=doc.work_id,
            user_id=work.user_id,
            storage_path=str(path),
            filename=doc.filename,
        )
        await queue.enqueue_ingest(redis, job)
        logger.info(
            "pending_document_requeued",
            extra={"document_id": doc.id, "work_id": doc.work_id},
        )


async def _mark_document_failed(
    document_id: int,
    error_message: str,
    *,
    chunk_count: int = 0,
) -> None:
    async with SessionLocal() as session:
        doc = await session.get(Document, document_id)
        if doc is None:
            return
        doc.status = "failed"
        doc.error_message = error_message
        doc.chunk_count = chunk_count
        await session.commit()


async def _mark_document_done(document_id: int, chunk_count: int) -> None:
    async with SessionLocal() as session:
        doc = await session.get(Document, document_id)
        if doc is None:
            return
        doc.status = "done"
        doc.chunk_count = chunk_count
        doc.error_message = None
        await session.commit()


async def process_ingest_job(job: IngestJob) -> None:
    path = Path(job.storage_path)
    written = 0
    try:
        if not path.is_file():
            raise FileNotFoundError(f"入库文件不存在: {path}")

        text = storage.read_upload_text(path)
        chunks = split_text_with_chapters(text, filename=job.filename)
        if not chunks:
            raise ValueError("未能从文件中切分出有效文本块")

        written = 0
        for batch_start, batch in ingest_pipeline.iter_chunk_batches(
            chunks, settings.RAG_INGEST_BATCH_SIZE
        ):
            n = await asyncio.wait_for(
                asyncio.to_thread(
                    ingest_pipeline.ingest_batch_sync,
                    batch,
                    batch_start=batch_start,
                    user_id=job.user_id,
                    work_id=job.work_id,
                    document_id=job.document_id,
                    filename=job.filename,
                ),
                timeout=settings.RAG_INGEST_BATCH_TIMEOUT_SECONDS,
            )
            written += n
            logger.info(
                "ingest_batch_done",
                extra={
                    "document_id": job.document_id,
                    "work_id": job.work_id,
                    "batch_start": batch_start,
                    "batch_size": n,
                    "chunk_total_so_far": written,
                },
            )
        await _mark_document_done(job.document_id, written)
        storage.delete_upload_file(path)
        logger.info(
            "document_ingest_done",
            extra={
                "document_id": job.document_id,
                "work_id": job.work_id,
                "chunk_count": written,
            },
        )
    except Exception as exc:
        logger.exception(
            "document_ingest_failed",
            extra={"document_id": job.document_id, "work_id": job.work_id},
        )
        if written > 0:
            try:
                await _delete_document_vectors(
                    job.user_id,
                    job.work_id,
                    job.document_id,
                    written,
                )
            except Exception:
                logger.exception(
                    "ingest_rollback_vectors_failed",
                    extra={"document_id": job.document_id},
                )
        await _mark_document_failed(
            job.document_id,
            _error_message_for_doc(exc),
            chunk_count=0,
        )
        storage.delete_upload_file(path)


async def _run_job_with_semaphore(
    sem: asyncio.Semaphore,
    job: IngestJob,
) -> None:
    async with sem:
        await process_ingest_job(job)


async def run_ingest_worker(
    app: FastAPI,
    shutdown: asyncio.Event,
) -> None:
    redis: aioredis.Redis | None = app.state.redis
    if redis is None:
        logger.warning("rag_ingest_worker_skipped_no_redis")
        return

    sem = asyncio.Semaphore(settings.RAG_INGEST_MAX_PARALLEL)
    logger.info("rag_ingest_worker_started")

    while not shutdown.is_set():
        try:
            job = await queue.dequeue_ingest(redis, timeout_seconds=2)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("rag_ingest_dequeue_error")
            await asyncio.sleep(1)
            continue

        if job is None:
            continue

        asyncio.create_task(_run_job_with_semaphore(sem, job))

    logger.info("rag_ingest_worker_stopped")
