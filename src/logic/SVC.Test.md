# Service Layer Testing (`AbstractSVCTest`)

> **Note:** For comprehensive documentation on testing the Service Layer, including AbstractSVCTest, please refer to [BLL.Abstraction.md](BLL.Abstraction.md#service-layer-testing-abstractsvctest).

This document explains how to test background services using the `AbstractSVCTest` class, located in `src/logic/AbstractSVCTest.py`. This class focuses on testing the lifecycle, execution loop, error handling, and configuration of services inheriting from `AbstractService`.

## Core Concepts

- **Inheritance**: Test classes for services inherit from `AbstractSVCTest`.
- **Configuration**: Each test class specifies the service it tests (`service_class`) and default initialization parameters (`service_init_params`). Mock parameters (`mock_init_params`) can be provided for the `mocked_service` fixture.
- **Fixtures**: Provides two main fixtures:
    - `service`: A standard instance of the service class.
    - `mocked_service`: An instance where the `update` method and potentially other dependencies (defined via `_get_mocks`) are mocked using `unittest.mock`. This is useful for testing the service loop and error handling without executing the actual service logic.
- **Lifecycle Testing**: Includes tests verifying the behavior of `start()`, `stop()`, `pause()`, and `resume()`.
- **Execution Testing**: Tests that the service loop (`run_service_loop`) correctly calls the `update` method repeatedly when running and not paused.
- **Error Handling**: Tests the service's resilience by simulating errors in the `update` method and verifying retry logic and the `max_failures` mechanism.
- **Asynchronous**: Tests are designed to work with the `asyncio` event loop, as services are asynchronous.

## Base Class (`AbstractTest`)

`AbstractSVCTest` inherits from `testing.AbstractTest.AbstractTest`, providing access to the common test skipping functionality (`skip_tests` attribute and `reason_to_skip_test` method). See `testing/Framework.Test.md` for more details.

## Class Configuration

When creating a test class for a specific service, configure these attributes:

```python
from services.SVC_Example import ExampleService # The Service class
from logic.AbstractSVCTest import AbstractSVCTest
from unittest.mock import MagicMock

class ExampleServiceTest(AbstractSVCTest):
    # The Service class to test
    service_class = ExampleService

    # Default parameters for initializing the service in tests
    service_init_params = {
        "interval_seconds": 0.1, # Use short interval for testing
        "max_failures": 3,
        "retry_delay_seconds": 0.1,
        # Add any other required init params for ExampleService
    }

    # Optional: Parameters only for the mocked_service fixture
    mock_init_params = {
        "mock_dependency": MagicMock()
    }

    # Optionally skip tests (inherited from AbstractTest)
    skip_tests = [
        # SkippedTest(name="test_max_failures", reason="Specific failure condition not applicable")
    ]

    # Optional: Override to provide specific mocks for mocked_service
    def _get_mocks(self) -> Dict[str, MagicMock]:
        return {
            "external_api_call": MagicMock(return_value=True)
        }
```

## Provided Fixtures

`AbstractSVCTest` uses fixtures provided by `conftest.py`:

- `db_session`: An active SQLAlchemy session.
- `requester_id`: A standard UUID string used to initialize the service.

It also defines its own fixtures:

- `service`: A standard instance of the `service_class`.
- `mocked_service`: An instance of the `service_class` where `update` is an `AsyncMock`, and other mocks defined in `_get_mocks` are applied. Useful for testing the service's control flow without running its core logic.

## Included Test Methods

`AbstractSVCTest` provides these standard tests (most require `asyncio` and use the `mocked_service` fixture):

- `test_service_lifecycle`: Checks the `running` and `paused` flags after calling `start`, `stop`, `pause`, `resume`.
- `test_run_service_loop`: Runs the service loop briefly and asserts that the mocked `update` method was called.
- `test_error_handling`: Configures the mocked `update` to raise exceptions and verifies that the failure count increases and retries occur.
- `test_max_failures`: Configures the mocked `update` to raise exceptions and verifies that the service stops running after exceeding `max_failures`.
- `test_pause_resume`: Verifies that the mocked `update` is not called while paused but is called after resuming.
- `test_cleanup`: Calls the `cleanup` method and asserts the service is no longer running.
- `test_db_property`: Checks that the `service.db` property provides an active database session.
- `test_reset_failures`: Checks that `_reset_failures` correctly resets the failure counter.
- `test_handle_failure`: Checks that `_handle_failure` increments the failure count and correctly handles the max failure condition.
- `test_configure_service`: Checks that the `_configure_service` method (intended for subclass implementation) is called during initialization.

## Testing Actual Service Logic

The standard tests primarily focus on the `AbstractService` framework itself using the `mocked_service`. To test the actual logic within your service's `update` method, you should:

1.  Add custom test methods to your specific service test class.
2.  Use the standard `service` fixture (not the `mocked_service`).
3.  Call `await service.update()` directly within your test method.
4.  Assert the expected side effects (database changes, interactions with external systems via mocks if necessary).

```python
# In ExampleServiceTest class
async def test_example_update_logic(self, service):
    test_name = "test_example_update_logic"
    if self.reason_to_skip_test(test_name):
        return

    # Setup initial state in the database if needed
    # ...

    # Call the actual update method
    await service.update()

    # Assert that the expected changes occurred
    # e.g., check database state, check mock calls
    # ...
``` 