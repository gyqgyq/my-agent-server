from src.core.settings import Settings


def test_parsed_cors_origins() -> None:
    s = Settings(
        ASYNC_DATABASE_URL="postgresql://localhost/db",
        JWT_SECRET="x",
        DEBUG=False,
        REDIS_HOST="localhost",
        REDIS_PORT=6379,
        REDIS_DB=0,
        REDIS_PASSWORD="",
        AGENT_CHAT_API_KEY="test",
        ARK_API_KEY="test-ark",
        CORS_ORIGINS=" http://a.com ,https://b.com ",
    )
    assert s.parsed_cors_origins() == ["http://a.com", "https://b.com"]


def test_parsed_cors_origins_empty() -> None:
    s = Settings(
        ASYNC_DATABASE_URL="postgresql://localhost/db",
        JWT_SECRET="x",
        DEBUG=False,
        REDIS_HOST="localhost",
        REDIS_PORT=6379,
        REDIS_DB=0,
        REDIS_PASSWORD="",
        AGENT_CHAT_API_KEY="test",
        ARK_API_KEY="test-ark",
        CORS_ORIGINS="   ",
    )
    assert s.parsed_cors_origins() == []
