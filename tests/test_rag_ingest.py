"""RAG 分块与章节启发式（无 DB、无 embedding）。"""

from src.rag import ingest


def test_split_plain_txt_no_chapter() -> None:
    chunks = ingest.split_text_with_chapters("hello world " * 200, filename="a.txt")
    assert len(chunks) >= 1
    assert all(ch is None for _, ch in chunks)


def test_split_md_detects_chapter() -> None:
    text = "# 第一章 开始\n\n" + ("段落内容。" * 80) + "\n\n## 第二章\n\n" + ("更多。" * 80)
    chunks = ingest.split_text_with_chapters(text, filename="book.md")
    assert len(chunks) >= 1
    assert any(ch is not None for _, ch in chunks)


def test_build_langchain_documents_metadata() -> None:
    docs = ingest.build_langchain_documents(
        [("片段A", "第一章")],
        user_id=1,
        work_id=2,
        document_id=3,
        filename="x.md",
    )
    assert docs[0].metadata["user_id"] == 1
    assert docs[0].metadata["work_id"] == 2
    assert docs[0].metadata["document_id"] == 3
    assert docs[0].metadata["chapter"] == "第一章"


def test_build_langchain_documents_chunk_index_offset() -> None:
    docs = ingest.build_langchain_documents(
        [("A", None), ("B", None)],
        user_id=1,
        work_id=2,
        document_id=3,
        filename="a.txt",
        chunk_index_offset=10,
    )
    assert docs[0].metadata["chunk_index"] == 10
    assert docs[1].metadata["chunk_index"] == 11


def test_split_txt_chapter_first() -> None:
    text = "前言\n\n第一章 开端\n\n" + ("正文。" * 100) + "\n\n第二章 发展\n\n" + ("续。" * 100)
    chunks = ingest.split_text_with_chapters(text, filename="book.txt")
    assert len(chunks) >= 2
    chapters = {ch for _, ch in chunks if ch is not None}
    assert any("第一章" in (c or "") for c in chapters)
