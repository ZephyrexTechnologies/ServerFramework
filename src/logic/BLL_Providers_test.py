from faker import Faker

from logic.AbstractBLLTest import AbstractBLLTest, TestCategory, TestClassConfig
from logic.BLL_Extensions import ExtensionManager
from logic.BLL_Providers import (
    ProviderExtensionManager,
    ProviderInstanceManager,
    ProviderInstanceSettingManager,
    ProviderManager,
    RotationManager,
    RotationProviderInstanceManager,
)

# Set default test configuration for all test classes
AbstractBLLTest.test_config = TestClassConfig(categories=[TestCategory.LOGIC])

# Initialize faker for generating test data once
faker = Faker()


class TestProviderManager(AbstractBLLTest):
    class_under_test = ProviderManager
    create_fields = {
        "name": f"Test Provider {faker.word()}",
        "agent_settings_json": '{"test_setting": "test_value"}',
        "system": False,
    }
    update_fields = {
        "name": f"Updated Provider {faker.word()}",
        "agent_settings_json": '{"updated_setting": "updated_value"}',
    }
    unique_field = "name"


class TestProviderExtensionManager(AbstractBLLTest):
    class_under_test = ProviderExtensionManager
    create_fields = {
        "provider_id": None,  # Will be set in setup
        "extension_id": None,  # Will be set in setup
    }
    update_fields = {}  # No meaningful updates for this relationship

    def setup_method(self, method):
        """Set up method-level test fixtures."""
        super().setup_method(method)

        # Create dependencies for testing
        self._create_dependencies()

    def teardown_method(self, method):
        """Clean up method-level test fixtures."""
        try:
            self._cleanup_dependencies()
        finally:
            super().teardown_method(method)

    def _create_dependencies(self):
        """Create required dependent entities."""
        # Create a provider for testing
        with ProviderManager(requester_id=self.root_id) as manager:
            provider = manager.create(
                name=f"Test Provider for Extension {faker.uuid4()}",
                agent_settings_json='{"test": "value"}',
            )
            self.provider_id = provider.id

        # Create an extension for testing
        with ExtensionManager(requester_id=self.root_id) as manager:
            extension = manager.create(
                name=f"Test Extension for Provider {faker.uuid4()}",
                description="Created for TestProviderExtensionManager",
            )
            self.extension_id = extension.id

        # Update create_fields with the IDs
        self.create_fields["provider_id"] = self.provider_id
        self.create_fields["extension_id"] = self.extension_id

    def _cleanup_dependencies(self):
        """Clean up dependent entities."""
        # Clean up the provider and extension we created
        if hasattr(self, "provider_id"):
            with ProviderManager(requester_id=self.root_id) as manager:
                try:
                    manager.delete(id=self.provider_id)
                except:
                    pass

        if hasattr(self, "extension_id"):
            with ExtensionManager(requester_id=self.root_id) as manager:
                try:
                    manager.delete(id=self.extension_id)
                except:
                    pass


class TestProviderInstanceManager(AbstractBLLTest):
    class_under_test = ProviderInstanceManager
    create_fields = {
        "name": f"Test Provider Instance {faker.word()}",
        "provider_id": None,  # Will be set in setup
        "model_name": "test-model",
        "api_key": faker.uuid4(),
    }
    update_fields = {
        "name": f"Updated Provider Instance {faker.word()}",
        "model_name": "updated-model",
        "api_key": faker.uuid4(),
    }
    unique_field = "name"

    def setup_method(self, method):
        """Set up method-level test fixtures."""
        super().setup_method(method)

        # Create a provider for testing
        with ProviderManager(requester_id=self.root_id) as manager:
            provider = manager.create(
                name=f"Test Provider for Instance {faker.uuid4()}",
                agent_settings_json='{"test": "value"}',
            )
            self.provider_id = provider.id

        # Update create_fields with the provider ID
        self.create_fields["provider_id"] = self.provider_id

    def teardown_method(self, method):
        """Clean up method-level test fixtures."""
        try:
            # Clean up the provider we created
            if hasattr(self, "provider_id"):
                with ProviderManager(requester_id=self.root_id) as manager:
                    try:
                        manager.delete(id=self.provider_id)
                    except:
                        pass
        finally:
            super().teardown_method(method)


class TestProviderInstanceSettingManager(AbstractBLLTest):
    class_under_test = ProviderInstanceSettingManager
    create_fields = {
        "provider_instance_id": None,  # Will be set in setup
        "key": f"test_key_{faker.word()}",
        "value": faker.sentence(),
    }
    update_fields = {
        "value": f"Updated {faker.sentence()}",
    }
    unique_field = "key"

    def setup_method(self, method):
        """Set up method-level test fixtures."""
        super().setup_method(method)
        self._create_dependencies()

    def teardown_method(self, method):
        """Clean up method-level test fixtures."""
        try:
            self._cleanup_dependencies()
        finally:
            super().teardown_method(method)

    def _create_dependencies(self):
        """Create dependencies needed for testing."""
        # Create a provider for testing
        with ProviderManager(requester_id=self.root_id) as manager:
            provider = manager.create(
                name=f"Test Provider for Settings {faker.uuid4()}",
                agent_settings_json='{"test": "value"}',
            )
            self.provider_id = provider.id

        # Create a provider instance for testing
        with ProviderInstanceManager(requester_id=self.root_id) as manager:
            instance = manager.create(
                name=f"Test Instance for Setting {faker.uuid4()}",
                provider_id=self.provider_id,
                model_name="test-model",
                api_key=faker.uuid4(),
            )
            self.instance_id = instance.id

        # Update create_fields with the instance ID
        self.create_fields["provider_instance_id"] = self.instance_id

    def _cleanup_dependencies(self):
        """Clean up dependencies created for testing."""
        # Clean up the instance and provider we created
        if hasattr(self, "instance_id"):
            with ProviderInstanceManager(requester_id=self.root_id) as manager:
                try:
                    manager.delete(id=self.instance_id)
                except:
                    pass

        if hasattr(self, "provider_id"):
            with ProviderManager(requester_id=self.root_id) as manager:
                try:
                    manager.delete(id=self.provider_id)
                except:
                    pass


class TestRotationManager(AbstractBLLTest):
    class_under_test = RotationManager
    create_fields = {
        "name": f"Test Rotation {faker.word()}",
        "description": faker.paragraph(),
    }
    update_fields = {
        "name": f"Updated Rotation {faker.word()}",
        "description": f"Updated {faker.paragraph()}",
    }
    unique_field = "name"


class TestRotationProviderInstanceManager(AbstractBLLTest):
    class_under_test = RotationProviderInstanceManager
    create_fields = {
        "rotation_id": None,  # Will be set in setup
        "provider_instance_id": None,  # Will be set in setup
    }
    update_fields = {
        "parent_id": None,  # Will be updated in test
    }

    def setup_method(self, method):
        """Set up method-level test fixtures."""
        super().setup_method(method)
        self._create_dependencies()

    def teardown_method(self, method):
        """Clean up method-level test fixtures."""
        try:
            self._cleanup_dependencies()
        finally:
            super().teardown_method(method)

    def _create_dependencies(self):
        """Create dependencies needed for testing."""
        # Create a provider for testing
        with ProviderManager(requester_id=self.root_id) as manager:
            provider = manager.create(
                name=f"Test Provider for Rotation {faker.uuid4()}",
                agent_settings_json='{"test": "value"}',
            )
            self.provider_id = provider.id

        # Create a provider instance for testing
        with ProviderInstanceManager(requester_id=self.root_id) as manager:
            instance = manager.create(
                name=f"Test Instance for Rotation {faker.uuid4()}",
                provider_id=self.provider_id,
                model_name="test-model",
                api_key=faker.uuid4(),
            )
            self.instance_id = instance.id

        # Create a rotation for testing
        with RotationManager(requester_id=self.root_id) as manager:
            rotation = manager.create(
                name=f"Test Rotation for Instance {faker.uuid4()}",
                description="Created for TestRotationProviderInstanceManager",
            )
            self.rotation_id = rotation.id

        # Update create_fields with the IDs
        self.create_fields["rotation_id"] = self.rotation_id
        self.create_fields["provider_instance_id"] = self.instance_id

    def _cleanup_dependencies(self):
        """Clean up dependencies created for testing."""
        # Clean up all the entities we created
        if hasattr(self, "rotation_id"):
            with RotationManager(requester_id=self.root_id) as manager:
                try:
                    manager.delete(id=self.rotation_id)
                except:
                    pass

        if hasattr(self, "instance_id"):
            with ProviderInstanceManager(requester_id=self.root_id) as manager:
                try:
                    manager.delete(id=self.instance_id)
                except:
                    pass

        if hasattr(self, "provider_id"):
            with ProviderManager(requester_id=self.root_id) as manager:
                try:
                    manager.delete(id=self.provider_id)
                except:
                    pass

    def _update(self, user_id=None, team_id=None):
        """Override to create a parent rotation instance first."""
        # Create a parent rotation instance first
        with RotationProviderInstanceManager(
            requester_id=user_id or self.root_id, target_team_id=team_id
        ) as manager:
            parent = manager.create(
                rotation_id=self.rotation_id,
                provider_instance_id=self.instance_id,
            )
            self.parent_id = parent.id
            self.tracked_entities["parent"] = parent

            # Update original update_fields with parent ID
            self.update_fields["parent_id"] = self.parent_id

        # Call the original update method
        return super()._update(user_id, team_id)
