# Database Management Documentation

This document details the database connection management, optimization strategies, and transaction handling patterns used in the application.

## Database Connection Architecture

The system uses a two-tier architecture for database connections:

1. **Parent Process**: Configures engines and connection parameters
2. **Worker Processes**: Create and manage actual database connections

This separation provides:
- Clean shutdown capabilities
- Connection isolation between workers
- Configuration centralization
- Proper connection pool management

## Database Backend Support

The system supports multiple database backends:

```python
# Base.py
DATABASE_TYPE = env("DATABASE_TYPE")
DATABASE_NAME = env("DATABASE_NAME")
PK_TYPE = UUID if DATABASE_TYPE != "sqlite" else String
```

For SQLite:
```python
db_file = f"{DATABASE_NAME}.db"
DATABASE_URI = f"sqlite:///{db_file}"
```

For PostgreSQL:
```python
LOGIN_URI = f"{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}?sslmode={DATABASE_SSL}"
DATABASE_URI = f"postgresql://{LOGIN_URI}"
```

This dual-backend support enables:
- Development with lightweight SQLite
- Production with robust PostgreSQL
- Testing with in-memory SQLite
- Consistent application code across environments

## Connection Management Strategies

### Simple Session Factory

For basic scenarios:

```python
def get_session():
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()
    return session
```

### Advanced Session Management

For complex applications, a `DatabaseManager` singleton manages connections:

```python
class DatabaseManager:
    _instance = None
    _lock = multiprocessing.Lock()
    
    @classmethod
    def get_instance(cls) -> "DatabaseManager":
        """Get or create the singleton instance with thread-safe double-checked locking."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
```

This provides:
1. **Thread Safety**: Properly handles concurrent access
2. **Worker Isolation**: Each worker initializes its own connections
3. **Connection Pooling**: Efficient connection reuse
4. **Resource Cleanup**: Proper disposal of connections

## Synchronous and Asynchronous Support

The system supports both synchronous and asynchronous database operations:

```python
def init_worker(self) -> None:
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
```

This dual-mode support enables:
- Synchronous operations for simpler code paths
- Asynchronous operations for high-concurrency endpoints
- Consistent interface for both modes
- Gradual migration from sync to async

## Transaction Management

### Context Managers for Transactions

Synchronous transactions:

```python
@contextmanager
def _get_db_session(self, *, auto_commit: bool = True) -> Generator[Session, None, None]:
    session = self._session_factory()
    try:
        yield session
        if auto_commit:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

Asynchronous transactions:

```python
@asynccontextmanager
async def _get_async_db_session(self, *, auto_commit: bool = True) -> AsyncGenerator[AsyncSession, None]:
    async with self._async_session_factory() as session:
        try:
            yield session
            if auto_commit:
                await session.commit()
        except Exception:
            await session.rollback()
            raise
```

Benefits:
1. **Automatic Commit/Rollback**: Transactions are automatically managed
2. **Resource Cleanup**: Sessions are properly closed
3. **Exception Safety**: Rollback on exceptions
4. **Configuration**: Auto-commit can be disabled for manual control

## Connection Pooling

The system uses connection pooling for efficiency:

```python
# SQLite Configuration
self.engine_config = {
    "url": DATABASE_URI,
    "connect_args": {"check_same_thread": False},
    "pool_pre_ping": True,
    "pool_recycle": 3600,
}

# PostgreSQL Configuration
self.engine_config = {
    "url": DATABASE_URI,
    "pool_size": 20,
    "max_overflow": 10,
    "pool_pre_ping": True,
    "pool_recycle": 3600,
}
```

Key pooling parameters:
- **pool_size**: Base number of connections maintained
- **max_overflow**: Additional temporary connections allowed
- **pool_pre_ping**: Tests connections before use to avoid stale connections
- **pool_recycle**: Maximum age of connections before recycling

## Thread-Local Storage

For multi-threaded environments, thread-local storage ensures isolation:

```python
self._thread_local = local()

# Usage
if not hasattr(self._thread_local, "session"):
    self._thread_local.session = self._session_factory()
session = self._thread_local.session
```

This approach ensures:
1. **Thread Isolation**: Each thread gets its own session
2. **Connection Reuse**: Sessions are reused within a thread
3. **No Leakage**: Thread data doesn't contaminate other threads
4. **Clean Termination**: Each thread cleans up its own resources

## Database Extension Support

The system adds custom SQLite functions through engine event listeners:

```python
def setup_sqlite_for_regex(engine):
    """Register the REGEXP function with SQLite."""
    import re
    import sqlite3

    def regexp(expr, item):
        if item is None:
            return False
        try:
            reg = re.compile(expr)
            return reg.search(item) is not None
        except Exception:
            return False
            
    @event.listens_for(engine, "connect")
    def do_connect(dbapi_connection, connection_record):
        dbapi_connection.create_function("REGEXP", 2, regexp)
```

This provides:
- SQL REGEXP support in SQLite
- Consistent query capabilities across backends
- Extended functionality for text search
- Custom functions as needed

## Worker Lifecycle Management

The system manages worker connections throughout their lifecycle:

```python
def init_worker(self) -> None:
    """Initialize database connections for this worker."""
    # Setup connections for this worker
    
async def close_worker(self) -> None:
    """Clean up database connections for this worker."""
    # Close sessions and dispose engines
```

This approach ensures:
1. **Resource Efficiency**: Connections aren't created until needed
2. **Clean Shutdown**: All resources are properly released
3. **Isolation**: Each worker has its own connection pool
4. **Monitoring**: Connection lifecycle events can be logged

## FastAPI Integration

The system provides dependency injection for FastAPI:

```python
def get_db(self, auto_commit: bool = True) -> Generator[Session, None, None]:
    """FastAPI dependency for getting a database session."""
    with self._get_db_session(auto_commit=auto_commit) as session:
        yield session

async def get_async_db(self, auto_commit: bool = True) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting an async database session."""
    async with self._get_async_db_session(auto_commit=auto_commit) as session:
        yield session
```

Usage:
```python
@router.get("/items")
def list_items(db: Session = Depends(db_manager.get_db)):
    # Use db session
```

This integration:
1. **Simplifies Endpoints**: Database sessions are injected automatically
2. **Standardizes Usage**: Consistent session handling across endpoints
3. **Automatic Cleanup**: Sessions are managed through dependency lifecycle
4. **Transaction Control**: Provides auto_commit=False option for manual control

## Database Initialization

The system handles database initialization and verification:

```python
# Test the connection
connection = engine.connect()
connection.close()
```

A separate seeding system populates initial data:

```python
def seed():
    """Generic seeding function that populates the database based on seed_list attributes."""
    session = get_session()
    try:
        # Process model classes in dependency order
        for model_class in get_all_models():
            seed_model(model_class, session)
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()
```

This ensures:
1. **Verified Connections**: Early failure if database is unavailable
2. **Consistent Initial State**: Required data is populated
3. **Transactional Safety**: All-or-nothing seeding
4. **Clean Shutdown**: Resources are released properly