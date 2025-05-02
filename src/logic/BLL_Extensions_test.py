from faker import Faker

from logic.AbstractBLLTest import AbstractBLLTest, TestCategory, TestClassConfig
from logic.BLL_Extensions import AbilityManager, ExtensionManager

# Set default test configuration for all test classes
AbstractBLLTest.test_config = TestClassConfig(categories=[TestCategory.LOGIC])

# Initialize faker for generating test data once
faker = Faker()


class TestExtensionManager(AbstractBLLTest):
    class_under_test = ExtensionManager
    create_fields = {
        "name": f"Test Extension {faker.word()}",
        "description": faker.paragraph(),
    }
    update_fields = {
        "name": f"Updated Extension {faker.word()}",
        "description": f"Updated {faker.paragraph()}",
    }
    unique_field = "name"

    def _get_unique_entity_data(self, **kwargs):
        """Override to ensure unique names for extensions."""
        data = super()._get_unique_entity_data(**kwargs)
        if "name" in data:
            data["name"] = f"Test Extension {faker.uuid4()}"
        return data


class TestAbilityManager(AbstractBLLTest):
    class_under_test = AbilityManager
    create_fields = {
        "name": f"Test Ability {faker.word()}",
        "extension_id": None,  # Will be set in setup
    }
    update_fields = {
        "name": f"Updated Ability {faker.word()}",
    }
    unique_field = "name"

    def setup_method(self, method):
        """Set up method-level test fixtures."""
        super().setup_method(method)

        # Create an extension for testing abilities
        with ExtensionManager(requester_id=self.root_id) as manager:
            extension = manager.create(
                name=f"Test Extension for Ability {faker.uuid4()}",
                description="Created for TestAbilityManager",
            )
            self.create_fields["extension_id"] = extension.id
            self.extension_id = extension.id

    def teardown_method(self, method):
        """Clean up method-level test fixtures."""
        try:
            # Clean up the extension we created
            if hasattr(self, "extension_id"):
                with ExtensionManager(requester_id=self.root_id) as manager:
                    try:
                        manager.delete(id=self.extension_id)
                    except:
                        pass
        finally:
            super().teardown_method(method)

    def _get_unique_entity_data(self, **kwargs):
        """Override to ensure unique names for abilities."""
        data = super()._get_unique_entity_data(**kwargs)
        if "name" in data:
            data["name"] = f"Test Ability {faker.uuid4()}"
        if "extension_id" not in data and hasattr(self, "extension_id"):
            data["extension_id"] = self.extension_id
        return data
