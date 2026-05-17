from functools import lru_cache

from langchain_core.documents import Document
from langchain_postgres import PGVector

from src.core.settings import settings
from src.rag.embeddings import get_embeddings


def chunk_vector_id(
    user_id: int,
    work_id: int,
    document_id: int,
    chunk_index: int,
) -> str:
    return f"u{user_id}_w{work_id}_d{document_id}_c{chunk_index}"


def ids_for_document(
    user_id: int,
    work_id: int,
    document_id: int,
    chunk_count: int,
) -> list[str]:
    return [
        chunk_vector_id(user_id, work_id, document_id, i) for i in range(chunk_count)
    ]


def work_metadata_filter(user_id: int, work_id: int) -> dict[str, int]:
    return {"user_id": user_id, "work_id": work_id}


@lru_cache(maxsize=1)
def get_vectorstore() -> PGVector:
    return PGVector(
        embeddings=get_embeddings(),
        collection_name=settings.RAG_VECTOR_COLLECTION,
        connection=settings.sync_database_url(),
        use_jsonb=True,
        create_extension=False,
    )


def _ensure_collection(store: PGVector) -> None:
    store.create_tables_if_not_exists()
    store.create_collection()


def add_langchain_documents(
    documents: list[Document],
    *,
    ids: list[str],
) -> list[str]:
    """索引阶段：同一 embedding 模型写入 PGVector（与检索共用 get_embeddings）。"""
    store = get_vectorstore()
    _ensure_collection(store)
    return store.add_documents(documents, ids=ids)


def delete_vectors_by_ids(ids: list[str]) -> None:
    if not ids:
        return
    get_vectorstore().delete(ids=ids, collection_only=True)


def similarity_search(
    query: str,
    *,
    k: int,
    user_id: int,
    work_id: int,
) -> list[Document]:
    """按作品作用域检索；RAG_SEARCH_TYPE=mmr 时使用 MMR 降低重复片段。"""
    store = get_vectorstore()
    filt = work_metadata_filter(user_id, work_id)
    if settings.RAG_SEARCH_TYPE == "mmr":
        return store.max_marginal_relevance_search(
            query,
            k=k,
            fetch_k=settings.RAG_MMR_FETCH_K,
            lambda_mult=settings.RAG_MMR_LAMBDA_MULT,
            filter=filt,
        )
    return store.similarity_search(query, k=k, filter=filt)
