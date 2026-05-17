from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

import httpx
from langchain_core.embeddings import Embeddings

from src.core.settings import settings


def resolve_embedding_base_url() -> str:
    """去掉误配的 /process 后缀，得到方舟 API 根路径（如 .../api/v3）。"""
    base = settings.RAG_EMBEDDING_BASE_URL.rstrip("/")
    if base.endswith("/process"):
        return base[: -len("/process")]
    return base


def resolve_multimodal_embedding_url() -> str:
    """Doubao-embedding-vision：POST {base}/embeddings/multimodal。"""
    return f"{resolve_embedding_base_url()}/embeddings/multimodal"


class ArkMultimodalEmbeddings(Embeddings):
    """火山方舟 Doubao-embedding-vision（/embeddings/multimodal，纯文本 RAG 用 type=text）。"""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        api_url: str,
        dimensions: int,
        timeout: float = 60.0,
        max_concurrency: int = 8,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self.dimensions = dimensions
        self._timeout = timeout
        self._max_concurrency = max(1, max_concurrency)
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._api_url = api_url

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if len(texts) == 1:
            return [self._embed_text(texts[0])]
        workers = min(self._max_concurrency, len(texts))
        out: list[list[float] | None] = [None] * len(texts)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self._embed_text, text): i
                for i, text in enumerate(texts)
            }
            for fut in as_completed(futures):
                idx = futures[fut]
                out[idx] = fut.result()
        return [e for e in out if e is not None]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_text(text)

    def _embed_text(self, text: str) -> list[float]:
        body: dict = {
            "model": self.model,
            "input": [{"type": "text", "text": text}],
            "encoding_format": "float",
        }
        if self.dimensions:
            body["dimensions"] = self.dimensions
        resp = self._client.post(
            self._api_url,
            headers=self._headers,
            json=body,
        )
        resp.raise_for_status()
        return _parse_multimodal_embedding(resp.json())

    def __del__(self) -> None:
        if getattr(self, "_owns_client", False) and hasattr(self, "_client"):
            self._client.close()


def _parse_multimodal_embedding(payload: dict) -> list[float]:
    data = payload.get("data")
    if isinstance(data, dict) and "embedding" in data:
        return list(data["embedding"])
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and "embedding" in first:
            return list(first["embedding"])
    raise ValueError("方舟 multimodal embedding 响应缺少 data.embedding")


@lru_cache(maxsize=1)
def get_embeddings() -> ArkMultimodalEmbeddings:
    return ArkMultimodalEmbeddings(
        model=settings.RAG_EMBEDDING_MODEL,
        api_key=settings.ARK_API_KEY,
        api_url=resolve_multimodal_embedding_url(),
        dimensions=settings.RAG_EMBEDDING_DIMENSIONS,
        timeout=60.0,
        max_concurrency=settings.RAG_EMBEDDING_MAX_CONCURRENCY,
    )
