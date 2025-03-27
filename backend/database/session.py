import logging
import threading
from typing import AsyncGenerator, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from backend.config.settings import get_settings
from backend.database.models import Base

logger = logging.getLogger(__name__)

settings = get_settings()

# Thread-local storage for engines
_thread_local = threading.local()
_engines_lock = threading.Lock()
_engines: Dict[int, AsyncEngine] = {}


def get_engine() -> AsyncEngine:
    """Get or create an engine for the current thread."""
    thread_id = threading.get_ident()

    # Check if we already have an engine for this thread
    with _engines_lock:
        if thread_id not in _engines:
            # Create a new engine for this thread
            _engines[thread_id] = create_async_engine(
                settings.DATABASE_URL,
                pool_size=3,
                max_overflow=5,
                pool_timeout=30,
                pool_pre_ping=True,
                pool_use_lifo=True,
                echo=False,  # Disable SQL trace logging to reduce log verbosity
            )

    return _engines[thread_id]


def get_session_factory(engine: Optional[AsyncEngine] = None) -> async_sessionmaker:
    """Get a session factory for the given engine or current thread."""
    if engine is None:
        engine = get_engine()

    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions."""
    # Get the session factory for the current thread
    session_factory = get_session_factory()

    session = session_factory()
    try:
        async with session:
            yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    # Close all engines
    with _engines_lock:
        for engine in _engines.values():
            try:
                # First try to dispose of the engine's connection pool
                await engine.dispose()
            except RuntimeError as e:
                # If the event loop is closed, try to close connections directly
                try:
                    pool = engine.pool
                    if pool is not None:
                        for conn in pool._refs:  # type: ignore
                            try:
                                await conn.close()
                            except Exception:
                                pass
                except Exception as e:
                    logger.error(f"Error closing connections: {e}", exc_info=True)
        # Clear the engines dictionary
        _engines.clear()
