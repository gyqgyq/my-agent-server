from src.rag.embeddings import resolve_embedding_base_url


def test_resolve_embedding_base_url_strips_process_suffix(
    monkeypatch,
) -> None:
    from src.core import settings as settings_mod

    monkeypatch.setattr(
        settings_mod.settings,
        "RAG_EMBEDDING_BASE_URL",
        "https://operator.las.cn-beijing.volces.com/api/v1/process",
    )
    assert (
        resolve_embedding_base_url()
        == "https://operator.las.cn-beijing.volces.com/api/v1"
    )
