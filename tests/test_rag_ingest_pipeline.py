"""RAG 分批入库工具（无 DB、无 embedding）。"""

from src.rag import ingest_pipeline


def test_iter_chunk_batches() -> None:
    chunks = [(f"c{i}", None) for i in range(5)]
    batches = list(ingest_pipeline.iter_chunk_batches(chunks, 2))
    assert len(batches) == 3
    assert batches[0][0] == 0
    assert len(batches[0][1]) == 2
    assert batches[2][0] == 4
    assert len(batches[2][1]) == 1
