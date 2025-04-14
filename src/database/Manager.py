"""
Database manager with parent/worker process separation and thread-safe session handling.
Provides automatic transaction management with commit-on-success and rollback-on-exception.
"""

import logging
import multiprocessing
from contextlib import asynccontextmanager, contextmanager
from threading import local
from typing import AsyncGenerator, Generator, Optional

from database.Base import DATABASE_TYPE, DATABASE_URI
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker


class DatabaseManager:
    """
    Thread-safe database manager with parent/worker process separation.
    Engine configuration happens in parent process, sessions in workers.
    Provides automatic transaction management.
    """

    _instance = None
    _lock = multiprocessing.Lock()

    def __init__(self):
        # Engine configurations (set in parent process)
        self.engine_config: Optional[dict] = None
        self.async_engine_config: Optional[dict] = None
        self._setup_engine: Optional[Engine] = None

        # Worker-specific attributes (initialized per worker)
        self.engine: Optional[Engine] = None
        self.async_engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._async_session_factory: Optional[async_sessionmaker] = None
        self._worker_initialized = False

        # Thread-local storage for session management
        self._thread_local = local()

    @classmethod
    def get_instance(cls) -> "DatabaseManager":
        """Get or create the singleton instance with thread-safe double-checked locking."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def init_engine_config(self) -> None:
        """Initialize engine configuration in parent process."""
        logging.info("Initializing database engine configuration in parent process")

        if DATABASE_TYPE == "sqlite":
            self.engine_config = {
                "url": DATABASE_URI,
                "connect_args": {"check_same_thread": False},
                "pool_pre_ping": True,
                "pool_recycle": 3600,
            }
            async_url = DATABASE_URI.replace("sqlite://", "sqlite+aiosqlite://")
            self.async_engine_config = {
                "url": async_url,
                "connect_args": {"check_same_thread": False},
                "pool_pre_ping": True,
                "pool_recycle": 3600,
            }
        else:
            self.engine_config = {
                "url": DATABASE_URI,
                "pool_size": 20,
                "max_overflow": 10,
                "pool_pre_ping": True,
                "pool_recycle": 3600,
            }
            async_url = DATABASE_URI.replace("postgresql://", "postgresql+asyncpg://")
            self.async_engine_config = {
                "url": async_url,
                "pool_size": 20,
                "max_overflow": 10,
                "pool_pre_ping": True,
                "pool_recycle": 3600,
            }

        # Create setup engine for parent process initialization
        self._setup_engine = create_engine(**self.engine_config)

    def get_setup_engine(self) -> Engine:
        """Get the setup engine used for parent process initialization."""
        if not self._setup_engine:
            raise RuntimeError("Setup engine not initialized")
        return self._setup_engine

    def init_worker(self) -> None:
        """Initialize database connections for this worker."""
        if self._worker_initialized:
            return

        if not self.engine_config or not self.async_engine_config:
            raise RuntimeError("Engine configuration not initialized in parent process")

        logging.info("Initializing database connections for worker")

        # Create engines using pre-configured settings
        self.engine = create_engine(**self.engine_config)
        self.async_engine = create_async_engine(**self.async_engine_config)

        # Create session factories
        self._session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
            expire_on_commit=False,
        )

        self._async_session_factory = async_sessionmaker(
            self.async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        self._worker_initialized = True

    async def close_worker(self) -> None:
        """Clean up database connections for this worker."""
        if not self._worker_initialized:
            return

        logging.info("Closing database connections for worker")

        # Close any open sessions
        if hasattr(self._thread_local, "session"):
            self._thread_local.session.close()

        if hasattr(self._thread_local, "async_session"):
            await self._thread_local.async_session.close()

        # Dispose engines
        if self.engine:
            self.engine.dispose()

        if self.async_engine:
            await self.async_engine.dispose()

        self._worker_initialized = False

    @contextmanager
    def _get_db_session(
        self, *, auto_commit: bool = True
    ) -> Generator[Session, None, None]:
        """
        Internal method for getting a database session.
        Args:
            auto_commit: If True, automatically commits if no exceptions occur
        """
        if not self._worker_initialized:
            self.init_worker()

        if not hasattr(self._thread_local, "session"):
            self._thread_local.session = self._session_factory()

        session = self._thread_local.session
        try:
            yield session
            if auto_commit:
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            delattr(self._thread_local, "session")

    @asynccontextmanager
    async def _get_async_db_session(
        self, *, auto_commit: bool = True
    ) -> AsyncGenerator[AsyncSession, None]:
        """
        Internal method for getting an async database session.
        Args:
            auto_commit: If True, automatically commits if no exceptions occur
        """
        if not self._worker_initialized:
            self.init_worker()

        async with self._async_session_factory() as session:
            try:
                yield session
                if auto_commit:
                    await session.commit()
            except Exception:
                await session.rollback()
                raise

    def get_db(self, auto_commit: bool = True) -> Generator[Session, None, None]:
        """
        FastAPI dependency for getting a database session.
        Args:
            auto_commit: If True, automatically commits if no exceptions occur.
                       Set to False when you need to control transaction boundaries manually.

        Usage:
            # Auto-commit mode (default)
            @router.get("/")
            def endpoint(db: Session = Depends(db_manager.get_db)):
                user = db.query(User).first()
                # Transaction automatically committed if no exceptions

            # Manual commit mode
            @router.get("/")
            def endpoint(db: Session = Depends(Depends(lambda: db_manager.get_db(auto_commit=False)))):
                user = db.query(User).first()
                db.commit()  # Manual commit required
        """
        with self._get_db_session(auto_commit=auto_commit) as session:
            yield session

    async def get_async_db(
        self, auto_commit: bool = True
    ) -> AsyncGenerator[AsyncSession, None]:
        """
        FastAPI dependency for getting an async database session.
        Args:
            auto_commit: If True, automatically commits if no exceptions occur.
                       Set to False when you need to control transaction boundaries manually.

        Usage:
            # Auto-commit mode (default)
            @router.get("/")
            async def endpoint(db: AsyncSession = Depends(db_manager.get_async_db)):
                result = await db.execute(select(User))
                # Transaction automatically committed if no exceptions

            # Manual commit mode
            @router.get("/")
            async def endpoint(
                db: AsyncSession = Depends(lambda: db_manager.get_async_db(auto_commit=False))
            ):
                result = await db.execute(select(User))
                await db.commit()  # Manual commit required
        """
        async with self._get_async_db_session(auto_commit=auto_commit) as session:
            yield session

    def cleanup_thread(self) -> None:
        """Clean up thread-local resources."""
        if hasattr(self._thread_local, "session"):
            self._thread_local.session.close()
            delattr(self._thread_local, "session")


# Global instance
db_manager = DatabaseManager.get_instance()
