# fastapi-first

## 本地开发

推荐使用 FastAPI CLI（读取 `pyproject.toml` 中的 `[tool.fastapi] entrypoint`）：

```bash
uv run fastapi dev
```

或直接指定 Uvicorn 模块路径（仓库根为当前工作目录，`PYTHONPATH` 包含项目根时可省略额外配置）：

```bash
uv run uvicorn src.main:app --reload
```

## 日志与生产环境建议

应用使用标准库 `logging`，在启动时通过 `lifespan` 调用 `core.logging_config.setup_logging`。访问日志由中间件写入 logger `app.access`，字段包含 `method`、`path`（不含 query，避免敏感参数进日志）、`status_code`、`duration_ms`、`client_ip`（若有）。

### 环境变量

| 变量 | 说明 |
|------|------|
| `LOG_LEVEL` | 如 `INFO`、`WARNING`、`DEBUG`；生产建议 `INFO` 或更严。 |
| `LOG_FORMAT` | `text`（本地可读）或 `json`（单行 JSON，便于 Loki / ELK 等采集）。生产建议在 `/opt/my-agent-server/.env` 中设为 `json`。 |
| `DEBUG` | `false` 时关闭 `/docs`、`/redoc`、`/openapi.json`，且不挂载调试用 `/api/test/*` 路由。生产务必为 `false`。 |
| `SERVER_STATUS_TOKEN` | 设置后，`GET /server-status?token=…` 校验通过才返回探活 JSON；未设置或空则始终 404。 |
| `CORS_ORIGINS` | 逗号分隔的浏览器 `Origin`；留空则不注册 CORS 中间件（由网关或同源处理）。 |
| `TRUST_PROXY_HEADERS` | 限流用的客户端 IP：仅在为 `true` 时才读取 `X-Forwarded-For` 首段。直连公网时保持 `false`，避免客户端伪造 IP；置于受信反向代理之后且网关会剥离/覆盖不可信链时再设为 `true`。 |
| `GOOGLE_API_KEY` | LangChain Agent 使用的 Google GenAI API 密钥（必填，见 `core.settings`）。 |

示例见仓库根目录 `.env.sample`。

### 反向代理与限流

默认（`TRUST_PROXY_HEADERS=false`）限流按 `request.client`（与 Uvicorn 之间一跳的 TCP 对端）区分客户端。若应用前有 Nginx、Ingress 等，应在网关把真实客户端 IP 写入受信头，并仅在确认该头不会被外网伪造后将本应用 `TRUST_PROXY_HEADERS` 设为 `true`。

### 与 Uvicorn 的 access 日志

应用内已有一套结构化访问日志。若同时使用 Uvicorn 默认 access，会出现两套访问行。生产环境可二选一：

- **推荐**：关闭 Uvicorn 自带 access，只保留应用内日志。

  ```bash
  uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --no-access-log
  ```

- **或**：使用 Uvicorn 的 `--log-config` 提供自定义 logging 配置，自行统一格式与级别（需与当前 `dictConfig` 协调，避免重复 handler）。

### 业务代码中打日志

```python
import logging

logger = logging.getLogger(__name__)
logger.info("处理完成", extra={"order_id": "123"})
```

不要在日志中输出 `Authorization`、Cookie、URL query 中的 token、密码或 JWT 载荷。

## RAG 与 pgvector

对话与检索依赖 PostgreSQL **pgvector** 扩展及业务表。应用**启动时**会检查 `pgvector` 是否已安装；未安装则进程退出（不会自动 `CREATE EXTENSION`，通常需超级用户权限）。

### 数据库迁移（按顺序执行）

```bash
psql "$ASYNC_DATABASE_URL" -f migrations/001_pgvector.sql
psql "$ASYNC_DATABASE_URL" -f migrations/002_works_documents.sql
```

首次文档入库时，`langchain-postgres` 会自动创建 `langchain_pg_collection`、`langchain_pg_embedding` 等向量表。

### RAG 相关环境变量

见 `.env.sample` 中 `ARK_API_KEY`、`RAG_*` 项。RAG 使用火山方舟 **Doubao-embedding-vision**（`POST /embeddings/multimodal`）；Agent 对话仍使用 `GOOGLE_API_KEY`。

| 变量 | 说明 |
|------|------|
| `ARK_API_KEY` | 火山方舟 API Key（控制台创建） |
| `RAG_EMBEDDING_BASE_URL` | 方舟：`https://ark.cn-beijing.volces.com/api/v3`（**不要**加 `/embeddings` 或 `/process`） |
| `RAG_EMBEDDING_MODEL` | Doubao-embedding-vision 推理接入点，如 `ep-xxx` |
| `RAG_EMBEDDING_DIMENSIONS` | 常用 `1024`（与接入点一致） |

若曾用其他 Embedding 模型入库，更换模型后需**清空向量并重新上传文档**（维度可能不同）。

### HTTP API（均需 `Authorization: Bearer <JWT>`）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/works` | 创建作品 `{ "title": "..." }` |
| GET | `/api/works` | 作品列表 |
| GET/PATCH/DELETE | `/api/works/{work_id}` | 详情 / 重命名 / 级联删除向量 |
| GET | `/api/works/{work_id}/documents` | 文档列表 |
| POST | `/api/works/{work_id}/documents` | 上传 `.txt` / `.md`（multipart `file`） |
| DELETE | `/api/works/{work_id}/documents/{document_id}` | 删除文档及向量 |
| POST | `/api/agent/chat/stream` | SSE；JSON 含 `message` 与 **`work_id`** |

### 手工验收

1. 执行上述 SQL 迁移后启动应用。
2. 登录获取 JWT → `POST /api/works` 创建作品 → 上传 sample.md。
3. `POST /api/agent/chat/stream`，body：`{"message":"…","work_id":1}`，确认响应基于文档内容。
4. `DELETE /api/works/{id}` 后，同 `work_id` 对话应无检索片段。

**注意**：更换 `RAG_EMBEDDING_MODEL` 会改变向量维度，需清空并重建向量数据。

## Docker 部署

镜像使用根目录 `Dockerfile` **多阶段**构建：依赖由 `uv.lock` 锁定（包索引已指向清华源，见 `uv.lock`），运行镜像不含 `uv` / `pyproject.toml`，体积更小；以非 root 用户运行单进程 Uvicorn，内置 TCP 健康检查（监听 `8000`）。**镜像内不包含 `.env`**（见 `.dockerignore`），配置须在运行时通过环境变量注入。

### 前置条件

1. 目标 PostgreSQL 已执行 `migrations/001_pgvector.sql`、`migrations/002_works_documents.sql`（在宿主机或能连库的机器上执行，不必在容器内）。
2. 准备好生产环境变量文件（可复制 `.env.sample` 为 `/opt/my-agent-server/.env`），至少包含 `ASYNC_DATABASE_URL`、`JWT_SECRET`、`DEBUG=false`、`REDIS_*`、`GOOGLE_API_KEY`、`ARK_API_KEY`、`RAG_EMBEDDING_MODEL` 等，字段说明见上文表格与 `.env.sample`。
3. 容器需能访问数据库、Redis 及方舟 / Google API（防火墙与安全组放行对应端口）。

### 构建镜像

在仓库根目录执行（建议开启 BuildKit）：

```bash
export DOCKER_BUILDKIT=1
docker build -t fastapi-first:latest .
```

可按版本打标签，例如：

```bash
docker build -t fastapi-first:1.0.0 .
```

#### 腾讯云轻量服务器注意

| 问题 | 建议 |
|------|------|
| 拉取 `python:3.14-slim`、`ghcr.io/astral-sh/uv` 慢 | 在 `/etc/docker/daemon.json` 配置 **镜像加速**（腾讯云控制台提供的 Docker 加速地址），`systemctl restart docker` 后重试 |
| 构建时内存不足（LangChain 依赖较多） | 2GB 机型建议先开 **2GB swap**；构建时不要并行跑多个大镜像；失败可看 `dmesg` 是否 OOM |
| 磁盘紧张 | 构建后执行 `docker image prune -f`；多阶段镜像已去掉构建工具，比单阶段更小 |
| 运行内存 | **不要**给 Uvicorn 加 `--workers`（默认 1 即可）；RAG 入库与 Agent 流式会短时占内存 |
| PyPI | 依赖下载走 `uv.lock` 内清华源 URL，一般无需再配 `UV_INDEX_URL` |

首次构建在轻量机上可能需要 **10～20 分钟**（拉基础镜像 + 装依赖），属正常现象。

### 运行容器

推荐用 `--env-file` 注入配置（勿把真实密钥提交进镜像）：

```bash
docker run -d \
  --name my-agent-serve \
  --env-file /opt/my-agent-server/.env \
  -p 8000:8000 \
  --restart unless-stopped \
  fastapi-first:latest
```

说明：

| 项 | 说明 |
|----|------|
| `-p 8000:8000` | 宿主机端口映射到容器内 Uvicorn |
| `--env-file` | 将文件中的键值注入为容器环境变量；`Settings` 从环境变量读取，无需把 `.env` 打进镜像 |
| `DEBUG` | 生产务必为 `false`（或 `False`），以关闭 `/docs` 等调试面 |
| `LOG_FORMAT` | 建议 `json`，便于日志采集 |
| `TRUST_PROXY_HEADERS` | 仅当应用位于**受信**反向代理之后且网关会正确改写 `X-Forwarded-For` 时设为 `true` |

查看日志与健康状态：

```bash
docker logs -f fastapi-first
docker inspect --format='{{json .State.Health}}' fastapi-first
```

若配置了 `SERVER_STATUS_TOKEN`，可在网关后探活：

```text
GET /server-status?token=<SERVER_STATUS_TOKEN>
```

### 置于 Nginx / Ingress 之后

对外只暴露反向代理端口；容器仍监听 `8000`。代理需转发 `Host`、`X-Forwarded-For`、`X-Forwarded-Proto` 等头，并在确认头不可被客户端伪造后将应用侧 `TRUST_PROXY_HEADERS=true`。

### 更新发布

```bash
docker build -t fastapi-first:latest .
docker stop fastapi-first && docker rm fastapi-first
docker run -d --name fastapi-first --env-file /opt/my-agent-server/.env -p 8000:8000 --restart unless-stopped fastapi-first:latest
```

或使用新标签滚动替换，避免覆盖正在运行的 `latest` 层。

## 测试

单元测试对 `Settings` 等使用显式构造参数或 monkeypatch，**不应依赖**本机根目录 `.env` 才能通过。安装开发依赖后运行：

```bash
uv sync --group dev
uv run pytest
```
