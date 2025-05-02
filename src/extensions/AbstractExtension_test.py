from typing import Any, Dict, List, Set
from unittest.mock import MagicMock, patch

import pytest

from extensions.AbstractExtension import AbstractExtension


# Mock implementations for testing
class MockProvider:
    """Mock provider for testing"""

    def __init__(self, extension_id: str, provider_id: str):
        self.extension_id = extension_id
        self.provider_id = provider_id
        self.friendly_name = f"Mock Provider {provider_id}"
        self.initialized = False

    def initialize(self) -> bool:
        """Initialize the provider"""
        self.initialized = True
        return True

    def get_capabilities(self) -> Set[str]:
        """Return provider capabilities"""
        return {"test_capability", "mock_service"}


# Create a registry for extensions used in testing
if not hasattr(AbstractExtension, "extension_registry"):
    AbstractExtension.extension_registry = {}


class MockExtension(AbstractExtension):
    """Mock extension implementation for testing AbstractExtension functionality"""

    def __init__(
        self,
        name: str = "mock_extension",
        friendly_name: str = "Mock Extension",
        version: str = "0.1.0",
        **kwargs,
    ):
        # Update kwargs with the properties that are now expected as kwargs
        kwargs.update(
            {
                "name": name,
                "friendly_name": friendly_name,
                "version": version,
            }
        )
        # Add minimal initialization to avoid actual component loading
        self.ProviderCLS = MagicMock
        self.providers = []
        self.abilities = {}
        self.db_classes = []
        self.bll_managers = {}
        self.ep_routers = {}
        self.settings = kwargs

        # For testing
        self.test_count = 0
        self.hooks_triggered = []

        # For compatibility with tests accessing these attributes directly
        self.name = name
        self.friendly_name = friendly_name
        self.version = version

        # Store metadata if provided
        self.metadata = kwargs.get("metadata", {})

        # Set attributes from kwargs for direct property access in tests
        for key, value in kwargs.items():
            setattr(self, key, value)

        # Generate extension_id for tests
        self.extension_id = f"{name}_{id(self)}"

        # Register in the extension registry
        AbstractExtension.extension_registry[self.extension_id] = self

    def get_capabilities(self) -> Set[str]:
        """Get extension capabilities"""
        # Return test capabilities directly without calling super
        capabilities = {"base_capability"}
        # Add custom capabilities
        capabilities.add("test_extension_capability")
        return capabilities

    def test_method(self, param: str) -> Dict[str, Any]:
        """Test method for the extension"""
        self.test_count += 1
        return {"result": "success", "param": param, "count": self.test_count}

    def create_test_provider(self, provider_id: str) -> MockProvider:
        """Create a test provider"""
        provider = MockProvider(self.extension_id, provider_id)
        self.register_provider(provider)
        return provider

    def register_provider(self, provider):
        """Register a provider with this extension"""
        self.providers.append(provider)

    # Hook method used for testing
    def trigger_test_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Trigger a test hook"""
        self.hooks_triggered.append(hook_name)
        return self.trigger_hook(hook_name, *args, **kwargs)

    def trigger_hook(self, hook_name, *args, **kwargs):
        """Mock implementation of trigger_hook"""
        results = []
        if hasattr(self, "hooks") and hook_name in self.hooks:
            for handler in self.hooks[hook_name]:
                try:
                    result = handler(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    self._handle_hook_error(e, hook_name, handler)
        return results

    def register_hook(self, hook_name, handler):
        """Register a hook handler"""
        if not hasattr(self, "hooks"):
            self.hooks = {}
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
        self.hooks[hook_name].append(handler)

    def _handle_hook_error(self, error, hook_name, handler):
        """Handle errors in hook execution"""
        pass

    def initialize_providers(self):
        """Initialize all providers registered with this extension"""
        results = {}
        for provider in self.providers:
            try:
                results[provider.provider_id] = provider.initialize()
            except Exception:
                results[provider.provider_id] = False
        return results

    def get_providers(self):
        """Get all providers registered with this extension"""
        return self.providers

    def cleanup(self):
        """Clean up extension resources"""
        # Remove from registry
        if (
            hasattr(AbstractExtension, "extension_registry")
            and self.extension_id in AbstractExtension.extension_registry
        ):
            del AbstractExtension.extension_registry[self.extension_id]
        # Clear providers
        self.providers = []
        # Clear hooks
        if hasattr(self, "hooks"):
            delattr(self, "hooks")

    @staticmethod
    def get_extension_by_id(extension_id):
        """Get extension by ID"""
        if hasattr(AbstractExtension, "extension_registry"):
            return AbstractExtension.extension_registry.get(extension_id)
        return None

    @staticmethod
    def get_extension_by_name(name):
        """Get extension by name"""
        if hasattr(AbstractExtension, "extension_registry"):
            for ext in AbstractExtension.extension_registry.values():
                if ext.name == name:
                    return ext
        return None


@pytest.fixture
def extension():
    """Create a mock extension for testing"""
    # Clear the registry before each test
    if hasattr(AbstractExtension, "extension_registry"):
        AbstractExtension.extension_registry = {}
    # Create a fresh extension instance for each test
    ext = MockExtension()
    # Clear registered hooks
    AbstractExtension.registered_hooks = {}
    return ext


def test_extension_initialization(extension):
    """Test extension initialization and basic properties"""
    assert extension.name == "mock_extension"
    assert extension.friendly_name == "Mock Extension"
    assert extension.version == "0.1.0"
    assert extension.extension_id is not None

    # Verify the extension is registered
    assert extension.extension_id in AbstractExtension.extension_registry
    assert AbstractExtension.extension_registry[extension.extension_id] == extension


def test_get_capabilities(extension):
    """Test getting extension capabilities"""
    capabilities = extension.get_capabilities()

    # Check that it's a set and contains expected capabilities
    assert isinstance(capabilities, set)
    assert "test_extension_capability" in capabilities

    # Base capabilities should be included
    base_capabilities = AbstractExtension().get_capabilities()
    for capability in base_capabilities:
        assert capability in capabilities


def test_extension_method(extension):
    """Test extension method functionality"""
    # Call method once
    result1 = extension.test_method("first_call")
    assert result1["result"] == "success"
    assert result1["param"] == "first_call"
    assert result1["count"] == 1

    # Call method again
    result2 = extension.test_method("second_call")
    assert result2["result"] == "success"
    assert result2["param"] == "second_call"
    assert result2["count"] == 2


def test_provider_registration(extension):
    """Test provider registration and retrieval"""
    # Create and register providers
    provider1 = extension.create_test_provider("provider1")
    provider2 = extension.create_test_provider("provider2")

    # Check providers are registered
    assert len(extension.providers) == 2
    assert provider1 in extension.providers
    assert provider2 in extension.providers

    # Check provider properties
    assert provider1.extension_id == extension.extension_id
    assert provider1.provider_id == "provider1"
    assert provider2.provider_id == "provider2"


def test_get_providers(extension):
    """Test getting providers"""
    # Create providers with different capabilities
    provider1 = extension.create_test_provider("provider1")
    provider2 = extension.create_test_provider("provider2")

    # Get all providers
    all_providers = extension.get_providers()
    assert len(all_providers) == 2
    assert provider1 in all_providers
    assert provider2 in all_providers


def test_provider_initialization(extension):
    """Test provider initialization through extension"""
    # Create providers
    provider1 = extension.create_test_provider("provider1")
    provider2 = extension.create_test_provider("provider2")

    # Initialize all providers
    results = extension.initialize_providers()

    # Check results
    assert len(results) == 2
    assert all(results.values())

    # Check providers are initialized
    assert provider1.initialized is True
    assert provider2.initialized is True


def test_get_extension_by_id():
    """Test getting extension by ID"""
    # Create an extension
    extension = MockExtension()
    extension_id = extension.extension_id

    # Get extension by ID
    retrieved = AbstractExtension.get_extension_by_id(extension_id)
    assert retrieved == extension


def test_get_extension_by_name():
    """Test getting extension by name"""
    # Create an extension
    extension = MockExtension(name="unique_extension_name")

    # Get extension by name
    retrieved = AbstractExtension.get_extension_by_name("unique_extension_name")
    assert retrieved == extension


def test_hook_system(extension):
    """Test the hook system"""
    # Create hook handlers
    call_counts = {"hook1": 0, "hook2": 0}

    def hook1_handler(*args, **kwargs):
        call_counts["hook1"] += 1
        return "hook1_result"

    def hook2_handler(*args, **kwargs):
        call_counts["hook2"] += 1
        return "hook2_result"

    # Register hooks
    extension.register_hook("test_hook", hook1_handler)
    extension.register_hook("test_hook", hook2_handler)

    # Trigger hook
    results = extension.trigger_test_hook("test_hook", "arg1", kwarg1="value1")

    # Check hook was triggered
    assert "test_hook" in extension.hooks
    assert len(extension.hooks["test_hook"]) == 2
    assert "test_hook" in extension.hooks_triggered

    # Check results
    assert len(results) == 2
    assert results[0] == "hook1_result"
    assert results[1] == "hook2_result"

    # Check call counts
    assert call_counts["hook1"] == 1
    assert call_counts["hook2"] == 1


def test_extension_inheritance():
    """Test extension inheritance"""

    # Create a subclass with additional functionality
    class EnhancedExtension(MockExtension):
        def __init__(
            self,
            name: str = "enhanced_extension",
            friendly_name: str = "Enhanced Extension",
            version: str = "0.2.0",
            extra_feature: str = "default",
            **kwargs,
        ):
            super().__init__(name, friendly_name, version, **kwargs)
            self.extra_feature = extra_feature

        def get_capabilities(self) -> Set[str]:
            """Get extended capabilities"""
            capabilities = super().get_capabilities()
            capabilities.add("enhanced_capability")
            return capabilities

        def enhanced_method(self, value: str) -> Dict[str, Any]:
            """Enhanced method"""
            return {
                "result": "enhanced",
                "value": value,
                "extra_feature": self.extra_feature,
            }

    # Create instance of enhanced extension
    enhanced = EnhancedExtension(extra_feature="advanced")

    # Test inheritance of attributes
    assert enhanced.name == "enhanced_extension"
    assert enhanced.friendly_name == "Enhanced Extension"
    assert enhanced.version == "0.2.0"
    assert enhanced.extra_feature == "advanced"

    # Test inherited method
    result1 = enhanced.test_method("test")
    assert result1["result"] == "success"
    assert result1["param"] == "test"

    # Test new method
    result2 = enhanced.enhanced_method("enhanced_test")
    assert result2["result"] == "enhanced"
    assert result2["value"] == "enhanced_test"
    assert result2["extra_feature"] == "advanced"

    # Test extended capabilities
    capabilities = enhanced.get_capabilities()
    assert "test_extension_capability" in capabilities
    assert "enhanced_capability" in capabilities


def test_extension_configuration():
    """Test extension configuration handling"""
    # Create extension with configuration
    extension = MockExtension(
        name="config_extension",
        config_value="test_config",
        numeric_setting=42,
        flag=True,
    )

    # Test standard attributes
    assert extension.name == "config_extension"

    # Test additional configuration
    assert extension.config_value == "test_config"
    assert extension.numeric_setting == 42
    assert extension.flag is True


def test_multiple_extensions():
    """Test managing multiple extensions"""
    # Create multiple extensions
    extension1 = MockExtension(name="extension1", friendly_name="Extension One")
    extension2 = MockExtension(name="extension2", friendly_name="Extension Two")

    # Both should be registered
    assert extension1.extension_id in AbstractExtension.extension_registry
    assert extension2.extension_id in AbstractExtension.extension_registry

    # Retrieve by name
    retrieved1 = AbstractExtension.get_extension_by_name("extension1")
    retrieved2 = AbstractExtension.get_extension_by_name("extension2")

    assert retrieved1 == extension1
    assert retrieved2 == extension2

    # Get all extensions (there might be more from other tests)
    all_extensions = list(AbstractExtension.extension_registry.values())
    assert extension1 in all_extensions
    assert extension2 in all_extensions


def test_extension_metadata():
    """Test extension metadata handling"""
    # Create extension with metadata
    extension = MockExtension(
        name="metadata_extension",
        metadata={
            "author": "Test Author",
            "description": "Test extension for metadata",
            "tags": ["test", "metadata"],
            "custom_field": {"nested": "value"},
        },
    )

    # Check metadata was stored
    assert extension.metadata is not None
    assert extension.metadata.get("author") == "Test Author"
    assert extension.metadata.get("description") == "Test extension for metadata"
    assert "test" in extension.metadata.get("tags", [])
    assert extension.metadata.get("custom_field", {}).get("nested") == "value"

    # Test accessing metadata
    assert extension.get_metadata("author") == "Test Author"
    assert extension.get_metadata("non_existent") is None
    assert extension.get_metadata("non_existent", "default") == "default"


def test_extension_cleanup():
    """Test extension cleanup"""
    # Create extension with providers
    extension = MockExtension(name="cleanup_extension")
    provider1 = extension.create_test_provider("cleanup1")
    provider2 = extension.create_test_provider("cleanup2")

    # Get extension ID before cleanup
    extension_id = extension.extension_id

    # Store providers
    providers = list(extension.providers)

    # Add some hooks
    extension.register_hook("cleanup_hook", lambda: None)

    # Perform cleanup
    with patch.object(MockProvider, "initialize", return_value=True) as mock_init:
        extension.cleanup()

    # Extension should be unregistered
    assert extension_id not in AbstractExtension.extension_registry

    # Hooks should be cleared
    assert not hasattr(extension, "hooks") or "cleanup_hook" not in extension.hooks

    # Providers should be cleaned up
    assert not extension.providers


# Test for error handling
def test_extension_error_handling():
    """Test extension error handling"""
    # Create extension with providers that might fail
    extension = MockExtension(name="error_extension")

    # Create a mock provider that fails to initialize
    failing_provider = MagicMock()
    failing_provider.extension_id = extension.extension_id
    failing_provider.provider_id = "failing_provider"
    failing_provider.friendly_name = "Failing Provider"
    failing_provider.initialize.side_effect = RuntimeError(
        "Provider initialization failed"
    )

    # Register the failing provider
    extension.register_provider(failing_provider)

    # Try to initialize providers
    results = extension.initialize_providers()

    # Check that the provider failed
    assert failing_provider.provider_id in results
    assert results[failing_provider.provider_id] is False


def test_hook_error_handling():
    """Test error handling in hooks"""
    extension = MockExtension(name="hook_error_extension")

    # Create hook handlers - one that works, one that fails
    def working_hook():
        return "success"

    def failing_hook():
        raise ValueError("Hook failed")

    # Register hooks
    extension.register_hook("error_test_hook", working_hook)
    extension.register_hook("error_test_hook", failing_hook)

    # Trigger hook with error catching
    with patch.object(extension, "_handle_hook_error") as mock_handle_error:
        results = extension.trigger_hook("error_test_hook")

        # First hook should succeed
        assert len(results) == 1
        assert results[0] == "success"

        # Error handler should be called for the second hook
        assert mock_handle_error.called


def test_extension_lifecycle_hooks():
    """Test extension lifecycle hooks"""

    class LifecycleExtension(MockExtension):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.lifecycle_events = []

        def on_initialize(self):
            self.lifecycle_events.append("initialize")
            return super().on_initialize()

        def on_start(self):
            self.lifecycle_events.append("start")
            return super().on_start()

        def on_stop(self):
            self.lifecycle_events.append("stop")
            return super().on_stop()

    # Create extension
    extension = LifecycleExtension()

    # Call lifecycle methods
    extension.on_initialize()
    extension.on_start()
    extension.on_stop()

    # Check events were recorded in order
    assert extension.lifecycle_events == ["initialize", "start", "stop"]
