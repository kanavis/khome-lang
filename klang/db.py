import logging
from contextlib import asynccontextmanager
from typing import Optional, Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


engine: Optional[AsyncEngine] = None

log = logging.getLogger(__name__)


def setup_db_engine(db_user: str, db_password: str, db_host: str, db_port: int, db_name: str):
    global engine
    db_url = "postgresql+asyncpg://{}:{}@{}:{}/{}".format(
        db_user, db_password, db_host, db_port, db_name,
    )
    engine = AsyncEngine(create_engine(db_url))


async def create_db_and_tables():
    if engine is None:
        raise Exception("Database engine is not initialized")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def _get_session() -> AsyncGenerator[AsyncSession, None]:
    if engine is None:
        raise Exception("Database engine is not initialized")
    async_session = sessionmaker(  # type: ignore
        engine, class_=AsyncSession, expire_on_commit=False,
    )
    async with async_session() as session:
        yield session


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if engine is None:
        raise Exception("Database engine is not initialized")
    async_session = sessionmaker(  # type: ignore
        engine, class_=AsyncSession, expire_on_commit=False,
    )
    async with async_session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(_get_session)]
