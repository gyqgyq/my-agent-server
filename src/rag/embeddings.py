from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from src.core.settings import settings




@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    """火山 Doubao-embedding（OpenAI 兼容 POST {base}/embeddings）。"""
    return OpenAIEmbeddings(
        model=settings.RAG_EMBEDDING_MODEL,
        openai_api_key=settings.ARK_API_KEY,
        openai_api_base=settings.RAG_EMBEDDING_BASE_URL,
        dimensions=settings.RAG_EMBEDDING_DIMENSIONS,
    )
