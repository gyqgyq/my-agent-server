# 生产镜像（多阶段）：构建装依赖，运行层仅保留 venv + 源码，减小磁盘占用。
# 适配腾讯云轻量等 2GB 内存机器：单 worker Uvicorn，勿在 CMD 中加大 --workers。
# syntax=docker/dockerfile:1

FROM python:3.14-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_CONCURRENT_DOWNLOADS=4 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev --no-editable \
    && rm -rf /root/.cache/uv

# --- 运行阶段：与 builder 同基础镜像，保证 venv 与解释器 ABI 一致 ---
FROM python:3.14-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /var/lib/wensu/uploads \
    && chown -R appuser:appuser /app /var/lib/wensu/uploads

ENV RAG_UPLOAD_DIR=/var/lib/wensu/uploads

VOLUME ["/var/lib/wensu/uploads"]

USER appuser

EXPOSE 8000

# 启动会连库；弱 CPU 上冷启动可能较慢，start-period 略放宽
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import socket; s=socket.create_connection(('127.0.0.1',8000),2); s.close()"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
