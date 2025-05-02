# Provider Layer Testing (`AbstractPRVTest`)

This document explains how to test server framework providers using the `AbstractPRVTest` class, located in `src/extensions/AbstractPRVTest.py`. This class provides a framework for testing the initialization, configuration, service discovery, abilities, and error handling of classes inheriting from `AbstractProvider` or `AbstractAPIProvider`.

## Core Concepts

- **Inheritance**: Test classes for providers inherit from `AbstractPRVTest`.
- **Configuration**: Each test class specifies the provider it tests (`provider_class`), a default `extension_id`, default initialization parameters (`provider_init_params`), and lists of expected abilities and services.
- **Fixtures**: Provides fixtures:
    - `provider`: A standard instance of the provider class.
    - `api_provider`: An instance initialized with dummy API key/URI (only if the provider inherits from `AbstractAPIProvider`).
    - `temp_workspace`: A temporary directory for testing workspace-related methods.
- **Initialization Testing**: Verifies core attributes (`extension_id`, `friendly_name`, failure counters) and API-specific attributes (`api_key`, `api_uri`) are set correctly. Checks that `_configure_provider` is called.
- **Service & Ability Testing**: Tests that the `services` property returns the expected list and that `has_ability` and `get_abilities` work correctly, including handling of unsupported abilities.
- **Workspace Testing**: Tests the `safe_join` method for correct path joining and security against path traversal. Verifies the `WORKING_DIRECTORY` is created.
- **Failure Handling**: Tests the `_handle_failure` method increments the failure count and correctly raises an exception when `MAX_FAILURES` is exceeded.

## Base Class (`AbstractTest`)

`AbstractPRVTest` inherits from `AbstractTest`, which provides common test functionality:
- **Test Skipping**: Uses the `skip_tests` attribute (list of `SkippedTest` objects) and the `reason_to_skip_test(test_name)` method to skip specific tests with reasons
- **Test Categories**: Uses the `test_config` attribute with testing categories, timeouts, and other configuration settings
- **Assertion Helpers**: Provides common assertion methods like `assert_objects_equal` and `assert_has_audit_fields`
- **Setup/Teardown**: Implements common setup and teardown patterns that subclasses can extend

This inheritance provides consistent test functionality across all test layers. See `AbstractTest.py` for more details.

## Class Configuration

When creating a test class for a specific provider, configure these attributes:

```python
from extensions.providers.PRV_Example import ExampleProvider # The Provider class
from extensions.AbstractPRVTest import AbstractPRVTest

class ExampleProviderTest(AbstractPRVTest):
    # The Provider class to test
    provider_class = ExampleProvider

    # Extension ID this provider belongs to
    extension_id = "example_extension"

    # Default parameters for initializing the provider in tests
    provider_init_params = {
        # Add any required init params for ExampleProvider
        "config_value": "test"
    }

    # List of ability names expected to be registered by the provider
    expected_abilities: List[str] = ["perform_action"]

    # List of service names the provider claims to support
    expected_services: List[str] = ["example_service"]

    # Optionally skip tests (inherited from AbstractTest)
    skip_tests = [
        SkippedTest(name="test_api_provider_initialization", reason="Not an API provider")
    ]
    
    # Optional test configuration
    test_config = TestClassConfig(
        categories=[TestCategory.UNIT],
        timeout=30,
        parallel=False
    )
```

## Provided Fixtures

`AbstractPRVTest` defines these fixtures:

- `provider`: An initialized instance of the `provider_class` using `extension_id` and `provider_init_params`.
- `api_provider`: An initialized instance similar to `provider` but also including dummy `api_key` and `api_uri`. This fixture is skipped if `provider_class` does not inherit from `AbstractAPIProvider`.
- `temp_workspace`: Provides the path to a temporary directory, cleaned up after the test.

## Included Test Methods

`AbstractPRVTest` provides these standard tests:

- `test_initialization`: Checks basic provider attributes and workspace directory creation.
- `test_api_provider_initialization`: Checks API-specific attributes (`api_key`, `api_uri`, timeouts) for API providers (skipped otherwise).
- `test_configure_provider`: Verifies that the `_configure_provider` method is called during initialization.
- `test_services`: Asserts that `provider.services` returns the `expected_services`.
- `test_register_unsupported_ability`: Tests marking an ability as unsupported and verifies `has_ability` reflects this.
- `test_has_ability`: Tests `has_ability` with non-existent, expected, and unsupported abilities.
- `test_get_abilities`: Checks that `get_abilities` returns a dictionary.
- `test_safe_join`: Tests the `safe_join` method with normal paths, prefixed paths, and path traversal attempts.
- `test_handle_failure`: Tests the `_handle_failure` method increments the failure count and raises an exception upon reaching `MAX_FAILURES`.
- `test_get_extension_info`: Checks that `get_extension_info` returns a dictionary with expected keys.
- `test_workspace_directory`: Verifies the `WORKING_DIRECTORY` attribute exists and points to a valid directory.
- `test_custom_working_directory`: Tests initializing the provider with a custom `conversation_directory`.

## Testing Provider-Specific Abilities

The standard tests focus on the `AbstractProvider` framework. To test the actual implementation of your provider's abilities (the methods registered in the `abilities` dictionary), you should:

1.  Add custom async test methods to your specific provider test class.
2.  Use the `provider` fixture.
3.  Call the ability method directly or via `provider.execute_ability`.
4.  Mock any external dependencies (like API clients) using `unittest.mock.patch`.
5.  Assert the expected results and side effects.

```python
import asyncio
from unittest.mock import patch, AsyncMock

# In ExampleProviderTest class
@patch("extensions.providers.PRV_Example.ApiClient") # Mock external client
async def test_perform_action_ability(self, MockApiClient, provider):
    test_name = "test_perform_action_ability"
    if self.reason_to_skip_test(test_name):
        return

    # Configure the mock client
    mock_instance = MockApiClient.return_value
    mock_instance.do_something = AsyncMock(return_value={"status": "ok"})

    # Get the ability function (or call execute_ability)
    perform_action_func = provider.abilities.get("perform_action")
    assert perform_action_func is not None

    # Call the ability
    result = await perform_action_func(input_data="test")

    # Assert results and mock calls
    assert result["status"] == "ok"
    mock_instance.do_something.assert_called_once_with(data="test")
``` 