# fastapi-first

## 本地开发

```bash
uv run uvicorn main:app --reload
```

## 日志与生产环境建议

应用使用标准库 `logging`，在启动时通过 `lifespan` 调用 `core.logging_config.setup_logging`。访问日志由中间件写入 logger `app.access`，字段包含 `method`、`path`（不含 query，避免敏感参数进日志）、`status_code`、`duration_ms`、`client_ip`（若有）。

### 环境变量

| 变量 | 说明 |
|------|------|
| `LOG_LEVEL` | 如 `INFO`、`WARNING`、`DEBUG`；生产建议 `INFO` 或更严。 |
| `LOG_FORMAT` | `text`（本地可读）或 `json`（单行 JSON，便于 Loki / ELK 等采集）。生产建议在 `.env.prod` 中设为 `json`。 |

示例见仓库根目录 `.env.sample`。

### 与 Uvicorn 的 access 日志

应用内已有一套结构化访问日志。若同时使用 Uvicorn 默认 access，会出现两套访问行。生产环境可二选一：

- **推荐**：关闭 Uvicorn 自带 access，只保留应用内日志。

  ```bash
  uv run uvicorn main:app --host 0.0.0.0 --port 8000 --no-access-log
  ```

- **或**：使用 Uvicorn 的 `--log-config` 提供自定义 logging 配置，自行统一格式与级别（需与当前 `dictConfig` 协调，避免重复 handler）。

### 业务代码中打日志

```python
import logging

logger = logging.getLogger(__name__)
logger.info("处理完成", extra={"order_id": "123"})
```

不要在日志中输出 `Authorization`、Cookie、URL query 中的 token、密码或 JWT 载荷。
