"""RAG 服务纯函数（无 DB）。"""

from langchain_core.documents import Document

from src.rag import vectorstore
from src.rag.service import build_combined_system_prompt, format_retrieved_chunks


def test_chunk_vector_id_stable() -> None:
    assert vectorstore.chunk_vector_id(1, 2, 3, 0) == "u1_w2_d3_c0"
    assert len(vectorstore.ids_for_document(1, 2, 3, 2)) == 2


def test_format_retrieved_chunks_empty() -> None:
    assert "无检索结果" in format_retrieved_chunks([])


def test_format_retrieved_chunks_with_doc() -> None:
    text = format_retrieved_chunks(
        [
            Document(
                page_content="原文",
                metadata={"chapter": "第一章", "source": "a.md"},
            )
        ]
    )
    assert "第一章" in text
    assert "原文" in text


def test_build_combined_system_prompt_includes_work_title() -> None:
    prompt = build_combined_system_prompt(
        "测试作品",
        "哈利是谁",
        [],
    )
    assert "测试作品" in prompt
    assert "哈利是谁" in prompt
    assert "文溯" in prompt
