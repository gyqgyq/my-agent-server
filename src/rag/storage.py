from __future__ import annotations

from pathlib import Path

from src.core.settings import settings


def _suffix_from_filename(filename: str) -> str:
    if "." in filename:
        return filename[filename.rfind(".") :].lower()
    return ".txt"


def document_storage_path(
    user_id: int,
    work_id: int,
    document_id: int,
    filename: str,
) -> Path:
    return (
        Path(settings.RAG_UPLOAD_DIR)
        / f"u{user_id}"
        / f"w{work_id}"
        / f"d{document_id}{_suffix_from_filename(filename)}"
    )


def ensure_upload_dir() -> None:
    Path(settings.RAG_UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


def save_upload_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def read_upload_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def delete_upload_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    parent = path.parent
    if parent.exists() and not any(parent.iterdir()):
        try:
            parent.rmdir()
        except OSError:
            pass
