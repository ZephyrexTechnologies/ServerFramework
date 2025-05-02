import logging
import os
import tempfile
import uuid
from typing import Any, Dict, List, Optional, Type, TypeVar
from unittest.mock import patch

import pytest
from AbstractProvider import AbstractAPIProvider, AbstractProvider

from AbstractTest import AbstractTest  # Import the new base class

# Type variable for provider class
T = TypeVar("T", bound=AbstractProvider)

# Set up logging
logger = logging.getLogger(__name__)


# Remove SkippedTest class definition
# class SkippedTest(BaseModel):
#     """Model for a skipped test with a reason."""
#
#     name: str
#     reason: str


# Inherit from AbstractTest
class AbstractPRVTest(AbstractTest):
    """
    Abstract base class for testing provider components.

    Provides a structured framework for testing providers that implement
    the AbstractProvider interface, with tests for ability registration,
    service discovery, error handling, and provider-specific functionality.

    Features:
    - Provider initialization testing
    - Ability registration and execution testing
    - Service detection testing
    - Path handling testing
    - Failure handling testing

    To use this class, extend it and override the class attributes and methods
    as needed for your specific provider.
    """

    # Class to be tested
    provider_class: Type[T] = None

    # Extension ID for the provider
    extension_id: str = "test_extension"

    # Default provider initialization parameters
    provider_init_params: Dict[str, Any] = {}

    # Expected abilities
    expected_abilities: List[str] = []

    # Expected services
    expected_services: List[str] = []

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
    def provider(self) -> AbstractProvider:
        """
        Create a provider instance for testing.

        Returns:
            An instance of the provider class being tested
        """
        if not self.provider_class:
            pytest.skip("provider_class not defined, test cannot run")

        # Initialize the provider
        provider = self.provider_class(
            extension_id=self.extension_id, **self.provider_init_params
        )

        return provider

    @pytest.fixture
    def api_provider(self) -> Optional[AbstractAPIProvider]:
        """
        Create an API provider instance for testing if applicable.

        Returns:
            An instance of the API provider class or None if not applicable
        """
        if not self.provider_class:
            pytest.skip("provider_class not defined, test cannot run")

        if not issubclass(self.provider_class, AbstractAPIProvider):
            pytest.skip("Provider class is not an API provider, test cannot run")

        # Initialize the API provider
        api_provider = self.provider_class(
            extension_id=self.extension_id,
            api_key="test_api_key",
            api_uri="https://test.api.example.com",
            **self.provider_init_params,
        )

        return api_provider

    @pytest.fixture
    def temp_workspace(self) -> str:
        """
        Create a temporary directory for workspace testing.

        Returns:
            Path to temporary directory
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    def test_initialization(self, provider):
        """Test provider initialization."""
        test_name = "test_initialization"
        if self.reason_to_skip(test_name):
            return

        # Check basic provider attributes
        assert provider.extension_id == self.extension_id, "Extension ID mismatch"
        assert provider.friendly_name is not None, "Friendly name should be set"
        assert provider.failures == 0, "Initial failures should be 0"
        assert hasattr(
            provider, "MAX_FAILURES"
        ), "Provider should have MAX_FAILURES defined"
        assert hasattr(
            provider, "unsupported_capabilities"
        ), "Provider should have unsupported_capabilities"
        assert hasattr(
            provider, "abilities"
        ), "Provider should have abilities dictionary"

        # Check working directory
        assert hasattr(
            provider, "WORKING_DIRECTORY"
        ), "Provider should have WORKING_DIRECTORY"
        assert os.path.exists(
            provider.WORKING_DIRECTORY
        ), "Working directory should exist"

    def test_api_provider_initialization(self, api_provider):
        """Test API provider initialization."""
        test_name = "test_api_provider_initialization"
        if self.reason_to_skip(test_name):
            return

        if not api_provider:
            return

        # Check API provider specific attributes
        assert hasattr(api_provider, "api_key"), "API provider should have api_key"
        assert api_provider.api_key == "test_api_key", "API key mismatch"
        assert hasattr(api_provider, "api_uri"), "API provider should have api_uri"
        assert (
            api_provider.api_uri == "https://test.api.example.com"
        ), "API URI mismatch"
        assert hasattr(
            api_provider, "WAIT_BETWEEN_REQUESTS"
        ), "API provider should have WAIT_BETWEEN_REQUESTS"
        assert hasattr(
            api_provider, "WAIT_AFTER_FAILURE"
        ), "API provider should have WAIT_AFTER_FAILURE"

    def test_configure_provider(self):
        """Test that _configure_provider is called during initialization."""
        test_name = "test_configure_provider"
        if self.reason_to_skip(test_name):
            return

        if not self.provider_class:
            pytest.skip("provider_class not defined, test cannot run")

        # Mock the _configure_provider method
        with patch.object(self.provider_class, "_configure_provider") as mock_configure:
            # Initialize the provider
            provider = self.provider_class(
                extension_id=self.extension_id, **self.provider_init_params
            )

            # Check that _configure_provider was called
            mock_configure.assert_called_once()

    def test_services(self, provider):
        """Test that services property returns expected services."""
        test_name = "test_services"
        if self.reason_to_skip(test_name):
            return

        # Get services from provider
        services = provider.services

        # Check that services is a list
        assert isinstance(services, list), "Services should be a list"

        # Check for expected services
        for service in self.expected_services:
            assert (
                service in services
            ), f"Expected service {service} not found in provider services"

    def test_register_unsupported_ability(self, provider):
        """Test registering an unsupported ability."""
        test_name = "test_register_unsupported_ability"
        if self.reason_to_skip(test_name):
            return

        # Register an unsupported ability
        test_ability = f"test_ability_{uuid.uuid4()}"
        provider.register_unsupported_ability(test_ability)

        # Check that the ability is in unsupported_capabilities
        assert (
            test_ability in provider.unsupported_capabilities
        ), "Ability should be in unsupported_capabilities"

        # Check that has_ability returns False for the ability
        assert not provider.has_ability(
            test_ability
        ), "has_ability should return False for unsupported ability"

    def test_has_ability(self, provider):
        """Test has_ability method."""
        test_name = "test_has_ability"
        if self.reason_to_skip(test_name):
            return

        # Test with nonexistent ability
        nonexistent_ability = f"nonexistent_ability_{uuid.uuid4()}"
        assert not provider.has_ability(
            nonexistent_ability
        ), "Should return False for nonexistent ability"

        # Test with expected abilities if any
        for ability in self.expected_abilities:
            # Temporarily set _extension_capabilities to include expected ability
            if not hasattr(provider, "_extension_capabilities"):
                provider._extension_capabilities = set()
            provider._extension_capabilities.add(ability)

            # Check that has_ability returns True
            assert provider.has_ability(
                ability
            ), f"Should return True for expected ability {ability}"

            # Register as unsupported
            provider.register_unsupported_ability(ability)

            # Check that has_ability now returns False
            assert not provider.has_ability(
                ability
            ), f"Should return False after registering {ability} as unsupported"

    def test_get_abilities(self, provider):
        """Test get_abilities method."""
        test_name = "test_get_abilities"
        if self.reason_to_skip(test_name):
            return

        # Get abilities
        abilities = provider.get_abilities()

        # Check that abilities is a dictionary
        assert isinstance(abilities, dict), "Abilities should be a dictionary"

    def test_safe_join(self, provider, temp_workspace):
        """Test safe_join method."""
        test_name = "test_safe_join"
        if self.reason_to_skip(test_name):
            return

        # Test normal path joining
        test_path = "test_dir/test_file.txt"
        joined_path = provider.safe_join(temp_workspace, test_path)

        # Check that the joined path starts with the base directory
        assert joined_path.startswith(
            temp_workspace
        ), "Joined path should start with base directory"
        assert (
            "/test_dir/test_file.txt" in joined_path
        ), "Joined path should contain the test path"

        # Test with /path/to/ prefix (should be removed)
        test_path_with_prefix = "/path/to/test_dir/test_file.txt"
        joined_path = provider.safe_join(temp_workspace, test_path_with_prefix)

        # Check that the prefix was removed
        assert "/path/to/" not in joined_path, "Prefix /path/to/ should be removed"
        assert (
            "/test_dir/test_file.txt" in joined_path
        ), "Joined path should contain the test path"

        # Test path traversal attempt
        with pytest.raises(ValueError):
            provider.safe_join(temp_workspace, "../../../etc/passwd")

    def test_handle_failure(self, provider):
        """Test _handle_failure method."""
        test_name = "test_handle_failure"
        if self.reason_to_skip(test_name):
            return

        # Create a test error
        test_error = Exception("Test error")

        # Initial failures should be 0
        assert provider.failures == 0, "Initial failures should be 0"

        # Handle the failure
        result = provider._handle_failure(test_error)

        # Failures should be incremented
        assert provider.failures == 1, "Failures should be incremented"

        # Result should be True (indicating retry is appropriate)
        assert result, "Result should be True indicating retry is appropriate"

        # Set failures to MAX_FAILURES
        provider.failures = provider.MAX_FAILURES

        # Handle the failure again, should raise an exception
        with pytest.raises(Exception):
            provider._handle_failure(test_error)

    def test_get_extension_info(self, provider):
        """Test get_extension_info method."""
        test_name = "test_get_extension_info"
        if self.reason_to_skip(test_name):
            return

        # Get extension info
        info = provider.get_extension_info()

        # Check that info is a dictionary
        assert isinstance(info, dict), "Extension info should be a dictionary"

        # Check for required keys
        assert "name" in info, "Extension info should contain 'name'"
        assert "description" in info, "Extension info should contain 'description'"

    def test_workspace_directory(self, provider):
        """Test that WORKING_DIRECTORY is set and accessible."""
        test_name = "test_workspace_directory"
        if self.reason_to_skip(test_name):
            return

        # Check that WORKING_DIRECTORY is set
        assert hasattr(
            provider, "WORKING_DIRECTORY"
        ), "Provider should have WORKING_DIRECTORY"

        # Check that directory exists
        assert os.path.exists(
            provider.WORKING_DIRECTORY
        ), "Working directory should exist"

        # Check that it's a directory
        assert os.path.isdir(
            provider.WORKING_DIRECTORY
        ), "Working directory should be a directory"

    def test_custom_working_directory(self):
        """Test provider initialization with custom working directory."""
        test_name = "test_custom_working_directory"
        if self.reason_to_skip(test_name):
            return

        if not self.provider_class:
            pytest.skip("provider_class not defined, test cannot run")

        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Initialize provider with custom directory
            provider = self.provider_class(
                extension_id=self.extension_id,
                conversation_directory=temp_dir,
                **self.provider_init_params,
            )

            # Check that WORKING_DIRECTORY is set to the custom directory
            assert (
                provider.WORKING_DIRECTORY == temp_dir
            ), "WORKING_DIRECTORY should be set to custom directory"
