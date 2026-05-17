"""向量检索路由（无 DB、无 embedding）。"""

from unittest.mock import MagicMock, patch

from src.rag import vectorstore


def test_similarity_search_uses_similarity_by_default(monkeypatch) -> None:
    from src.core import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "RAG_SEARCH_TYPE", "similarity")
    store = MagicMock()
    store.similarity_search.return_value = []
    with patch.object(vectorstore, "get_vectorstore", return_value=store):
        vectorstore.similarity_search("q", k=3, user_id=1, work_id=2)
    store.similarity_search.assert_called_once_with(
        "q", k=3, filter={"user_id": 1, "work_id": 2}
    )
    store.max_marginal_relevance_search.assert_not_called()


def test_similarity_search_uses_mmr_when_configured(monkeypatch) -> None:
    from src.core import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "RAG_SEARCH_TYPE", "mmr")
    monkeypatch.setattr(settings_mod.settings, "RAG_MMR_FETCH_K", 15)
    monkeypatch.setattr(settings_mod.settings, "RAG_MMR_LAMBDA_MULT", 0.4)
    store = MagicMock()
    store.max_marginal_relevance_search.return_value = []
    with patch.object(vectorstore, "get_vectorstore", return_value=store):
        vectorstore.similarity_search("q", k=3, user_id=1, work_id=2)
    store.max_marginal_relevance_search.assert_called_once_with(
        "q",
        k=3,
        fetch_k=15,
        lambda_mult=0.4,
        filter={"user_id": 1, "work_id": 2},
    )
