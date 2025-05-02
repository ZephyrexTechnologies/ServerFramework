# Extension Layer Testing (`AbstractEXTTest`)

This document describes testing server framework extensions using the `AbstractEXTTest` class, located in `src/extensions/AbstractEXTTest.py`. This class provides a framework for testing the initialization, dependency management, component loading, and core functionalities (hooks, abilities) of classes inheriting from `AbstractExtension`.

## Core Concepts

- **Inheritance**: Test classes for extensions inherit from `AbstractEXTTest`.
- **Configuration**: Each test class specifies the extension it tests (`extension_class`) and lists expected components like providers, DB tables, BLL managers, EP routers, abilities, and dependencies.
- **Fixtures**: Provides an `extension` fixture, which is an initialized instance of the configured `extension_class`.
- **Component Verification**: Includes tests to verify that the extension correctly declares its name, version, description, dependencies, and initializes its internal component collections (providers, abilities, etc.).
- **Dependency Testing**: Tests the `check_dependencies` and `resolve_dependencies` static methods for validating and ordering extension loading based on declared dependencies.
- **Hook and Ability Testing**: Verifies the registration and execution mechanisms for hooks (`register_hook`, `trigger_hook`) and abilities (`execute_ability`, `_get_ability_args`).

## Base Class (`AbstractTest`)

`AbstractEXTTest` inherits from `AbstractTest`, which provides common test functionality:
- **Test Skipping**: Uses the `skip_tests` attribute (list of `SkippedTest` objects) and the `reason_to_skip_test(test_name)` method to skip specific tests with reasons
- **Test Categories**: Uses the `test_config` attribute with testing categories, timeouts, and other configuration settings
- **Assertion Helpers**: Provides common assertion methods like `assert_objects_equal` and `assert_has_audit_fields`
- **Setup/Teardown**: Implements common setup and teardown patterns that subclasses can extend

This inheritance provides consistent test functionality across all test layers. See `AbstractTest.py` for more details.

## Class Configuration

When creating a test class for a specific extension, configure these attributes:

```python
from extensions.EXT_Example import ExampleExtension # The Extension class
from extensions.AbstractEXTTest import AbstractEXTTest
from AbstractExtension import EXT_Dependency, PIP_Dependency, APT_Dependency

class ExampleExtensionTest(AbstractEXTTest):
    # The Extension class to test
    extension_class = ExampleExtension

    # Expected component names (or identifiers)
    expected_providers: List[str] = ["ExampleProvider"]
    expected_db_tables: List[str] = ["example_entities"]
    expected_bll_managers: List[str] = ["ExampleEntityManager"]
    expected_ep_routers: List[str] = ["/v1/example"]
    expected_abilities: List[str] = ["do_example_thing"]

    # Expected dependencies declared by the extension class
    expected_dependencies = [
        # Example: {"name": "core", "optional": False, ...}
        # Matches the structure used in AbstractExtension dependency lists
    ]

    # Optionally skip tests (inherited from AbstractTest)
    skip_tests = [
        SkippedTest(name="test_resolve_dependencies", reason="Dependency logic covered elsewhere")
    ]
    
    # Optional test configuration
    test_config = TestClassConfig(
        categories=[TestCategory.UNIT],
        timeout=30,
        parallel=False
    )
```

## Provided Fixtures

`AbstractEXTTest` defines these fixtures:

- `extension`: An initialized instance of the `extension_class` under test.
- `mock_database`: A `MagicMock` object simulating a database session (used in some tests).

It also has access to fixtures provided by `conftest.py`, such as `db_session` and `requester_id`.

## Included Test Methods

`AbstractEXTTest` provides these standard tests:

- `test_initialization`: Checks basic attributes (`name`, `version`, etc.) and ensures component collections (lists/dicts for providers, abilities, etc.) are initialized.
- `test_dependencies`: Verifies the structure and types of the extension's declared dependency lists (`ext_dependencies`, `pip_dependencies`, `apt_dependencies`).
- `test_check_dependencies`: Tests the static `check_dependencies` method with various scenarios (satisfied, unsatisfied, missing, optional dependencies).
- `test_resolve_dependencies`: Tests the static `resolve_dependencies` method for correctly ordering extensions based on dependencies and detecting circular dependencies.
- `test_load_db_tables`: Tests the dynamic loading of database table classes (requires mocking `importlib`).
- `test_load_providers`: Checks that the `providers` list is initialized (actual loading involves dynamic imports).
- `test_register_hook`: Verifies that `register_hook` correctly adds a handler to the `registered_hooks` dictionary.
- `test_trigger_hook`: Registers a test hook and verifies that `trigger_hook` executes it and returns the result. Also tests triggering a non-existent hook.
- `test_execute_ability`: Registers a test ability and verifies `execute_ability` runs it correctly with default and custom arguments. Also tests executing a non-existent ability.
- `test_get_ability_args`: Tests the internal `_get_ability_args` helper method for correctly extracting argument names and default values from an ability function signature.
- `test_discover_extensions`: Checks that the static `discover_extensions` method exists and returns a list (requires mocking filesystem operations).

## Testing Extension-Specific Logic

The standard tests focus on the `AbstractExtension` framework. To test logic specific to your extension (e.g., custom methods, interactions between its components), add new test methods to your test class and use the `extension` fixture.

```python
# In ExampleExtensionTest class
async def test_example_custom_functionality(self, extension):
    test_name = "test_example_custom_functionality"
    if self.reason_to_skip_test(test_name):
        return

    # Assuming ExampleExtension has a custom method
    result = await extension.perform_custom_action(param="test")

    # Assert expected outcome
    assert result == "expected_result"

    # Or test interaction with a registered ability
    ability_result = await extension.execute_ability("do_example_thing", {"arg": 123})
    assert "123" in ability_result
``` 