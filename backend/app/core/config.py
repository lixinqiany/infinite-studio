"""应用配置：单一事实源是仓库根的 .env（docker compose 也读同一份）。

pydantic-settings 默认按进程 CWD 找 env_file，但后端通常从 backend/ 启动，
而 .env 在仓库根。这里用相对本文件的绝对路径锁定到根 .env，避免 CWD 漂移。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py → parents[3] = 仓库根
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 后端连库串（psycopg3 async，如 postgresql+psycopg://user:pw@localhost:5432/db）
    database_url: str = "postgresql+psycopg://infinite:infinite_dev_pw@localhost:5432/infinite_studio"

    # CORS 放行的前端 dev 源
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
