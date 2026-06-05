"""数据库接线：async engine + session + 声明式 Base。

本期只铺地基 —— Base 暂无任何模型；13 张表的模型与首条迁移留到下一步。
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类；Alembic 的 target_metadata 指向 Base.metadata。"""


async def get_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI 依赖：每请求一个 session。"""
    async with async_session() as session:
        yield session
