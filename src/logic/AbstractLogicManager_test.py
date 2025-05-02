import unittest
import uuid
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import MagicMock, patch

from AbstractLogicManager import (
    AbstractBLLManager,
    BaseMixinModel,
    HookDict,
    NameMixinModel,
    get_hooks_for_manager,
    hook_types,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session


# Mock Database Models
class MockDBModel:
    # Define class attributes that will be accessible via hasattr/getattr
    id = MagicMock()
    name = MagicMock()
    description = MagicMock()
    created_at = MagicMock()
    created_by_user_id = MagicMock()
    updated_at = MagicMock()
    updated_by_user_id = MagicMock()
    user_id = MagicMock()
    count = MagicMock()
    value = MagicMock()
    is_active = MagicMock()

    @classmethod
    def create(cls, requester_id, db, return_type, override_dto, **kwargs):
        instance = cls()
        for key, value in kwargs.items():
            setattr(instance, key, value)

        instance.id = str(uuid.uuid4())
        instance.created_at = datetime.now()
        instance.created_by_user_id = requester_id
        # Add default values for update fields
        instance.updated_at = instance.created_at
        instance.updated_by_user_id = requester_id

        # Convert to DTO if requested
        if return_type == "dto" and override_dto:
            return override_dto(
                id=instance.id,
                name=getattr(instance, "name", "Test"),
                description=getattr(instance, "description", "Test Description"),
                created_at=instance.created_at,
                created_by_user_id=instance.created_by_user_id,
                updated_at=instance.updated_at,
                updated_by_user_id=instance.updated_by_user_id,
            )
        return instance

    @classmethod
    def get(cls, requester_id, db, return_type, override_dto, options=None, **kwargs):
        instance = cls()
        instance.id = kwargs.get("id", str(uuid.uuid4()))
        instance.name = "Test Item"
        instance.description = "Test Description"
        instance.created_at = datetime.now()
        instance.created_by_user_id = requester_id
        instance.updated_at = instance.created_at
        instance.updated_by_user_id = requester_id

        # Convert to DTO if requested
        if return_type == "dto" and override_dto:
            return override_dto(
                id=instance.id,
                name=instance.name,
                description=instance.description,
                created_at=instance.created_at,
                created_by_user_id=instance.created_by_user_id,
                updated_at=instance.updated_at,
                updated_by_user_id=instance.updated_by_user_id,
            )
        return instance

    @classmethod
    def list(
        cls,
        requester_id,
        db,
        return_type,
        override_dto,
        options=None,
        order_by=None,
        limit=None,
        offset=None,
        filters=None,
        **kwargs,
    ):
        results = []
        for i in range(5):  # Return 5 mock objects
            instance = cls()
            instance.id = str(uuid.uuid4())
            instance.name = f"Test Item {i}"
            instance.description = f"Test Description {i}"
            instance.created_at = datetime.now()
            instance.created_by_user_id = requester_id
            instance.updated_at = instance.created_at
            instance.updated_by_user_id = requester_id

            # Apply any filters (mock implementation)
            should_include = True
            if kwargs.get("name"):
                should_include = kwargs["name"] in instance.name

            if should_include:
                # Convert to DTO if requested
                if return_type == "dto" and override_dto:
                    results.append(
                        override_dto(
                            id=instance.id,
                            name=instance.name,
                            description=instance.description,
                            created_at=instance.created_at,
                            created_by_user_id=instance.created_by_user_id,
                            updated_at=instance.updated_at,
                            updated_by_user_id=instance.updated_by_user_id,
                        )
                    )
                else:
                    results.append(instance)
        return results

    @classmethod
    def update(cls, requester_id, db, return_type, override_dto, new_properties, id):
        instance = cls()
        instance.id = id
        instance.created_at = datetime.now() - timedelta(days=1)
        instance.created_by_user_id = requester_id
        instance.updated_at = datetime.now()
        instance.updated_by_user_id = requester_id

        # Apply updates
        for key, value in new_properties.items():
            setattr(instance, key, value)

        # Convert to DTO if requested
        if return_type == "dto" and override_dto:
            return override_dto(
                id=instance.id,
                name=getattr(instance, "name", "Updated Test"),
                description=getattr(instance, "description", "Updated Description"),
                created_at=instance.created_at,
                created_by_user_id=instance.created_by_user_id,
                updated_at=instance.updated_at,
                updated_by_user_id=instance.updated_by_user_id,
            )
        return instance

    @classmethod
    def delete(cls, requester_id, db, id):
        # Just a mock implementation that does nothing
        pass


# Mock User and Team
class MockUser:
    def __init__(self, id):
        self.id = id
        self.name = "Test User"


class MockTeam:
    def __init__(self, id):
        self.id = id
        self.name = "Test Team"


# Test Models
class EntityModelForTest(BaseMixinModel, NameMixinModel):
    description: str
    updated_at: Optional[datetime] = Field(None)
    updated_by_user_id: Optional[str] = Field(None)

    class Create(BaseModel):
        name: str
        description: Optional[str] = None

    class Update(BaseModel):
        name: Optional[str] = None
        description: Optional[str] = None

    class Search(BaseMixinModel.Search, NameMixinModel.Search):
        pass


# Custom search transformer mock
def mock_transform_custom_search(value):
    """Mocked custom search transformer for testing"""
    return [MagicMock()]


# Test Manager
class ManagerForTest(AbstractBLLManager):
    Model = EntityModelForTest
    DBClass = MockDBModel

    def _register_search_transformers(self):
        self.register_search_transformer("custom_search", self._transform_custom_search)

    def _transform_custom_search(self, value):
        # Example custom transformer that creates a condition based on name
        if value and hasattr(self.DBClass, "name"):
            from sqlalchemy import or_

            return or_(
                self.DBClass.name.ilike(f"%{value}%"),
                self.DBClass.description.ilike(f"%{value}%"),
            )
        return None


# Tests
class TestAbstractLogicManager(unittest.TestCase):
    def setUp(self):
        # Mock DB session
        self.mock_db = MagicMock(spec=Session)
        self.mock_db.query.return_value.filter.return_value.first.return_value = (
            MockUser(id="user1")
        )

        # Create manager instance
        self.manager = ManagerForTest(
            requester_id="user1",
            target_user_id="user2",
            target_team_id="team1",
            db=self.mock_db,
        )

    def test_manager_initialization(self):
        """Test that manager initializes correctly with proper attributes."""
        self.assertEqual(self.manager.requester.id, "user1")
        self.assertEqual(self.manager.target_user_id, "user2")
        self.assertEqual(self.manager.target_team_id, "team1")
        self.assertIsNotNone(self.manager._db)

    def test_hooks_initialization(self):
        """Test that hooks are properly initialized for manager classes."""
        hooks = get_hooks_for_manager(ManagerForTest)

        # Verify all hook types exist
        for hook_type in hook_types:
            self.assertIn(hook_type, hooks)
            self.assertIn("before", hooks[hook_type])
            self.assertIn("after", hooks[hook_type])
            self.assertIsInstance(hooks[hook_type]["before"], list)
            self.assertIsInstance(hooks[hook_type]["after"], list)

    def test_hook_registration_and_execution(self):
        """Test registering and executing hooks."""
        # Create hook tracking variables
        create_before_executed = False
        create_after_executed = False

        # Define hook functions
        def before_create_hook(manager, data):
            nonlocal create_before_executed
            create_before_executed = True
            # Modify data
            data["description"] = "Modified by hook"

        def after_create_hook(manager, entity, data):
            nonlocal create_after_executed
            create_after_executed = True
            # Verify entity has the modified description
            self.assertEqual(entity.description, "Modified by hook")

        # Register hooks
        hooks = get_hooks_for_manager(ManagerForTest)
        hooks["create"]["before"].append(before_create_hook)
        hooks["create"]["after"].append(after_create_hook)

        # Execute operation that should trigger hooks
        entity = self.manager.create(name="Test Entity")

        # Verify hooks were executed
        self.assertTrue(create_before_executed)
        self.assertTrue(create_after_executed)

        # Clean up hooks for other tests
        hooks["create"]["before"].remove(before_create_hook)
        hooks["create"]["after"].remove(after_create_hook)

    def test_create_operation(self):
        """Test creating an entity."""
        entity = self.manager.create(name="Test Entity", description="Test Description")

        self.assertIsNotNone(entity)
        self.assertIsNotNone(entity.id)
        self.assertEqual(entity.name, "Test Entity")
        self.assertEqual(entity.created_by_user_id, "user1")

    def test_get_operation(self):
        """Test getting an entity by ID."""
        test_id = str(uuid.uuid4())
        entity = self.manager.get(id=test_id)

        self.assertIsNotNone(entity)
        self.assertEqual(entity.id, test_id)

    def test_list_operation(self):
        """Test listing entities."""
        entities = self.manager.list()

        self.assertIsInstance(entities, list)
        self.assertEqual(len(entities), 5)

        # Test with filters
        filtered = self.manager.list(name="Test Item 1")
        self.assertIsInstance(filtered, list)

    def test_update_operation(self):
        """Test updating an entity."""
        # Setup update hooks for testing
        update_before_executed = False
        update_after_executed = False

        def before_update_hook(manager, id, data):
            nonlocal update_before_executed
            update_before_executed = True
            # Modify update data
            data["description"] = "Modified by update hook"

        def after_update_hook(manager, updated_entity, entity_before, data):
            nonlocal update_after_executed
            update_after_executed = True
            # Verify entity has the modified description
            self.assertEqual(updated_entity.description, "Modified by update hook")

        # Register hooks
        hooks = get_hooks_for_manager(ManagerForTest)
        hooks["update"]["before"].append(before_update_hook)
        hooks["update"]["after"].append(after_update_hook)

        # Perform update
        test_id = str(uuid.uuid4())
        updated = self.manager.update(id=test_id, name="Updated Name")

        # Verify update and hooks
        self.assertIsNotNone(updated)
        self.assertEqual(updated.id, test_id)
        self.assertEqual(updated.name, "Updated Name")
        self.assertEqual(updated.description, "Modified by update hook")
        self.assertTrue(update_before_executed)
        self.assertTrue(update_after_executed)

        # Clean up hooks
        hooks["update"]["before"].remove(before_update_hook)
        hooks["update"]["after"].remove(after_update_hook)

    def test_delete_operation(self):
        """Test deleting an entity."""
        # Setup delete hooks for testing
        delete_before_executed = False
        delete_after_executed = False

        def before_delete_hook(manager, id, entity_before):
            nonlocal delete_before_executed
            delete_before_executed = True
            # Verify entity exists before deletion
            self.assertIsNotNone(entity_before)

        def after_delete_hook(manager, id, entity_before):
            nonlocal delete_after_executed
            delete_after_executed = True
            # Verify we have the ID and entity data
            self.assertIsNotNone(id)
            self.assertIsNotNone(entity_before)

        # Register hooks
        hooks = get_hooks_for_manager(ManagerForTest)
        hooks["delete"]["before"].append(before_delete_hook)
        hooks["delete"]["after"].append(after_delete_hook)

        # Perform delete
        test_id = str(uuid.uuid4())
        self.manager.delete(id=test_id)

        # Verify hooks executed
        self.assertTrue(delete_before_executed)
        self.assertTrue(delete_after_executed)

        # Clean up hooks
        hooks["delete"]["before"].remove(before_delete_hook)
        hooks["delete"]["after"].remove(after_delete_hook)

    def test_search_operation(self):
        """Test searching entities with various filters."""
        # Simple search
        results = self.manager.search(name="Test")
        self.assertIsInstance(results, list)

        # Search with string pattern
        results = self.manager.search(name={"inc": "Test"})
        self.assertIsInstance(results, list)

        # Test with custom search transformer
        # In AbstractLogicManager.search(), only dictionary parameters are passed to build_search_filters
        # So we need to use a dict value for custom_search to ensure it's passed to build_search_filters
        custom_search_value = {"value": "test value"}

        # Create a spy for the _transform_custom_search method
        transform_spy = MagicMock(side_effect=mock_transform_custom_search)

        # Register the spy as the search transformer
        self.manager.search_transformers = {"custom_search": transform_spy}

        # Mock the list method to avoid downstream errors
        with patch.object(self.manager.DBClass, "list", return_value=[]):
            self.manager.search(custom_search=custom_search_value)

            # Verify custom search transformer was called with the correct value
            transform_spy.assert_called_once_with(custom_search_value)

    def test_search_filter_building(self):
        """Test building of search filters."""
        # Create a mock SQLAlchemy field that can handle the ilike operation
        mock_field = MagicMock()
        mock_field.ilike.return_value = "mocked filter condition"

        # Patch the specific field access for the test
        with patch.object(MockDBModel, "name", mock_field):
            with patch.object(MockDBModel, "description", mock_field):
                with patch.object(self.manager, "get_field_types") as mock_get_types:
                    mock_get_types.return_value = (
                        ["name", "description"],  # string fields
                        ["count", "value"],  # numeric fields
                        ["created_at", "updated_at"],  # date fields
                        ["is_active"],  # boolean fields
                    )

                    # Test with various search parameters - using only the fields we've properly mocked
                    search_params = {
                        "name": {"inc": "test"},
                        "custom_search": "custom value",
                    }

                    # Register a custom transformer for testing
                    custom_transformer_called = False

                    def mock_custom_transformer(value):
                        nonlocal custom_transformer_called
                        custom_transformer_called = True
                        return [MagicMock()]

                    self.manager.search_transformers["custom_search"] = (
                        mock_custom_transformer
                    )

                    # Build filters
                    filters = self.manager.build_search_filters(search_params)

                    # Verify custom transformer was called
                    self.assertTrue(custom_transformer_called)
                    # Verify we got filters back
                    self.assertTrue(len(filters) > 0)

                    # Cleanup
                    del self.manager.search_transformers["custom_search"]

    def test_batch_update_operation(self):
        """Test batch updating entities."""
        items = [
            {
                "id": str(uuid.uuid4()),
                "data": {"name": "Updated 1", "description": "Batch Update 1"},
            },
            {
                "id": str(uuid.uuid4()),
                "data": {"name": "Updated 2", "description": "Batch Update 2"},
            },
        ]

        results = self.manager.batch_update(items)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "Updated 1")
        self.assertEqual(results[1].name, "Updated 2")

    def test_batch_delete_operation(self):
        """Test batch deleting entities."""
        # Create some IDs to delete
        ids = [str(uuid.uuid4()) for _ in range(3)]

        # Mock the delete method to track calls
        original_delete = self.manager.delete
        delete_calls = []

        def mock_delete(id):
            delete_calls.append(id)
            return original_delete(id)

        self.manager.delete = mock_delete

        # Execute batch delete
        self.manager.batch_delete(ids)

        # Verify all IDs were deleted
        self.assertEqual(len(delete_calls), 3)
        for id in ids:
            self.assertIn(id, delete_calls)

        # Restore original method
        self.manager.delete = original_delete

    def test_hook_dict_access(self):
        """Test HookDict attribute access."""
        hook_dict = HookDict({"test": {"nested": "value"}})

        # Test attribute access
        self.assertEqual(hook_dict.test.nested, "value")

        # Test attribute setting
        hook_dict.new_attr = "new value"
        self.assertEqual(hook_dict["new_attr"], "new value")

        # Test attribute error
        with self.assertRaises(AttributeError):
            _ = hook_dict.nonexistent


if __name__ == "__main__":
    unittest.main()
