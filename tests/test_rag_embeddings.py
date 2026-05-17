import httpx

from src.rag.embeddings import (
    ArkMultimodalEmbeddings,
    _parse_multimodal_embedding,
    get_embeddings,
    resolve_embedding_base_url,
    resolve_multimodal_embedding_url,
)


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


def test_resolve_multimodal_embedding_url(monkeypatch) -> None:
    from src.core import settings as settings_mod

    monkeypatch.setattr(
        settings_mod.settings,
        "RAG_EMBEDDING_BASE_URL",
        "https://ark.cn-beijing.volces.com/api/v3",
    )
    assert (
        resolve_multimodal_embedding_url()
        == "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal"
    )


def test_parse_multimodal_embedding_object_data() -> None:
    vec = _parse_multimodal_embedding({"data": {"embedding": [0.1, 0.2]}})
    assert vec == [0.1, 0.2]


def test_embed_documents_one_request_per_text() -> None:
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(
            200,
            json={"data": {"embedding": [float(len(calls)), 0.0]}},
        )

    emb = ArkMultimodalEmbeddings(
        model="ep-test",
        api_key="key",
        api_url="https://example.com/embeddings/multimodal",
        dimensions=1024,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = emb.embed_documents(["a", "b"])
    assert len(calls) == 2
    assert all(c["input"] == [{"type": "text", "text": t}] for c, t in zip(calls, ["a", "b"]))
    assert calls[0]["dimensions"] == 1024
    assert result == [[1.0, 0.0], [2.0, 0.0]]


def test_get_embeddings_returns_multimodal_client() -> None:
    get_embeddings.cache_clear()
    emb = get_embeddings()
    assert isinstance(emb, ArkMultimodalEmbeddings)
    assert emb.dimensions == 1024
