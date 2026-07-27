from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.config import DATABASE_URL, MARKET_DB_IS_FALLBACK, MARKET_DATABASE_URL

logger = logging.getLogger("uvicorn.error")


class Base(DeclarativeBase):
    pass


engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# market 전용 엔진 — 앱별 DB(market-pgvector :5434). URL 미설정이면 메인과 같은 DB를
# 가리키는 별도 풀이 된다(폴백 — 단순성을 위해 엔진 공유는 하지 않는다).
market_engine: AsyncEngine | None = None
_market_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine() -> None:
    global engine, _session_factory
    if engine is not None:
        return
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
    _session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


def init_market_engine() -> None:
    global market_engine, _market_session_factory
    if market_engine is not None:
        return
    if MARKET_DB_IS_FALLBACK:
        logger.warning(
            "MARKET_DATABASE_URL 미설정 — market 전용 DB(:5434)가 아니라 메인 DB로 폴백합니다. "
            "실운영이라면 .env에 키가 유실된 것입니다(2026-07-24 사고)."
        )
    market_engine = create_async_engine(MARKET_DATABASE_URL, pool_pre_ping=True, echo=False)
    _market_session_factory = async_sessionmaker(
        market_engine, expire_on_commit=False, autoflush=False
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        init_engine()
    if _session_factory is None:
        raise RuntimeError("DB 엔진이 초기화되지 않았습니다.")
    async with _session_factory() as session:
        yield session


async def get_market_db() -> AsyncGenerator[AsyncSession, None]:
    """market 스포크 전용 세션 — market 프로바이더만 사용한다(앱별 DB 불가침)."""
    if _market_session_factory is None:
        init_market_engine()
    if _market_session_factory is None:
        raise RuntimeError("market DB 엔진이 초기화되지 않았습니다.")
    async with _market_session_factory() as session:
        yield session


async def create_all_tables() -> None:
    if engine is None:
        init_engine()
    if engine is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    global engine, _session_factory
    if engine is not None:
        await engine.dispose()
    engine = None
    _session_factory = None


async def dispose_market_engine() -> None:
    global market_engine, _market_session_factory
    if market_engine is not None:
        await market_engine.dispose()
    market_engine = None
    _market_session_factory = None
