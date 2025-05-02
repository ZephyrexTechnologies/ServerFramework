# Service Layer Patterns & Best Practices

> **Note:** For comprehensive documentation on the Service Layer abstractions, including AbstractService, please refer to [BLL.Abstraction.md](BLL.Abstraction.md#service-layer-abstractservice).

Services (`SVC_*.py`) in the framework represent long-running background processes or tasks that operate independently of direct API requests. They often perform periodic actions, maintenance, or interact with external systems asynchronously.

## Core Structure (`AbstractService`)

All services inherit from `AbstractService` (located in `src/services/AbstractService.py`). This base class provides a standardized structure and lifecycle management for services.

### Key Components:

- **`__init__(...)`**: Initializes the service, setting up essential attributes like the run interval, failure thresholds, database session handling, and a unique service ID.
- **`requester_id`**: Services operate under a specific user context, typically the `SYSTEM_ID` or a dedicated service user ID, provided during initialization.
- **`db` Property**: Provides access to a SQLAlchemy database session. The service can manage its own session or use one provided externally.
- **`interval_seconds`**: Defines how often the service's main logic (`update` method) should run.
- **`max_failures` / `retry_delay_seconds`**: Control the service's resilience by defining how many consecutive failures are allowed before stopping and how long to wait before retrying after a failure.
- **`running` / `paused` Flags**: Control the service's execution state.
- **`_configure_service()`**: An abstract method intended for subclasses to perform one-time setup specific to the service during initialization.
- **`update()`**: An abstract async method containing the core logic that the service performs repeatedly.
- **`run_service_loop()`**: The main async loop that manages the service's execution, including handling the interval, pausing, error handling, and retries.
- **Lifecycle Methods**: `start()`, `stop()`, `pause()`, `resume()`, `cleanup()` allow external control over the service's state.
- **Error Handling**: The loop automatically catches exceptions during `update()`, logs them, increments a failure counter (`failures`), and implements the retry/max failure logic using `_handle_failure()`.
- **`_reset_failures()`**: Called upon a successful `update()` execution to reset the failure counter.

### Service Implementation Pattern:

```python
import asyncio
import logging
from sqlalchemy.orm import Session

from services.AbstractService import AbstractService

logger = logging.getLogger(__name__)

class ExampleService(AbstractService):
    """An example background service."""

    def _configure_service(self) -> None:
        """Perform one-time setup for the service."""
        logger.info(f"Configuring ExampleService ({self.service_id})")
        # Example: Load configuration, initialize clients, etc.
        self.some_client = ...

    async def update(self) -> None:
        """Core logic performed by the service periodically."""
        logger.debug(f"ExampleService ({self.service_id}) executing update...")
        
        # Use self.db for database operations
        # session = self.db
        # items = session.query(SomeModel).filter(...).all()

        # Perform actions...
        # await self.some_client.process(items)
        
        # Simulate work
        await asyncio.sleep(0.5)

        logger.debug(f"ExampleService ({self.service_id}) update finished.")

    def cleanup(self) -> None:
        """Perform cleanup when the service stops."""
        super().cleanup() # Ensure parent cleanup runs
        logger.info(f"Cleaning up ExampleService ({self.service_id})")
        # Example: Close connections, release resources
        # if self.some_client:
        #     self.some_client.close()
```

## Service Management

Services are typically instantiated and managed by a central service registry or manager (implementation details depend on the application's entry point and structure). This registry would be responsible for starting, stopping, and monitoring the health of registered services.

## Best Practices

1.  **Idempotency**: Design the `update` logic to be idempotent where possible, meaning running it multiple times with the same initial state produces the same end state. This makes recovery from failures easier.
2.  **Error Handling**: Catch specific exceptions within `update` if custom handling is needed beyond the base class's retry logic. Re-raise exceptions if the base class should handle the failure/retry.
3.  **Resource Management**: Use the `db` property for database access. Ensure any other resources (network connections, file handles) are properly managed and released in the `cleanup` method.
4.  **Configuration**: Load service-specific configuration (e.g., API keys, external URLs) during `_configure_service` using the environment or a configuration manager.
5.  **Logging**: Implement clear and informative logging within `_configure_service`, `update`, and `cleanup` to aid debugging and monitoring.
6.  **Concurrency**: Be mindful of potential race conditions if the service interacts with data that might also be modified by API requests or other services. Use appropriate database locking or transactional patterns.
7.  **Interval**: Choose a reasonable `interval_seconds` based on the task's requirements and the expected load. 