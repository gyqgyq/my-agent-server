from functools import lru_cache

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from src.core.settings import settings


@lru_cache(maxsize=1)
def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model=settings.RAG_EMBEDDING_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
    )
