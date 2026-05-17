from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from src.core.settings import settings


def resolve_embedding_base_url() -> str:
    """去掉误配的 /process 后缀，保证请求 {base}/embeddings。"""
    base = settings.RAG_EMBEDDING_BASE_URL.rstrip("/")
    if base.endswith("/process"):
        return base[: -len("/process")]
    return base


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    """火山 Doubao-embedding（OpenAI 兼容 POST {base}/embeddings）。"""
    return OpenAIEmbeddings(
        model=settings.RAG_EMBEDDING_MODEL,
        openai_api_key=settings.ARK_API_KEY,
        openai_api_base=resolve_embedding_base_url(),
        dimensions=settings.RAG_EMBEDDING_DIMENSIONS,
    )