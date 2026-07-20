"""Neo4j drivers — sync for workers/search/MCP; async for health probe."""
from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator

from neo4j import AsyncGraphDatabase, GraphDatabase
from neo4j import AsyncDriver, Driver

from src.config import settings

_sync_driver: Driver | None = None
_async_driver: AsyncDriver | None = None

_POOL = {
    "max_connection_pool_size": 25,
    "connection_acquisition_timeout": 30,
}


def get_sync_driver() -> Driver:
    global _sync_driver
    if _sync_driver is None:
        _sync_driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            **_POOL,
        )
    return _sync_driver


def get_async_driver() -> AsyncDriver:
    global _async_driver
    if _async_driver is None:
        _async_driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            **_POOL,
        )
    return _async_driver


@contextmanager
def sync_session() -> Iterator:
    driver = get_sync_driver()
    with driver.session() as session:
        yield session


@asynccontextmanager
async def async_session() -> AsyncIterator:
    driver = get_async_driver()
    async with driver.session() as session:
        yield session


def verify_connectivity() -> None:
    get_sync_driver().verify_connectivity()


def is_available() -> bool:
    try:
        verify_connectivity()
        return True
    except Exception:
        return False


def reset_drivers() -> None:
    """Test helper — close and drop singletons."""
    global _sync_driver, _async_driver
    if _sync_driver is not None:
        _sync_driver.close()
        _sync_driver = None
    if _async_driver is not None:
        # AsyncDriver.close() is sync in neo4j 5
        _async_driver.close()
        _async_driver = None
