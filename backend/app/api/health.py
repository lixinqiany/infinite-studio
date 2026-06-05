"""健康检查：验证 FastAPI 进程与 Postgres 链路是否通。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, str]:
    """返回进程状态 + DB ping 结果。DB 连不上时 status=degraded、db=down，但不抛 500。"""
    try:
        await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "down"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
    }
