import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.core.settings import settings

# 中文长文：在段落/句号/逗号处优先切分，减少句中硬断
_TEXT_SPLIT_SEPARATORS = ["\n\n", "\n", "。", "，", " ", ""]

_CHAPTER_RE = re.compile(
    r"^#+\s*(第[一二三四五六七八九十百千\d]+章[^\n]*)",
    re.MULTILINE,
)


def _guess_chapter_for_chunk(text: str, current_chapter: str | None) -> str | None:
    m = _CHAPTER_RE.search(text)
    if m:
        return m.group(1).strip()
    return current_chapter


def split_text_with_chapters(
    content: str,
    *,
    filename: str,
) -> list[tuple[str, str | None]]:
    """返回 (chunk_text, chapter) 列表。"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.RAG_CHUNK_SIZE,
        chunk_overlap=settings.RAG_CHUNK_OVERLAP,
        separators=_TEXT_SPLIT_SEPARATORS,
    )
    raw_chunks = splitter.split_text(content)
    if not raw_chunks:
        return []

    is_markdown = Path(filename).suffix.lower() == ".md"
    if not is_markdown:
        return [(c, None) for c in raw_chunks]

    result: list[tuple[str, str | None]] = []
    chapter: str | None = None
    for chunk in raw_chunks:
        chapter = _guess_chapter_for_chunk(chunk, chapter)
        result.append((chunk, chapter))
    return result


def build_langchain_documents(
    chunks: list[tuple[str, str | None]],
    *,
    user_id: int,
    work_id: int,
    document_id: int,
    filename: str,
) -> list[Document]:
    docs: list[Document] = []
    for i, (text, chapter) in enumerate(chunks):
        meta: dict = {
            "user_id": user_id,
            "work_id": work_id,
            "document_id": document_id,
            "source": filename,
            "chunk_index": i,
        }
        if chapter is not None:
            meta["chapter"] = chapter
        docs.append(Document(page_content=text, metadata=meta))
    return docs
