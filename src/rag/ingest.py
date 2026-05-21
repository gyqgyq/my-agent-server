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
# 行首「第X章」标题（txt/md 常见）
_CHAPTER_LINE_RE = re.compile(
    r"^(?:#+\s*)?(第[一二三四五六七八九十百千\d]+章[^\n]*)",
    re.MULTILINE,
)


def _guess_chapter_for_chunk(text: str, current_chapter: str | None) -> str | None:
    m = _CHAPTER_RE.search(text)
    if m:
        return m.group(1).strip()
    return current_chapter


def _split_into_chapter_sections(content: str) -> list[tuple[str, str | None]]:
    """按章节标题切分为 (section_text, chapter_title)。"""
    matches = list(_CHAPTER_LINE_RE.finditer(content))
    if not matches:
        return [(content, None)]

    sections: list[tuple[str, str | None]] = []
    if matches[0].start() > 0:
        preamble = content[: matches[0].start()].strip()
        if preamble:
            sections.append((preamble, None))

    for i, m in enumerate(matches):
        chapter = m.group(1).strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section = content[start:end].strip()
        if section:
            sections.append((section, chapter))
    return sections


def _split_section(
    section: str,
    *,
    chapter: str | None,
    splitter: RecursiveCharacterTextSplitter,
) -> list[tuple[str, str | None]]:
    raw_chunks = splitter.split_text(section)
    if not raw_chunks:
        return []
    if chapter is None:
        result: list[tuple[str, str | None]] = []
        current: str | None = None
        for chunk in raw_chunks:
            current = _guess_chapter_for_chunk(chunk, current)
            result.append((chunk, current))
        return result
    return [(c, chapter) for c in raw_chunks]


def split_text_with_chapters(
    content: str,
    *,
    filename: str,
) -> list[tuple[str, str | None]]:
    """返回 (chunk_text, chapter) 列表；优先按章节再 RecursiveCharacter 切分。"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.RAG_CHUNK_SIZE,
        chunk_overlap=settings.RAG_CHUNK_OVERLAP,
        separators=_TEXT_SPLIT_SEPARATORS,
    )
    if not content.strip():
        return []

    sections = _split_into_chapter_sections(content)
    result: list[tuple[str, str | None]] = []
    for section_text, chapter in sections:
        result.extend(
            _split_section(section_text, chapter=chapter, splitter=splitter)
        )
    return result


def build_langchain_documents(
    chunks: list[tuple[str, str | None]],
    *,
    user_id: int,
    work_id: int,
    document_id: int,
    filename: str,
    chunk_index_offset: int = 0,
) -> list[Document]:
    docs: list[Document] = []
    for i, (text, chapter) in enumerate(chunks):
        meta: dict = {
            "user_id": user_id,
            "work_id": work_id,
            "document_id": document_id,
            "source": filename,
            "chunk_index": chunk_index_offset + i,
        }
        if chapter is not None:
            meta["chapter"] = chapter
        docs.append(Document(page_content=text, metadata=meta))
    return docs
