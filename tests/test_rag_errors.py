import httpx

from src.rag.errors import map_embedding_error


def _http_status_error(status: int, body: str = "") -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://ark.example.com/v3/embeddings/multimodal")
    response = httpx.Response(status, text=body, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


def test_map_embedding_error_403() -> None:
    exc = map_embedding_error(_http_status_error(403))
    assert exc.status_code == 502
    assert "403" in exc.detail
    assert "ARK_API_KEY" in exc.detail


def test_map_embedding_error_401() -> None:
    exc = map_embedding_error(_http_status_error(401))
    assert exc.status_code == 502
    assert "401" in exc.detail


def test_map_embedding_error_429() -> None:
    exc = map_embedding_error(_http_status_error(429))
    assert exc.status_code == 429


def test_map_embedding_error_400() -> None:
    exc = map_embedding_error(_http_status_error(400))
    assert exc.status_code == 400
