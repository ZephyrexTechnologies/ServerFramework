from AbstractTest import ParentEntity
from database.AbstractDBTest import AbstractDBTest
from database.DB_Extensions import Ability, Extension


class TestExtension(AbstractDBTest):
    class_under_test = Extension
    create_fields = {
        "name": "test_extension",
        "description": "Test extension description",
    }
    update_fields = {
        "name": "updated_extension",
        "description": "Updated extension description",
    }
    unique_field = "name"


class TestAbility(AbstractDBTest):
    class_under_test = Ability
    create_fields = {
        "extension_id": None,  # Will be populated in setup
        "name": "test_ability",
    }
    update_fields = {
        "name": "updated_ability",
    }
    unique_field = "name"
    parent_entities = [
        ParentEntity(
            name="extension", foreign_key="extension_id", test_class=TestExtension
        )
    ]

    # def setup_method(self, method):
    #     super().setup_method(method)
    #     # Create an extension to reference
    #     extension = Extension.create(
    #         self.root_user_id,
    #         self.db,
    #         return_type="dict",
    #         name="test_parent_extension",
    #         description="Extension for ability test",
    #     )
    #     # Update create_fields with valid extension_id
    #     self.create_fields["extension_id"] = extension["id"]
