"""Async SQLAlchemy engine + session factory used by the worker."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def make_engine(url: str):  # type: ignore[no-untyped-def]
    """Build an async engine from a Postgres URL.

    Postgres-only in production. The worker does not run against SQLite.
    """
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return create_async_engine(url, pool_pre_ping=True, future=True)


def make_sessionmaker(engine) -> async_sessionmaker[AsyncSession]:  # type: ignore[no-untyped-def]
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
