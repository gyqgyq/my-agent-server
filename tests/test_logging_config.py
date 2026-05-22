import json
import logging
from pathlib import Path

from src.core.logging_config import setup_logging
from src.core.settings import Settings


def _base_settings(**overrides) -> Settings:
    defaults = {
        "ASYNC_DATABASE_URL": "postgresql://localhost/db",
        "JWT_SECRET": "x",
        "DEBUG": False,
        "REDIS_HOST": "localhost",
        "REDIS_PORT": 6379,
        "REDIS_DB": 0,
        "REDIS_PASSWORD": "",
        "AGENT_CHAT_API_KEY": "test",
        "ARK_API_KEY": "test-ark",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_setup_logging_stderr_only() -> None:
    setup_logging(_base_settings(LOG_FORMAT="json"))
    root = logging.getLogger()
    names = [type(h).__name__ for h in root.handlers]
    assert names == ["StreamHandler"]


def test_setup_logging_with_rotating_file(tmp_path: Path) -> None:
    log_path = tmp_path / "app.log"
    setup_logging(_base_settings(LOG_FORMAT="json", LOG_FILE=str(log_path)))
    root = logging.getLogger()
    handler_types = {type(h).__name__ for h in root.handlers}
    assert handler_types == {"StreamHandler", "RotatingFileHandler"}

    logging.getLogger("test.app").warning("hello_file", extra={"k": 1})
    for h in root.handlers:
        h.flush()

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    payloads = [json.loads(line) for line in lines]
    warn = next(p for p in payloads if p.get("message") == "hello_file")
    assert warn["level"] == "WARNING"
    assert warn["k"] == 1
