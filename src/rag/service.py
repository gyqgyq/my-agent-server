import asyncio
import logging
from collections.abc import Sequence

from fastapi import HTTPException, UploadFile, status
from langchain_core.documents import Document as LCDocument
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.settings import settings
from src.rag import ingest, vectorstore
from src.rag.errors import map_embedding_error
from src.rag.models import Document, Work

logger = logging.getLogger(__name__)

_ALLOWED_SUFFIXES = {".txt", ".md"}
_ALLOWED_CONTENT_TYPES = {
    "text/plain",
    "text/markdown",
    "application/octet-stream",
}


class WorkNotFound(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="作品不存在或无权访问",
        )


async def get_work_for_user(
    session: AsyncSession,
    work_id: int,
    user_id: int,
) -> Work:
    work = await session.get(Work, work_id)
    if work is None or work.user_id != user_id:
        raise WorkNotFound()
    return work


async def create_work(session: AsyncSession, user_id: int, title: str) -> Work:
    work = Work(user_id=user_id, title=title.strip())
    session.add(work)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该标题的作品已存在",
        ) from None
    await session.refresh(work)
    return work


async def list_works(session: AsyncSession, user_id: int) -> Sequence[Work]:
    result = await session.execute(
        select(Work).where(Work.user_id == user_id).order_by(Work.id.desc())
    )
    return result.scalars().all()


async def update_work_title(
    session: AsyncSession,
    work_id: int,
    user_id: int,
    title: str,
) -> Work:
    work = await get_work_for_user(session, work_id, user_id)
    work.title = title.strip()
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该标题的作品已存在",
        ) from None
    await session.refresh(work)
    return work


def _delete_vectors_sync(ids: list[str]) -> None:
    vectorstore.delete_vectors_by_ids(ids)


async def _delete_document_vectors(
    user_id: int,
    work_id: int,
    document_id: int,
    chunk_count: int,
) -> None:
    ids = vectorstore.ids_for_document(
        user_id, work_id, document_id, chunk_count
    )
    await asyncio.to_thread(_delete_vectors_sync, ids)


async def delete_work(
    session: AsyncSession,
    work_id: int,
    user_id: int,
) -> None:
    result = await session.execute(
        select(Work)
        .where(Work.id == work_id, Work.user_id == user_id)
        .options(selectinload(Work.documents))
    )
    work = result.scalar_one_or_none()
    if work is None:
        raise WorkNotFound()
    all_ids: list[str] = []
    for doc in work.documents:
        if doc.chunk_count > 0:
            all_ids.extend(
                vectorstore.ids_for_document(
                    user_id, work_id, doc.id, doc.chunk_count
                )
            )
    if all_ids:
        await asyncio.to_thread(_delete_vectors_sync, all_ids)
    await session.delete(work)
    await session.commit()


async def list_documents(
    session: AsyncSession,
    work_id: int,
    user_id: int,
) -> Sequence[Document]:
    await get_work_for_user(session, work_id, user_id)
    result = await session.execute(
        select(Document)
        .where(Document.work_id == work_id)
        .order_by(Document.id.desc())
    )
    return result.scalars().all()


async def delete_document(
    session: AsyncSession,
    work_id: int,
    document_id: int,
    user_id: int,
) -> None:
    await get_work_for_user(session, work_id, user_id)
    doc = await session.get(Document, document_id)
    if doc is None or doc.work_id != work_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在",
        )
    if doc.chunk_count > 0:
        await _delete_document_vectors(user_id, work_id, document_id, doc.chunk_count)
    await session.delete(doc)
    await session.commit()


def _validate_upload(file: UploadFile, raw: bytes) -> None:
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件内容为空",
        )
    if len(raw) > settings.RAG_MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件超过 {settings.RAG_MAX_UPLOAD_BYTES} 字节上限",
        )
    name = file.filename or ""
    suffix = name[name.rfind(".") :].lower() if "." in name else ""
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 .txt 与 .md 文件",
        )
    ct = (file.content_type or "").split(";")[0].strip().lower()
    if ct and ct not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的 Content-Type",
        )


def _ingest_sync(
    lc_docs: list[LCDocument],
    *,
    user_id: int,
    work_id: int,
    document_id: int,
) -> int:
    texts = [d.page_content for d in lc_docs]
    metadatas = [d.metadata for d in lc_docs]
    ids = [
        vectorstore.chunk_vector_id(user_id, work_id, document_id, i)
        for i in range(len(lc_docs))
    ]
    vectorstore.add_document_chunks(texts=texts, metadatas=metadatas, ids=ids)
    return len(lc_docs)


async def upload_document(
    session: AsyncSession,
    work_id: int,
    user_id: int,
    file: UploadFile,
) -> Document:
    await get_work_for_user(session, work_id, user_id)
    raw = await file.read()
    _validate_upload(file, raw)

    filename = file.filename or "upload.txt"
    doc = Document(
        work_id=work_id,
        filename=filename,
        content_type=file.content_type or "text/plain",
        size_bytes=len(raw),
        status="pending",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    try:
        text = raw.decode("utf-8")
        chunks = ingest.split_text_with_chapters(text, filename=filename)
        if not chunks:
            raise ValueError("未能从文件中切分出有效文本块")

        lc_docs = ingest.build_langchain_documents(
            chunks,
            user_id=user_id,
            work_id=work_id,
            document_id=doc.id,
            filename=filename,
        )
        count = await asyncio.wait_for(
            asyncio.to_thread(
                _ingest_sync,
                lc_docs,
                user_id=user_id,
                work_id=work_id,
                document_id=doc.id,
            ),
            timeout=settings.RAG_INGEST_TIMEOUT_SECONDS,
        )
        doc.status = "done"
        doc.chunk_count = count
        doc.error_message = None
    except Exception as exc:
        logger.exception(
            "document_ingest_failed",
            extra={"work_id": work_id, "document_id": doc.id},
        )
        doc.status = "failed"
        http_exc = map_embedding_error(exc)
        doc.error_message = (
            str(exc) if settings.DEBUG else http_exc.detail
        )
        await session.commit()
        await session.refresh(doc)
        raise http_exc from exc

    await session.commit()
    await session.refresh(doc)
    return doc


def format_retrieved_chunks(docs: list[LCDocument]) -> str:
    if not docs:
        return "（无检索结果）"
    parts: list[str] = []
    for i, doc in enumerate(docs, start=1):
        chapter = doc.metadata.get("chapter") or "未知章节"
        source = doc.metadata.get("source", "")
        parts.append(
            f'"片段{i}": {{\n'
            f'        "章节": "{chapter}",\n'
            f'        "来源": "{source}",\n'
            f'        "内容": {json_escape(doc.page_content)}\n'
            f"    }}"
        )
    return "{\n    " + ",\n    ".join(parts) + "\n    }"


def json_escape(s: str) -> str:
    import json

    return json.dumps(s, ensure_ascii=False)


async def retrieve_for_user(
    session: AsyncSession,
    user_id: int,
    work_id: int,
    query: str,
) -> tuple[Work, list[LCDocument]]:
    work = await get_work_for_user(session, work_id, user_id)
    try:
        docs = await asyncio.wait_for(
            asyncio.to_thread(
                vectorstore.similarity_search,
                query,
                k=settings.RAG_TOP_K,
                user_id=user_id,
                work_id=work_id,
            ),
            timeout=settings.RAG_INGEST_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        raise map_embedding_error(exc) from exc
    return work, docs


def build_combined_system_prompt(
    work_title: str,
    user_query: str,
    retrieved_docs: list[LCDocument],
) -> str:
    from src.agent.prompt import rag_prompt, system_prompt

    chunks_block = format_retrieved_chunks(retrieved_docs)
    rag_block = rag_prompt.format(
        作品名称=work_title,
        预处理后的用户查询=user_query,
        检索片段=chunks_block,
    )
    return f"{system_prompt.strip()}\n\n{rag_block.strip()}"
