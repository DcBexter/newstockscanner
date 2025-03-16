from typing import AsyncGenerator, Dict, Optional
import asyncio
import threading
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker

from backend.config.settings import get_settings
from backend.database.models import Base

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
                echo=False,
                future=True,
                pool_pre_ping=True,
                # Use smaller pool size for thread-specific engines
                pool_size=5,
                max_overflow=10
            )
    
    return _engines[thread_id]

def get_session_factory(engine: Optional[AsyncEngine] = None) -> sessionmaker:
    """Get a session factory for the given engine or current thread."""
    if engine is None:
        engine = get_engine()
    
    return sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions."""
    # Get the session factory for the current thread
    session_factory = get_session_factory()
    
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
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
            await engine.dispose()
        _engines.clear() 
