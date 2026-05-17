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
| `LOG_FORMAT` | `text`（本地可读）或 `json`（单行 JSON，便于 Loki / ELK 等采集）。生产建议在 `.env.prod` 中设为 `json`。 |
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

## Gitee Go / 腾讯云部署

推送 `main`（或 `master`）时，[`.gitee-ci.yml`](.gitee-ci.yml) 使用 **Gitee Go 原生格式**（`version` + `stages` + `step` 插件），不是 GitLab CI 语法。

### 社区版与共享构建资源

本项目按 **Gitee 社区版 + Gitee Go 官方共享构建资源** 设计（无需自建 Runner、无需企业版私有构建集群）：

| 阶段 | 插件 | 运行环境 |
|------|------|----------|
| **构建并推送镜像** | `build@docker` | Gitee **共享构建机**（云端自动分配） |
| **部署到 CVM** | `shell@agent` | 你腾讯云 CVM 上安装的 **Gitee Agent**（主机组） |

说明：

- 共享构建资源只负责 **Docker 构建 + 推送到 TCR**；不会在共享机上替你跑生产容器。
- 自动部署仍需在 Gitee Go **主机管理** 中把 CVM 加入主机组，并配置变量 `DEPLOY_HOST_GROUP`。
- 免费额度：单仓库约 **200 分钟** 构建时长；账号每月约 **500 分钟**（以 Gitee 当前规则为准）。
- 当前部署阶段为 **`trigger: manual`**：镜像构建成功后在流水线里**手动触发**部署，避免未配主机组时自动失败。

**尚未配置主机组时**（仅共享构建）：构建完成后在 CVM 上手动执行（将 `<镜像>` 换为流水线日志中的 `GITEE_DOCKER_IMAGE`）：

```bash
echo "<TCR密码>" | docker login ccr.ccs.tencentyun.com -u "<TCR用户名>" --password-stdin
docker pull <镜像>
docker stop fastapi-first 2>/dev/null || true
docker rm fastapi-first 2>/dev/null || true
docker run -d --name fastapi-first --restart unless-stopped \
  -p 8000:8000 --env-file /opt/my-agent-server/.env <镜像>
```

### 所有流水线变量

配置入口：**仓库 → 设置 → 流水线变量**（建议 Secret 项勾选「保护变量 / 掩码」）。

#### 1. 需在 Gitee 配置的变量

| 变量名 | 必填 | 类型建议 | 说明 | 使用阶段 |
|--------|------|----------|------|----------|
| `DOCKER_USER` | 是 | Secret | 腾讯云 TCR 登录用户名 | 构建、部署 |
| `DOCKER_PWD` | 是 | Secret | 腾讯云 TCR 登录密码 | 构建、部署 |
| `DEPLOY_HOST_GROUP` | 否* | 普通 | Gitee Go **主机组唯一标识**；启用自动/手动部署阶段时必填 | 部署 |

\* 仅使用共享构建、在服务器手动 `docker run` 时可不配置。
| `DEPLOY_ENV_FILE` | 否 | 普通 | 服务器上 `.env` 绝对路径；未配置时默认 `/opt/my-agent-server/.env` | 部署 |
| `HOST_PORT` | 否 | 普通 | 宿主机映射端口；未配置时默认 `8000`（容器内固定 `8000`） | 部署 |

**仅共享构建（推镜像）** 最少 2 项 Secret：

```text
DOCKER_USER = <TCR 用户名>   [Secret]
DOCKER_PWD  = <TCR 密码>     [Secret]
```

**含流水线部署阶段** 再增加：

```text
DEPLOY_HOST_GROUP = <主机组唯一标识>   [普通]
```

#### 2. Gitee Go 系统变量（自动注入，无需配置）

| 变量名 | 说明 |
|--------|------|
| `GITEE_PIPELINE_BUILD_NUMBER` | 本次构建号；镜像 tag 为 `fastapi-first:<构建号>` |
| `GITEE_DOCKER_IMAGE` | 镜像构建插件产出；部署阶段 `docker pull` 使用此地址 |
| `GITEE_PIPELINE_NAME` | 流水线唯一标识 |
| `GITEE_PIPELINE_DISPLAY_NAME` | 流水线显示名称 |
| `GITEE_COMMIT` | 提交 SHA |
| `GITEE_BRANCH` | 分支名 |
| `GITEE_REPO` | 仓库名 |
| `GITEE_PIPELINE_TRIGGER_USER` | 触发人 |

更多系统参数见 [Gitee Go 参数设置](https://help.gitee.com/gitee-go/pipeline/parameter)。

#### 3. 写在 `.gitee-ci.yml` 中的固定项（非流水线变量）

| 项 | 当前值 |
|----|--------|
| TCR 仓库 | `ccr.ccs.tencentyun.com/my-agent-server` |
| 镜像名 | `fastapi-first` |
| 容器名 | `fastapi-first` |
| 容器内端口 | `8000` |
| Dockerfile | `./Dockerfile` |

镜像示例：`ccr.ccs.tencentyun.com/my-agent-server/fastapi-first:<构建号>`

#### 4. 未在流水线中使用（可保留作本地/手工运维）

| 变量名 | 说明 |
|--------|------|
| `SERVER_HOST` | 服务器公网 IP；共享构建流水线不读取，可用于本机 `ssh` 运维 |
| `SERVER_USER` | SSH 登录用户 |
| `SERVER_SSH_KEY` | SSH 私钥 |

#### 5. 应用环境变量（服务器 `.env`，勿写入 Gitee 流水线）

由 `docker run --env-file` 注入，路径为 `DEPLOY_ENV_FILE`（默认 `/opt/my-agent-server/.env`），字段见 [`.env.sample`](.env.sample)。与流水线变量分工：

- **Gitee 流水线变量**：构建镜像、登录 TCR、选择部署主机。
- **服务器 `.env`**：数据库、JWT、Redis、LLM / RAG 等业务配置。

| 变量 | 必填 | 说明 |
|------|------|------|
| `ASYNC_DATABASE_URL` | 是 | PostgreSQL 连接串 |
| `JWT_SECRET` | 是 | JWT 签名密钥 |
| `DEBUG` | 是 | 生产务必 `false` |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB` / `REDIS_PASSWORD` | 是 | Redis |
| `GOOGLE_API_KEY` | 是 | Agent 对话（Gemini） |
| `ARK_API_KEY` | 是 | 火山方舟 |
| `RAG_EMBEDDING_MODEL` | 是 | Doubao-embedding-vision 接入点 `ep-xxx` |
| `LOG_LEVEL` / `LOG_FORMAT` | 否 | 日志 |
| `RAG_EMBEDDING_BASE_URL` / `RAG_EMBEDDING_DIMENSIONS` | 否 | RAG 向量化 |
| `CORS_ORIGINS` / `SERVER_STATUS_TOKEN` / `TRUST_PROXY_HEADERS` | 否 | 跨域、探活、代理头 |
| 其余 `RAG_*`、`AGENT_*` | 否 | 见 `.env.sample` 注释 |

### 主机组（流水线自动部署时需要）

在 Gitee Go 中使用 `shell@agent` / `deploy@agent` 时（**不是**共享构建机）：

1. **仓库 → 服务 → Gitee Go → 主机管理** → 新建主机组，记下**唯一标识**（填入 `DEPLOY_HOST_GROUP`）。
2. 在腾讯云 CVM 上按页面安装 **Gitee Agent**（社区版支持公网主机接入）。
3. 主机显示**在线**后，在流水线中手动或自动执行 **deploy** 阶段。
4. 将主机组与当前仓库**关联**（若页面有「关联仓库」选项）。

### 服务器首次准备

```bash
sudo mkdir -p /opt/my-agent-server
# 将 .env.sample 复制为 .env 并按生产填写（DEBUG=false、数据库、Redis、GOOGLE_API_KEY、ARK_API_KEY、RAG_* 等）
sudo chmod 600 /opt/my-agent-server/.env
```

1. 安装 Docker；安全组放行 `HOST_PORT`（默认 8000）。
2. PostgreSQL 已启用 **pgvector** 并完成迁移（见上文「数据库迁移」）。
3. 确保服务器能访问火山方舟与 Google GenAI（出站 HTTPS）。

部署成功后容器名 `fastapi-first`，日志可用 `docker logs -f fastapi-first` 查看；应出现 `Application startup complete`。

## 测试

单元测试对 `Settings` 等使用显式构造参数或 monkeypatch，**不应依赖**本机根目录 `.env` 才能通过。安装开发依赖后运行：

```bash
uv sync --group dev
uv run pytest
```
