# infinite-studio

万能 AI 工坊 —— Web 形态的统一 AI 能力平台（MVP-1）。

- 设计文档：[`docs/2026-06-03-infinite-studio-mvp-1-table-design.md`](docs/2026-06-03-infinite-studio-mvp-1-table-design.md)
- 形态：**monorepo** —— `backend/`（Python · FastAPI · uv）+ `frontend/`（Vue3 · TS · pnpm），各自独立工具链。

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vue3 + TypeScript + Vite（Router / Pinia / ESLint / Prettier / Vitest） |
| 后端 | Python 3.12 + FastAPI + SQLAlchemy 2.0(async) + Alembic |
| 数据库 | PostgreSQL 18（docker 起） |
| 驱动 | psycopg3（app 走 async，alembic 走 sync，同一驱动） |

## 前置工具

`uv`、`pnpm`、`docker`（Node 20+、Python 3.12）。Windows 与 Mac 命令一致。

## 本地开发（起三样：依赖 + 后端 + 前端）

```bash
# 0) 准备环境变量
cp .env.example .env          # Windows PowerShell: copy .env.example .env

# 1) 起开发依赖（Postgres，后台运行）
docker compose -f docker/docker-compose.yml up -d

# 2) 终端 A —— 后端（热重载，:8000）
cd backend && uv run uvicorn app.main:app --reload

# 3) 终端 B —— 前端（热重载，:5173）
cd frontend && pnpm install   # 首次
pnpm dev
```

打开 http://localhost:5173 —— 首页应显示后端健康状态。
后端健康检查：`curl http://localhost:8000/health` → `{"status":"ok","db":"ok"}`。

## 常用命令

```bash
# 依赖（Postgres）
docker compose -f docker/docker-compose.yml down        # 停
docker compose -f docker/docker-compose.yml logs -f db  # 看日志
docker compose -f docker/docker-compose.yml exec db psql -U infinite -d infinite_studio  # 进 psql

# 后端
cd backend && uv run alembic upgrade head   # 应用迁移（当前无迁移，no-op）
cd backend && uv run ruff check .           # lint
```

> 说明：compose **只起 Postgres**。前后端在本机裸跑以便热重载/断点；因此后端连库串用 `localhost:5432`（见 `.env.example`）。
