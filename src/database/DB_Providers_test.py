from AbstractTest import ParentEntity
from database.AbstractDBTest import AbstractDBTest
from database.DB_Providers import (
    Provider,
    ProviderExtension,
    ProviderExtensionAbility,
    ProviderInstance,
    ProviderInstanceExtensionAbility,
    ProviderInstanceSetting,
    ProviderInstanceUsage,
    Rotation,
    RotationProviderInstance,
)


class TestProvider(AbstractDBTest):
    class_under_test = Provider
    create_fields = {
        "name": "test_provider",
        "friendly_name": "Test Provider",
        "agent_settings_json": '{"test": "value"}',
    }
    update_fields = {
        "friendly_name": "Updated Provider",
        "agent_settings_json": '{"updated": "value"}',
    }
    unique_field = "name"


class TestProviderExtension(AbstractDBTest):
    pass
    # from database.DB_Extensions_test import TestExtension

    # class_under_test = ProviderExtension
    # create_fields = {}
    # update_fields = {}  # No updateable fields besides system fields
    # parent_entities = [
    #    ParentEntity(
    #        name="extension", foreign_key="extension_id", test_class=TestExtension
    #    ),
    #    ParentEntity(
    #        name="provider",
    #        foreign_key="provider_id",
    #        test_class=TestProvider,
    #    ),
    # ]

    # def setup_method(self, method):
    #     super().setup_method(method)
    #     # Create provider and extension to reference
    #     provider = Provider.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         name="test_provider_for_extension",
    #         friendly_name="Test Provider",
    #     )
    #     extension = Extension.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         name="test_extension_for_provider",
    #         description="Test extension for provider",
    #     )
    #     # Update create_fields with valid IDs
    #     self.create_fields["provider_id"] = provider["id"]
    #     self.create_fields["extension_id"] = extension["id"]


class TestProviderInstance(AbstractDBTest):
    class_under_test = ProviderInstance
    create_fields = {
        "name": "test_provider_instance",
        "model_name": "test_model",
        "api_key": "test_api_key",
        "enabled": True,
    }
    update_fields = {
        "name": "updated_provider_instance",
        "model_name": "updated_model",
        "api_key": "updated_api_key",
        "enabled": False,
    }
    unique_field = "name"
    parent_entities = [
        ParentEntity(
            name="provider",
            foreign_key="provider_id",
            test_class=TestProvider,
        ),
    ]

    # def setup_method(self, method):
    #     super().setup_method(method)
    #     # Create provider to reference
    #     provider = Provider.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         name="test_provider_for_instance",
    #         friendly_name="Test Provider",
    #     )
    #     # Update create_fields with valid provider_id
    #     self.create_fields["provider_id"] = provider["id"]


class TestProviderExtensionAbility(AbstractDBTest):
    pass
    # from DB_Extensions_test import TestAbility
    # class_under_test = ProviderExtensionAbility
    # create_fields = {
    #    "provider_extension_id": None,  # Will be populated in setup
    #    "ability_id": None,  # Will be populated in setup
    # }
    # update_fields = {}  # No updateable fields besides system fields
    # parent_entities = [
    #    ParentEntity(
    #        name="provider_extension",
    #        foreign_key="provider_extension_id",
    #        test_class=TestProviderExtension,
    #    ),
    #    ParentEntity(
    #        name="ability",
    #        foreign_key="ability_id",
    #        test_class=TestAbility,
    #    ),
    # ]

    # def setup_method(self, method):
    #     super().setup_method(method)
    #     # Create dependencies
    #     provider = Provider.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         name="test_provider_for_ability",
    #         friendly_name="Test Provider",
    #     )
    #     extension = Extension.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         name="test_extension_for_ability",
    #         description="Test extension for ability",
    #     )
    #     provider_extension = ProviderExtension.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         provider_id=provider["id"],
    #         extension_id=extension["id"],
    #     )
    #     ability = Ability.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         extension_id=extension["id"],
    #         name="test_ability",
    #     )
    #     # Update create_fields with valid IDs
    #     self.create_fields["provider_extension_id"] = provider_extension["id"]
    #     self.create_fields["ability_id"] = ability["id"]


class TestProviderInstanceUsage(AbstractDBTest):
    class_under_test = ProviderInstanceUsage
    create_fields = {
        "user_id": None,  # Will be populated in setup
        "input_tokens": 100,
        "output_tokens": 50,
    }
    update_fields = {
        "input_tokens": 200,
        "output_tokens": 100,
    }
    parent_entities = [
        ParentEntity(
            name="provider_instance",
            foreign_key="provider_instance_id",
            test_class=TestProviderInstance,
        ),
    ]
    # def setup_method(self, method):
    #     super().setup_method(method)
    #     # Create provider and instance to reference
    #     provider = Provider.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         name="test_provider_for_usage",
    #         friendly_name="Test Provider",
    #     )
    #     provider_instance = ProviderInstance.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         provider_id=provider["id"],
    #         name="test_instance_for_usage",
    #         model_name="test_model",
    #         api_key="test_key",
    #         enabled=True,
    #     )
    #     # Update create_fields with valid IDs
    #     self.create_fields["provider_instance_id"] = provider_instance["id"]
    #     self.create_fields["user_id"] = self.regular_user_id


class TestProviderInstanceSetting(AbstractDBTest):
    class_under_test = ProviderInstanceSetting
    create_fields = {
        "key": "test_setting_key",
        "value": "test_setting_value",
    }
    update_fields = {
        "key": "updated_setting_key",
        "value": "updated_setting_value",
    }
    parent_entities = [
        ParentEntity(
            name="provider_instance",
            foreign_key="provider_instance_id",
            test_class=TestProviderInstance,
        ),
    ]
    # def setup_method(self, method):
    #     super().setup_method(method)
    #     # Create provider and instance to reference
    #     provider = Provider.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         name="test_provider_for_setting",
    #         friendly_name="Test Provider",
    #     )
    #     provider_instance = ProviderInstance.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         provider_id=provider["id"],
    #         name="test_instance_for_setting",
    #         model_name="test_model",
    #         api_key="test_key",
    #         enabled=True,
    #     )
    #     # Update create_fields with valid provider_instance_id
    #     self.create_fields["provider_instance_id"] = provider_instance["id"]


class TestProviderInstanceExtensionAbility(AbstractDBTest):
    class_under_test = ProviderInstanceExtensionAbility
    create_fields = {
        "state": True,
        "forced": False,
    }
    update_fields = {
        "state": False,
        "forced": True,
    }
    parent_entities = [
        ParentEntity(
            name="provider_instance",
            foreign_key="provider_instance_id",
            test_class=TestProviderInstance,
        ),
        ParentEntity(
            name="provider_extension_ability",
            foreign_key="provider_extension_ability_id",
            test_class=TestProviderExtensionAbility,
        ),
    ]

    # def setup_method(self, method):
    #     super().setup_method(method)
    #     # Create all required dependencies
    #     provider = Provider.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         name="test_provider_for_piea",
    #         friendly_name="Test Provider",
    #     )
    #     extension = Extension.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         name="test_extension_for_piea",
    #         description="Test extension for PIEA",
    #     )
    #     provider_extension = ProviderExtension.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         provider_id=provider["id"],
    #         extension_id=extension["id"],
    #     )
    #     ability = Ability.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         extension_id=extension["id"],
    #         name="test_ability_for_piea",
    #     )
    #     provider_extension_ability = ProviderExtensionAbility.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         provider_extension_id=provider_extension["id"],
    #         ability_id=ability["id"],
    #     )
    #     provider_instance = ProviderInstance.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         provider_id=provider["id"],
    #         name="test_instance_for_piea",
    #         model_name="test_model",
    #         api_key="test_key",
    #         enabled=True,
    #     )
    #     # Update create_fields with valid IDs
    #     self.create_fields["provider_instance_id"] = provider_instance["id"]
    #     self.create_fields["provider_extension_ability_id"] = (
    #         provider_extension_ability["id"]
    #     )


class TestRotation(AbstractDBTest):
    class_under_test = Rotation
    create_fields = {
        "name": "test_rotation",
        "description": "Test rotation description",
    }
    update_fields = {
        "name": "updated_rotation",
        "description": "Updated rotation description",
    }
    unique_field = "name"


class TestRotationProviderInstance(AbstractDBTest):
    class_under_test = RotationProviderInstance
    create_fields = {}
    update_fields = {}  # No updateable fields besides system fields
    parent_entities = [
        ParentEntity(
            name="rotation", foreign_key="rotation_id", test_class=TestRotation
        ),
        ParentEntity(
            name="provider_instance",
            foreign_key="provider_instance_id",
            test_class=TestProviderInstance,
        ),
    ]
    # def setup_method(self, method):
    #     super().setup_method(method)
    #     # Create rotation and provider instance
    #     rotation = Rotation.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         name="test_rotation_for_instance",
    #         description="Test rotation for provider instance",
    #     )
    #     provider = Provider.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         name="test_provider_for_rotation",
    #         friendly_name="Test Provider",
    #     )
    #     provider_instance = ProviderInstance.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         provider_id=provider["id"],
    #         name="test_instance_for_rotation",
    #         model_name="test_model",
    #         api_key="test_key",
    #         enabled=True,
    #     )
    #     # Update create_fields with valid IDs
    #     self.create_fields["rotation_id"] = rotation["id"]
    #     self.create_fields["provider_instance_id"] = provider_instance["id"]
