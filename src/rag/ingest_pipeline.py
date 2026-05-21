from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence

from langchain_core.documents import Document as LCDocument

from src.rag import ingest, vectorstore

logger = logging.getLogger(__name__)


def iter_chunk_batches(
    chunks: Sequence[tuple[str, str | None]],
    batch_size: int,
) -> Iterator[tuple[int, list[tuple[str, str | None]]]]:
    for start in range(0, len(chunks), batch_size):
        yield start, list(chunks[start : start + batch_size])


def ingest_batch_sync(
    batch: list[tuple[str, str | None]],
    *,
    batch_start: int,
    user_id: int,
    work_id: int,
    document_id: int,
    filename: str,
) -> int:
    lc_docs = ingest.build_langchain_documents(
        batch,
        user_id=user_id,
        work_id=work_id,
        document_id=document_id,
        filename=filename,
        chunk_index_offset=batch_start,
    )
    ids = [
        vectorstore.chunk_vector_id(user_id, work_id, document_id, batch_start + i)
        for i in range(len(batch))
    ]
    vectorstore.add_langchain_documents(lc_docs, ids=ids)
    return len(batch)


def ingest_all_chunks_sync(
    chunks: list[tuple[str, str | None]],
    *,
    user_id: int,
    work_id: int,
    document_id: int,
    filename: str,
    batch_size: int,
) -> int:
    total = 0
    for batch_start, batch in iter_chunk_batches(chunks, batch_size):
        n = ingest_batch_sync(
            batch,
            batch_start=batch_start,
            user_id=user_id,
            work_id=work_id,
            document_id=document_id,
            filename=filename,
        )
        total += n
        logger.info(
            "ingest_batch_done",
            extra={
                "document_id": document_id,
                "work_id": work_id,
                "batch_start": batch_start,
                "batch_size": n,
                "chunk_total_so_far": total,
            },
        )
    return total
