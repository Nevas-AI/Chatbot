"""
database.py - Async PostgreSQL Database Engine for Aria Dashboard
================================================================
SQLAlchemy async engine, session factory, and base model class.
Uses asyncpg for high-performance async PostgreSQL access.
"""

import os
import logging
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Database URL
# ─────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/aria_dashboard",
)

# ─────────────────────────────────────────────
# Engine & Session Factory
# ─────────────────────────────────────────────
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ─────────────────────────────────────────────
# Base model
# ─────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────
# Dependency: get a DB session
# ─────────────────────────────────────────────
async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async DB session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables. Called once at startup."""
    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(
            __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector")
        )
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables created successfully.")
