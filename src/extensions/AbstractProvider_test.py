from typing import Any, Dict, Optional, Set
from unittest.mock import MagicMock, patch

import pytest

from extensions.AbstractProvider import AbstractProvider


# Create a mock AbstractExtension class for testing
class MockAbstractExtension:
    extension_registry = {}

    @classmethod
    def get_extension_by_id(cls, extension_id):
        return cls.extension_registry.get(extension_id)


# Mock the AbstractExtension module and class
with patch("extensions.AbstractExtension.AbstractExtension", MockAbstractExtension):
    # Make the mock module and class available for imports
    import sys

    sys.modules["extensions.AbstractExtension"] = MagicMock()
    sys.modules["extensions.AbstractExtension"].AbstractExtension = (
        MockAbstractExtension
    )


# Mock implementations for testing
class MockProvider(AbstractProvider):
    """Mock provider for testing AbstractProvider functionality"""

    def __init__(
        self,
        extension_id: Optional[str] = None,
        api_key: str = "",
        **kwargs,
    ):
        # Initialize the base provider
        super().__init__(extension_id=extension_id, api_key=api_key, **kwargs)
        self.service_calls = []
        self.initialized = False

    def initialize(self) -> bool:
        """Initialize the provider"""
        self.initialized = True
        return True

    def get_capabilities(self) -> Set[str]:
        """Return provider capabilities"""
        return {"test_capability", "mock_service"}

    def validate_config(self) -> bool:
        """Validate the provider configuration"""
        return self.api_key is not None and self.api_key != ""

    def test_service(self, param1, param2=None):
        """Test service implementation"""
        self.service_calls.append(("test_service", param1, param2))
        return {"result": "success", "param1": param1, "param2": param2}


# Fixture for creating a provider with an extension ID
@pytest.fixture
def extension_id():
    """Return a test extension ID"""
    return "eff56a01-b85c-43fe-83e6-9d1ba0b2aa98"


@pytest.fixture
def provider(extension_id):
    """Create a mock provider for testing"""
    return MockProvider(api_key="test_key_123", extension_id=extension_id)


def test_initialization(provider, extension_id):
    """Test provider initialization"""
    assert provider.extension_id == extension_id
    assert provider.api_key == "test_key_123"
    assert provider.initialized is False


def test_initialize_method(provider):
    """Test the initialize method"""
    result = provider.initialize()
    assert result is True
    assert provider.initialized is True


def test_get_capabilities(provider):
    """Test the get_capabilities method"""
    capabilities = provider.get_capabilities()
    assert isinstance(capabilities, set)
    assert "test_capability" in capabilities
    assert "mock_service" in capabilities


def test_validate_config(provider, extension_id):
    """Test configuration validation"""
    # Valid configuration
    assert provider.validate_config() is True

    # Invalid configuration
    invalid_provider = MockProvider(extension_id=extension_id)
    assert invalid_provider.validate_config() is False


def test_service_method(provider):
    """Test a service method on the provider"""
    result = provider.test_service("test_value", 42)

    # Check the result
    assert result["result"] == "success"
    assert result["param1"] == "test_value"
    assert result["param2"] == 42

    # Check that the call was recorded
    assert len(provider.service_calls) == 1
    assert provider.service_calls[0][0] == "test_service"
    assert provider.service_calls[0][1] == "test_value"
    assert provider.service_calls[0][2] == 42


def test_get_extension_id(provider, extension_id):
    """Test getting the extension ID"""
    assert provider.get_parent_extension_id() == extension_id


def test_provider_without_extension():
    """Test provider without an extension ID"""
    standalone_provider = MockProvider(api_key="standalone_key")
    assert standalone_provider.extension_id is None
    assert standalone_provider.get_parent_extension_id() is None

    # Should still function normally
    result = standalone_provider.test_service("standalone_test")
    assert result["result"] == "success"


def test_provider_configuration(extension_id):
    """Test provider configuration handling"""
    # Create a provider with various configuration options
    config_provider = MockProvider(
        extension_id=extension_id,
        api_key="config_key",
        timeout=30,
        retries=3,
        custom_setting="custom_value",
    )

    # Check that kwargs are properly handled
    assert config_provider.api_key == "config_key"

    # Check access to arbitrary config values
    assert config_provider.timeout == 30
    assert config_provider.retries == 3
    assert config_provider.custom_setting == "custom_value"


def test_provider_inheritance(extension_id):
    """Test that provider inheritance works correctly"""

    # Create a more specialized provider class
    class SpecializedProvider(MockProvider):
        def __init__(
            self,
            extension_id: Optional[str] = None,
            api_key: Optional[str] = None,
            specialized_param: str = "default",
            **kwargs,
        ):
            super().__init__(extension_id=extension_id, api_key=api_key, **kwargs)
            self.specialized_param = specialized_param
            self.friendly_name = "Specialized Provider"

        def get_capabilities(self) -> Set[str]:
            """Return extended capabilities"""
            # Get parent capabilities
            capabilities = super().get_capabilities()
            # Add specialized capabilities
            capabilities.add("specialized_capability")
            return capabilities

        def specialized_service(self, data: Dict[str, Any]) -> Dict[str, Any]:
            """Specialized service method"""
            self.service_calls.append(("specialized_service", data))
            return {
                "result": "specialized",
                "data": data,
                "specialized_param": self.specialized_param,
            }

    # Create instance of specialized provider
    specialized = SpecializedProvider(
        extension_id=extension_id,
        api_key="specialized_key",
        specialized_param="special",
    )

    # Test inheritance of initialization and properties
    assert specialized.extension_id == extension_id
    assert specialized.api_key == "specialized_key"
    assert specialized.specialized_param == "special"
    assert specialized.friendly_name == "Specialized Provider"

    # Test inheritance of capabilities
    capabilities = specialized.get_capabilities()
    assert "test_capability" in capabilities  # From parent
    assert "mock_service" in capabilities  # From parent
    assert "specialized_capability" in capabilities  # New capability

    # Test inherited service method
    result1 = specialized.test_service("inherited")
    assert result1["result"] == "success"
    assert result1["param1"] == "inherited"

    # Test specialized service method
    result2 = specialized.specialized_service({"key": "value"})
    assert result2["result"] == "specialized"
    assert result2["data"] == {"key": "value"}
    assert result2["specialized_param"] == "special"

    # Both service calls should be recorded
    assert len(specialized.service_calls) == 2


def test_provider_with_mock_extension(provider, extension_id):
    """Test provider interaction with an extension"""

    # Create a mock extension
    mock_extension = MagicMock()
    mock_extension.extension_id = extension_id
    mock_extension.name = "mock_extension"
    mock_extension.friendly_name = "Mock Extension"

    # Update the extension registry
    MockAbstractExtension.extension_registry[extension_id] = mock_extension

    # Patch the dynamic import in the get_parent_extension method
    with patch("extensions.AbstractExtension.AbstractExtension", MockAbstractExtension):
        # Also need to patch the import statement in the method
        with patch(
            "extensions.AbstractProvider.AbstractExtension", create=True
        ) as mock_import:
            # Make the mock import return our MockAbstractExtension
            mock_import.get_extension_by_id.return_value = mock_extension

            # Test that provider can get its parent extension
            extension = provider.get_parent_extension()
            assert extension == mock_extension
            assert extension.extension_id == extension_id
            assert extension.friendly_name == "Mock Extension"


def test_provider_error_handling(extension_id):
    """Test provider error handling mechanism"""

    # Create a provider that raises exceptions
    class ErrorProvider(AbstractProvider):
        def initialize(self):
            raise ConnectionError("Failed to connect")

        def test_service(self):
            raise ValueError("Invalid input")

    error_provider = ErrorProvider(extension_id=extension_id)

    # Test exception handling
    with pytest.raises(ConnectionError):
        error_provider.initialize()

    with pytest.raises(ValueError):
        error_provider.test_service()

    # Test with custom error handler
    errors = []

    def error_handler(provider, exception, method_name, *args, **kwargs):
        errors.append((provider, exception, method_name))
        return {"error": str(exception)}

    # Create mock methods for error handling
    error_provider.set_error_handler(error_handler)

    # Create a wrapper for test_service that uses error handler
    original_test_service = error_provider.test_service

    def wrapped_test_service(*args, **kwargs):
        try:
            return original_test_service(*args, **kwargs)
        except Exception as e:
            return error_handler(error_provider, e, "test_service", *args, **kwargs)

    error_provider.test_service = wrapped_test_service

    # Now the method should not raise but return the error handler's result
    result = error_provider.test_service()
    assert result == {"error": "Invalid input"}
    assert len(errors) == 1
    assert errors[0][0] == error_provider
    assert str(errors[0][1]) == "Invalid input"
    assert errors[0][2] == "test_service"


# Additional tests for provider hooks and interactions
def test_provider_hook_registration():
    """Test registration of provider hooks"""

    # Create a provider with a hook method
    class ProviderWithHook(AbstractProvider):
        def __init__(self, extension_id=None, **kwargs):
            super().__init__(extension_id, **kwargs)
            self.hook_called = False
            self.hooks = {}

        def register_hook(self, hook_name, hook_handler):
            """Register a hook function"""
            if hook_name not in self.hooks:
                self.hooks[hook_name] = []
            self.hooks[hook_name].append(hook_handler)

        def trigger_hook(self, hook_name, *args, **kwargs):
            """Trigger all handlers for a hook"""
            if hook_name not in self.hooks:
                return []

            results = []
            for handler in self.hooks[hook_name]:
                result = handler(*args, **kwargs)
                results.append(result)
            return results

        def service_with_hook(self, data):
            """Service that triggers a hook"""
            # Trigger before hook
            before_results = self.trigger_hook("before_service", data)

            # Process data
            processed_data = {
                "result": "processed",
                "original": data,
                "before_hook_results": before_results,
            }

            # Trigger after hook
            after_results = self.trigger_hook("after_service", processed_data)

            # Return final result
            return {**processed_data, "after_hook_results": after_results}

    # Create provider instance
    provider = ProviderWithHook()

    # Define hook handlers
    def before_hook(data):
        data["modified_by_hook"] = True
        return "before_done"

    def after_hook(result):
        result["hook_saw_result"] = True
        return "after_done"

    # Register hooks
    provider.register_hook("before_service", before_hook)
    provider.register_hook("after_service", after_hook)

    # Test service with hooks
    data = {"input": "test"}
    result = provider.service_with_hook(data)

    # Check that hooks were triggered
    assert data["modified_by_hook"] is True
    assert result["hook_saw_result"] is True
    assert result["before_hook_results"] == ["before_done"]
    assert result["after_hook_results"] == ["after_done"]
    assert result["result"] == "processed"


def test_provider_lifecycle():
    """Test provider lifecycle methods"""

    # Create a provider with lifecycle methods
    class LifecycleProvider(AbstractProvider):
        def __init__(self, extension_id=None, **kwargs):
            super().__init__(extension_id, **kwargs)
            self.lifecycle_events = []

        def initialize(self):
            self.lifecycle_events.append("initialize")
            return True

        def connect(self):
            self.lifecycle_events.append("connect")
            return True

        def close(self):
            self.lifecycle_events.append("close")
            return True

    # Create provider instance
    provider = LifecycleProvider()

    # Test lifecycle methods
    assert provider.initialize() is True
    assert "initialize" in provider.lifecycle_events

    assert provider.connect() is True
    assert "connect" in provider.lifecycle_events

    assert provider.close() is True
    assert "close" in provider.lifecycle_events

    # Check event order
    assert provider.lifecycle_events == ["initialize", "connect", "close"]
