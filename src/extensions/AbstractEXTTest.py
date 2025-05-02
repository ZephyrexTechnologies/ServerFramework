import logging
import uuid
from typing import Any, Dict, List, Type, TypeVar
from unittest.mock import MagicMock, patch

import pytest
from AbstractExtension import (
    AbstractExtension,
    APT_Dependency,
    EXT_Dependency,
    PIP_Dependency,
)

from AbstractTest import AbstractTest  # Import the new base class

# Type variable for extension class
T = TypeVar("T", bound=AbstractExtension)

# Set up logging
logger = logging.getLogger(__name__)


# Remove SkippedTest class definition
# class SkippedTest(BaseModel):
#     """Model for a skipped test with a reason."""
#
#     name: str
#     reason: str


# Inherit from AbstractTest
class AbstractEXTTest(AbstractTest):
    """
    Abstract base class for testing extension components.

    Provides a structured framework for testing extensions that implement
    the AbstractExtension interface, with tests for component loading,
    dependency resolution, hook management, and extension-specific functionality.

    Features:
    - Extension initialization testing
    - Component loading testing
    - Dependency resolution testing
    - Hook registration and execution testing
    - Ability registration and execution testing

    To use this class, extend it and override the class attributes and methods
    as needed for your specific extension.
    """

    # Class to be tested
    extension_class: Type[T] = None

    # Expected providers
    expected_providers: List[str] = []

    # Expected database tables
    expected_db_tables: List[str] = []

    # Expected business logic managers
    expected_bll_managers: List[str] = []

    # Expected endpoint routers
    expected_ep_routers: List[str] = []

    # Expected abilities
    expected_abilities: List[str] = []

    # Expected dependencies
    expected_dependencies: List[Dict[str, Any]] = []

    # Tests to skip - Inherited from AbstractTest
    # skip_tests: List[SkippedTest] = []

    # Remove reason_to_skip_test method - Inherited from AbstractTest
    # def reason_to_skip_test(self, test_name: str) -> bool:
    #     """Check if a test should be skipped based on the skip_tests list."""
    #     for skip in self.skip_tests:
    #         if skip.name == test_name:
    #             pytest.skip(skip.reason)
    #             return True
    #     return False

    @pytest.fixture
    def extension(self) -> AbstractExtension:
        """
        Create an extension instance for testing.

        Returns:
            An instance of the extension class being tested
        """
        if not self.extension_class:
            pytest.skip("extension_class not defined, test cannot run")

        # Mock imports that might be needed for extension initialization
        with patch("importlib.import_module") as mock_import:
            # Mock return value for import_module
            mock_module = MagicMock()
            mock_import.return_value = mock_module

            # Initialize the extension
            extension = self.extension_class()

            return extension

    @pytest.fixture
    def mock_database(self) -> MagicMock:
        """
        Create a mock database for testing.

        Returns:
            Mock database object
        """
        # Create a mock database
        mock_db = MagicMock()

        # Mock query method
        mock_db.query.return_value = mock_db
        mock_db.filter.return_value = mock_db
        mock_db.first.return_value = None

        return mock_db

    def test_initialization(self, extension):
        """Test extension initialization."""
        test_name = "test_initialization"
        if self.reason_to_skip(test_name):
            return

        # Check basic extension attributes
        assert hasattr(extension, "name"), "Extension should have name attribute"
        assert hasattr(extension, "version"), "Extension should have version attribute"
        assert hasattr(
            extension, "description"
        ), "Extension should have description attribute"

        # Check component collections
        assert hasattr(extension, "providers"), "Extension should have providers list"
        assert hasattr(
            extension, "abilities"
        ), "Extension should have abilities dictionary"
        assert hasattr(extension, "db_classes"), "Extension should have db_classes list"
        assert hasattr(
            extension, "bll_managers"
        ), "Extension should have bll_managers dictionary"
        assert hasattr(
            extension, "ep_routers"
        ), "Extension should have ep_routers dictionary"

        # Check provider class
        assert hasattr(
            extension, "ProviderCLS"
        ), "Extension should have ProviderCLS attribute"

    def test_dependencies(self, extension):
        """Test extension dependencies."""
        test_name = "test_dependencies"
        if self.reason_to_skip(test_name):
            return

        # Check dependency lists
        assert hasattr(
            extension.__class__, "ext_dependencies"
        ), "Extension should have ext_dependencies list"
        assert isinstance(
            extension.__class__.ext_dependencies, list
        ), "ext_dependencies should be a list"

        assert hasattr(
            extension.__class__, "pip_dependencies"
        ), "Extension should have pip_dependencies list"
        assert isinstance(
            extension.__class__.pip_dependencies, list
        ), "pip_dependencies should be a list"

        assert hasattr(
            extension.__class__, "apt_dependencies"
        ), "Extension should have apt_dependencies list"
        assert isinstance(
            extension.__class__.apt_dependencies, list
        ), "apt_dependencies should be a list"

        # Check dependency structure
        for dependency in extension.__class__.ext_dependencies:
            assert isinstance(
                dependency, EXT_Dependency
            ), "Extension dependency should be an EXT_Dependency"
            assert hasattr(dependency, "name"), "Dependency should have name attribute"
            assert hasattr(
                dependency, "friendly_name"
            ), "Dependency should have friendly_name attribute"
            assert hasattr(
                dependency, "optional"
            ), "Dependency should have optional attribute"
            assert hasattr(
                dependency, "reason"
            ), "Dependency should have reason attribute"

        for dependency in extension.__class__.pip_dependencies:
            assert isinstance(
                dependency, PIP_Dependency
            ), "PIP dependency should be a PIP_Dependency"

        for dependency in extension.__class__.apt_dependencies:
            assert isinstance(
                dependency, APT_Dependency
            ), "APT dependency should be an APT_Dependency"

    def test_check_dependencies(self, extension):
        """Test check_dependencies method."""
        test_name = "test_check_dependencies"
        if self.reason_to_skip(test_name):
            return

        # Create a test loaded_extensions dictionary
        loaded_extensions = {"test_extension_1": "1.0.0", "test_extension_2": "2.0.0"}

        # Add a test dependency
        test_dependency = EXT_Dependency(
            name="test_extension_1",
            friendly_name="Test Extension 1",
            optional=False,
            reason="Testing dependency checking",
            semver=">=1.0.0",
        )

        # Temporarily add the test dependency to ext_dependencies
        original_dependencies = extension.__class__.ext_dependencies
        extension.__class__.ext_dependencies = [test_dependency]

        try:
            # Check dependencies
            dependency_status = extension.__class__.check_dependencies(
                loaded_extensions
            )

            # Test dependency should be satisfied
            assert (
                "test_extension_1" in dependency_status
            ), "Dependency should be in status dictionary"
            assert dependency_status[
                "test_extension_1"
            ], "Dependency should be satisfied"

            # Test with unsatisfied dependency
            loaded_extensions = {"test_extension_1": "0.5.0"}  # Version too low

            dependency_status = extension.__class__.check_dependencies(
                loaded_extensions
            )

            # Now the dependency should not be satisfied
            assert (
                "test_extension_1" in dependency_status
            ), "Dependency should be in status dictionary"
            assert not dependency_status[
                "test_extension_1"
            ], "Dependency should not be satisfied"

            # Test with missing dependency
            loaded_extensions = {}

            dependency_status = extension.__class__.check_dependencies(
                loaded_extensions
            )

            # Dependency should not be satisfied
            assert (
                "test_extension_1" in dependency_status
            ), "Dependency should be in status dictionary"
            assert not dependency_status[
                "test_extension_1"
            ], "Dependency should not be satisfied"

            # Test with optional dependency
            test_dependency.optional = True

            dependency_status = extension.__class__.check_dependencies(
                loaded_extensions
            )

            # Optional dependency should be satisfied even if missing
            assert (
                "test_extension_1" in dependency_status
            ), "Dependency should be in status dictionary"
            assert dependency_status[
                "test_extension_1"
            ], "Optional dependency should be satisfied even if missing"
        finally:
            # Restore original dependencies
            extension.__class__.ext_dependencies = original_dependencies

    def test_resolve_dependencies(self, extension):
        """Test resolve_dependencies method."""
        test_name = "test_resolve_dependencies"
        if self.reason_to_skip(test_name):
            return

        # Create some test extension classes
        class TestExtension1(AbstractExtension):
            name = "test_extension_1"
            version = "1.0.0"
            description = "Test Extension 1"
            ext_dependencies = []

        class TestExtension2(AbstractExtension):
            name = "test_extension_2"
            version = "1.0.0"
            description = "Test Extension 2"
            ext_dependencies = [
                EXT_Dependency(
                    name="test_extension_1",
                    friendly_name="Test Extension 1",
                    optional=False,
                    reason="Required dependency",
                )
            ]

        class TestExtension3(AbstractExtension):
            name = "test_extension_3"
            version = "1.0.0"
            description = "Test Extension 3"
            ext_dependencies = [
                EXT_Dependency(
                    name="test_extension_2",
                    friendly_name="Test Extension 2",
                    optional=False,
                    reason="Required dependency",
                )
            ]

        # Create available extensions dictionary
        available_extensions = {
            "test_extension_1": TestExtension1,
            "test_extension_2": TestExtension2,
            "test_extension_3": TestExtension3,
        }

        # Resolve dependencies
        loading_order = extension.__class__.resolve_dependencies(available_extensions)

        # Check that the order is correct
        assert (
            "test_extension_1" in loading_order
        ), "Extension 1 should be in loading order"
        assert (
            "test_extension_2" in loading_order
        ), "Extension 2 should be in loading order"
        assert (
            "test_extension_3" in loading_order
        ), "Extension 3 should be in loading order"

        # Extension 1 should come before Extension 2
        assert loading_order.index("test_extension_1") < loading_order.index(
            "test_extension_2"
        ), "Extension 1 should come before Extension 2"

        # Extension 2 should come before Extension 3
        assert loading_order.index("test_extension_2") < loading_order.index(
            "test_extension_3"
        ), "Extension 2 should come before Extension 3"

        # Test circular dependency detection
        class CircularExtension1(AbstractExtension):
            name = "circular_1"
            version = "1.0.0"
            description = "Circular Extension 1"
            ext_dependencies = [
                EXT_Dependency(
                    name="circular_2",
                    friendly_name="Circular Extension 2",
                    optional=False,
                    reason="Circular dependency",
                )
            ]

        class CircularExtension2(AbstractExtension):
            name = "circular_2"
            version = "1.0.0"
            description = "Circular Extension 2"
            ext_dependencies = [
                EXT_Dependency(
                    name="circular_1",
                    friendly_name="Circular Extension 1",
                    optional=False,
                    reason="Circular dependency",
                )
            ]

        # Create circular available extensions dictionary
        circular_extensions = {
            "circular_1": CircularExtension1,
            "circular_2": CircularExtension2,
        }

        # Resolving should raise ValueError due to circular dependency
        with pytest.raises(ValueError):
            extension.__class__.resolve_dependencies(circular_extensions)

    def test_load_db_tables(self, extension):
        """Test load_db_tables method."""
        test_name = "test_load_db_tables"
        if self.reason_to_skip(test_name):
            return

        # Test requires patching importlib.import_module
        with patch("importlib.import_module") as mock_import:
            # Create a mock module with mock Base classes
            mock_module = MagicMock()

            # Create a mock Base class
            from database.Base import Base

            class MockTable1(Base):
                __tablename__ = "mock_table_1"

            class MockTable2(Base):
                __tablename__ = "mock_table_2"

            # Add mock tables to the mock module
            mock_module.MockTable1 = MockTable1
            mock_module.MockTable2 = MockTable2

            # Set up the import_module mock to return our mock module
            mock_import.return_value = mock_module

            # Clear existing tables
            extension.__class__.db_tables = []

            # Call load_db_tables
            extension.__class__.load_db_tables()

            # Check that the tables were loaded
            assert len(extension.__class__.db_tables) > 0, "DB tables should be loaded"

    def test_load_providers(self, extension):
        """Test _load_providers method."""
        test_name = "test_load_providers"
        if self.reason_to_skip(test_name):
            return

        # This test is tricky because it involves dynamic imports
        # We'll focus on checking that the provider list exists and is the expected type
        assert hasattr(extension, "providers"), "Extension should have providers list"
        assert isinstance(extension.providers, list), "Providers should be a list"

    def test_register_hook(self, extension):
        """Test register_hook method."""
        test_name = "test_register_hook"
        if self.reason_to_skip(test_name):
            return

        # Create a test hook handler
        def test_hook_handler(*args, **kwargs):
            return "Test hook handler called"

        # Create a unique hook path
        layer = "BLL"
        domain = f"Test_Domain_{uuid.uuid4()}"
        entity = "TestEntity"
        function = "get"
        time = "before"

        hook_path = (layer, domain, entity, function, time)

        # Register the hook
        extension.__class__.register_hook(
            layer, domain, entity, function, time, test_hook_handler
        )

        # Check that the hook was registered
        assert (
            hook_path in extension.__class__.registered_hooks
        ), "Hook should be registered"
        assert (
            test_hook_handler in extension.__class__.registered_hooks[hook_path]
        ), "Hook handler should be in registered hooks"

        # Clean up after the test
        extension.__class__.registered_hooks.pop(hook_path, None)

    def test_trigger_hook(self, extension):
        """Test trigger_hook method."""
        test_name = "test_trigger_hook"
        if self.reason_to_skip(test_name):
            return

        # Create a test hook handler
        test_result = f"Test result {uuid.uuid4()}"

        def test_hook_handler(*args, **kwargs):
            return test_result

        # Create a unique hook path
        layer = "BLL"
        domain = f"Test_Domain_{uuid.uuid4()}"
        entity = "TestEntity"
        function = "get"
        time = "before"

        hook_path = (layer, domain, entity, function, time)

        # Register the hook
        extension.__class__.register_hook(
            layer, domain, entity, function, time, test_hook_handler
        )

        try:
            # Trigger the hook
            results = extension.__class__.trigger_hook(
                layer, domain, entity, function, time
            )

            # Check the results
            assert len(results) == 1, "Hook should return one result"
            assert results[0] == test_result, "Hook result should match test result"

            # Trigger a hook that doesn't exist
            nonexistent_hook_path = (
                layer,
                f"Nonexistent_Domain_{uuid.uuid4()}",
                entity,
                function,
                time,
            )
            results = extension.__class__.trigger_hook(*nonexistent_hook_path)

            # Should return an empty list
            assert results == [], "Nonexistent hook should return empty list"
        finally:
            # Clean up after the test
            extension.__class__.registered_hooks.pop(hook_path, None)

    def test_execute_ability(self, extension):
        """Test execute_ability method."""
        test_name = "test_execute_ability"
        if self.reason_to_skip(test_name):
            return

        # Create a test ability
        ability_name = f"test_ability_{uuid.uuid4()}"
        ability_result = f"Test ability result {uuid.uuid4()}"

        async def test_ability_func(arg1="default", arg2=None):
            return f"{ability_result} {arg1} {arg2}"

        # Register the ability
        extension.abilities[ability_name] = test_ability_func

        # Test executing the ability
        import asyncio

        # Execute with default arguments
        result = asyncio.run(extension.execute_ability(ability_name))
        assert ability_result in result, "Ability result should contain expected value"

        # Execute with custom arguments
        result = asyncio.run(
            extension.execute_ability(
                ability_name, {"arg1": "custom1", "arg2": "custom2"}
            )
        )
        assert "custom1" in result, "Ability result should contain custom arg1"
        assert "custom2" in result, "Ability result should contain custom arg2"

        # Execute nonexistent ability
        result = asyncio.run(
            extension.execute_ability(f"nonexistent_ability_{uuid.uuid4()}")
        )
        assert (
            "not found" in result
        ), "Nonexistent ability should return 'not found' message"

    def test_get_ability_args(self, extension):
        """Test _get_ability_args method."""
        test_name = "test_get_ability_args"
        if self.reason_to_skip(test_name):
            return

        # Create a test ability function
        async def test_ability_func(arg1="default1", arg2="default2", arg3=None):
            return "Test ability result"

        # Get ability args
        args = extension._get_ability_args(test_ability_func)

        # Check the args
        assert isinstance(args, dict), "Ability args should be a dictionary"
        assert "arg1" in args, "Args should include arg1"
        assert args["arg1"] == "default1", "arg1 should have correct default value"
        assert "arg2" in args, "Args should include arg2"
        assert args["arg2"] == "default2", "arg2 should have correct default value"
        assert "arg3" in args, "Args should include arg3"
        assert args["arg3"] is None, "arg3 should have correct default value"

    def test_discover_extensions(self, extension):
        """Test discover_extensions method."""
        test_name = "test_discover_extensions"
        if self.reason_to_skip(test_name):
            return

        # This test is tricky because it involves file system operations
        # We'll just check that the method exists and returns a list
        with patch("os.path.isdir", return_value=True):
            with patch("os.listdir", return_value=[]):
                extensions = extension.__class__.discover_extensions()
                assert isinstance(
                    extensions, list
                ), "discover_extensions should return a list"
