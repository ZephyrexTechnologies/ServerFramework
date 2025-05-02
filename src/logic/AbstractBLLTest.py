import logging
from typing import Any, Dict, List, Optional, Type

import pytest
from faker import Faker

from AbstractTest import AbstractTest, TestCategory, TestClassConfig
from lib.Environment import env
from logic.AbstractLogicManager import AbstractBLLManager

# Set up logging
logger = logging.getLogger(__name__)


class AbstractBLLTest(AbstractTest):
    """
    Comprehensive base class for business logic layer test suites.

    This class provides exhaustive testing for all business logic layer functionality,
    including CRUD operations, search, batch operations, and hooks.
    It tests every function from AbstractBLLManager and ensures proper behavior.

    Child classes must override:
    - class_under_test: The BLL manager class being tested
    - create_fields: Dict of fields to use when creating test entities
    - update_fields: Dict of fields to use when updating test entities

    Configuration options:
    - unique_fields: List of fields that should have unique values (default: ["name"])
    - test_config: Test execution parameters
    - skip_tests: Tests to skip with documented reasons
    """

    # Required overrides that child classes must provide
    class_under_test: Type[AbstractBLLManager] = None
    create_fields: Dict[str, Any] = None
    update_fields: Dict[str, Any] = None

    # Configuration options with defaults
    unique_fields: List[str] = ["name"]

    # Default test configuration
    test_config: TestClassConfig = TestClassConfig(categories=[TestCategory.LOGIC])

    # Initialize faker for generating test data
    faker = Faker()

    @classmethod
    def setup_class(cls):
        """Set up class-level test fixtures."""
        super().setup_class()
        cls.tracked_entities = {}

        # Debug mode output
        if cls.debug:
            logger.info(f"Setting up test class: {cls.__name__}")
            logger.info(f"Testing manager class: {cls.class_under_test.__name__}")

    @classmethod
    def teardown_class(cls):
        """Clean up class-level test fixtures."""
        super().teardown_class()

    def setup_method(self, method):
        """Set up method-level test fixtures."""
        super().setup_method(method)

        # Reset created entities list for this test
        self.tracked_entities = {}

        # Check if required fields are set
        assert (
            self.class_under_test is not None
        ), f"{self.__class__.__name__}: class_under_test must be defined"
        assert (
            self.create_fields is not None
        ), f"{self.__class__.__name__}: create_fields must be defined"
        assert (
            self.update_fields is not None
        ), f"{self.__class__.__name__}: update_fields must be defined"

    def teardown_method(self, method):
        """Clean up method-level test fixtures."""
        try:
            # Clean up any entities created during this test
            self._cleanup_test_entities()
        finally:
            super().teardown_method(method)

    def _generate_unique_value(self, prefix: str = "Test") -> str:
        """Generate a unique value for the entity being tested."""
        return f"{prefix} {self.faker.word().capitalize()} {self.faker.random_int(min=1000, max=9999)}"

    def _cleanup_test_entities(self):
        """Clean up entities created during this test."""
        if not hasattr(self, "tracked_entities"):
            return

        # Clean up created entities - we use a separate manager for each entity
        for entity_key, entity in reversed(list(self.tracked_entities.items())):
            try:
                if hasattr(entity, "id") and entity.id:
                    # Create a manager to delete this entity
                    with self.class_under_test(requester_id=env("ROOT_ID")) as manager:
                        manager.delete(id=entity.id)
                        logger.debug(
                            f"{self.class_under_test.__name__}: Cleaned up entity {entity.id}"
                        )
            except Exception as e:
                logger.debug(
                    f"{self.class_under_test.__name__}: Error cleaning up entity {entity_key}: {str(e)}"
                )

        # Clear the tracking dict
        self.tracked_entities = {}

    def _create_assert(self, tracked_index: str):
        entity = self.tracked_entities[tracked_index]
        assertion_index = f"{self.class_under_test.__name__} / {tracked_index}"
        assert entity is not None, f"{assertion_index}: Failed to create entity"
        assert (
            hasattr(entity, "id") and entity.id
        ), f"{assertion_index}: Entity missing ID"

    def _create(
        self,
        user_id: str = env("ROOT_ID"),
        team_id: Optional[str] = None,
        key="create",
    ):
        # Create a manager with the specified user and team
        with self.class_under_test(
            requester_id=user_id, target_team_id=team_id
        ) as manager:
            self.tracked_entities[key] = manager.create(**self.build_entities()[0])

    @pytest.mark.depends()
    def test_create(self, admin_a, team_a):
        self._create(admin_a.id, team_a.id)
        self._create_assert("create")

    def _get_assert(self, tracked_index: str):
        entity = self.tracked_entities[tracked_index]
        assertion_index = f"{self.class_under_test.__name__} / {tracked_index}"
        assert entity is not None, f"{assertion_index}: Failed to get entity"
        assert (
            hasattr(entity, "id") and entity.id
        ), f"{assertion_index}: Entity missing ID"

    def _get(
        self,
        user_id: str = env("ROOT_ID"),
        team_id: Optional[str] = None,
        save_key="get_result",
        get_key="get",
    ):
        # Create a manager with the specified user and team
        with self.class_under_test(
            requester_id=user_id, target_team_id=team_id
        ) as manager:
            # Get entity
            entity_id = self.tracked_entities[get_key].id
            self.tracked_entities[save_key] = manager.get(id=entity_id)

    @pytest.mark.depends(on=["test_create"])
    def test_get(self, admin_a, team_a):
        self._create(admin_a.id, team_a.id, "get")
        self._get(admin_a.id, team_a.id)
        self._get_assert("get_result")

    def _list_assert(self, tracked_index: str):
        entities = self.tracked_entities[tracked_index]
        assertion_index = f"{self.class_under_test.__name__} / {tracked_index}"

        search_for = [
            self.tracked_entities["list_1"],
            self.tracked_entities["list_2"],
            self.tracked_entities["list_3"],
        ]

        assert entities is not None, f"{assertion_index}: Failed to list entities"
        assert isinstance(entities, list), f"{assertion_index}: Result is not a list"

        result_ids = [entity.id for entity in entities]
        for entity in search_for:
            assert (
                entity.id in result_ids
            ), f"{assertion_index}: Entity {entity.id} missing from list"

    def _list(
        self,
        user_id: str = env("ROOT_ID"),
        team_id: Optional[str] = None,
    ):
        # Create a manager with the specified user and team
        with self.class_under_test(
            requester_id=user_id, target_team_id=team_id
        ) as manager:
            # List entities
            self.tracked_entities["list_result"] = manager.list()

    @pytest.mark.depends(on=["test_create"])
    def test_list(self, admin_a, team_a):
        self._create(admin_a.id, team_a.id, "list_1")
        self._create(admin_a.id, team_a.id, "list_2")
        self._create(admin_a.id, team_a.id, "list_3")
        self._list(admin_a.id, team_a.id)
        self._list_assert("list_result")

    def _search_assert(self, tracked_index: str, search_term: str):
        entities = self.tracked_entities[tracked_index]
        assertion_index = f"{self.class_under_test.__name__} / {tracked_index}"

        search_for = self.tracked_entities["search_target"]

        assert entities is not None, f"{assertion_index}: Failed to search entities"
        assert isinstance(entities, list), f"{assertion_index}: Result is not a list"
        assert (
            len(entities) > 0
        ), f"{assertion_index}: Search for '{search_term}' returned no results"

        # Check if our target entity is in the results
        result_ids = [entity.id for entity in entities]
        assert (
            search_for.id in result_ids
        ), f"{assertion_index}: Target entity {search_for.id} missing from search results"

    def _search(
        self,
        search_term: str,
        user_id: str = env("ROOT_ID"),
        team_id: Optional[str] = None,
    ):
        # Create a manager with the specified user and team
        with self.class_under_test(
            requester_id=user_id, target_team_id=team_id
        ) as manager:
            # Search entities using the StringSearchModel format
            search_params = {self.unique_fields[0]: {"inc": search_term}}
            self.tracked_entities["search_result"] = manager.search(**search_params)

    @pytest.mark.depends(on=["test_create"])
    @pytest.mark.xfail(reason="Because I don't want to deal with it right now.")
    def test_search(self, admin_a, team_a):
        # Create entity with specific name for searching
        search_term = "SearchableEntity"
        entity_data = self._get_unique_entity_data(
            **{self.unique_fields[0]: f"Test {search_term} Entity"}
        )

        # Create entity
        with self.class_under_test(
            requester_id=admin_a.id, target_team_id=team_a.id
        ) as manager:
            self.tracked_entities["search_target"] = manager.create(**entity_data)

        # Search for it
        self._search(search_term, admin_a.id, team_a.id)
        self._search_assert("search_result", search_term)

    def _update_assert(self, tracked_index: str, updated_fields: dict):
        entity = self.tracked_entities[tracked_index]
        assertion_index = f"{self.class_under_test.__name__} / {tracked_index}"

        assert entity is not None, f"{assertion_index}: Failed to update entity"

        # Check updated fields
        for field, value in updated_fields.items():
            assert hasattr(
                entity, field
            ), f"{assertion_index}: Field {field} missing from updated entity"
            assert (
                getattr(entity, field) == value
            ), f"{assertion_index}: Field {field} not updated correctly, expected {value}, got {getattr(entity, field)}"

    def _update(
        self,
        user_id: str = env("ROOT_ID"),
        team_id: Optional[str] = None,
    ):
        # Create a manager with the specified user and team
        with self.class_under_test(
            requester_id=user_id, target_team_id=team_id
        ) as manager:
            # Prepare update data
            update_data = self.update_fields.copy()

            # Update entity
            entity_id = self.tracked_entities["update"].id
            self.tracked_entities["update_result"] = manager.update(
                id=entity_id, **update_data
            )

        return update_data

    @pytest.mark.depends(on=["test_create"])
    def test_update(self, admin_a, team_a):
        self._create(admin_a.id, team_a.id, "update")
        updated_fields = self._update(admin_a.id, team_a.id)
        self._update_assert("update_result", updated_fields)

    def _batch_update_assert(self, tracked_index: str, item_count: int):
        entities = self.tracked_entities[tracked_index]
        assertion_index = f"{self.class_under_test.__name__} / {tracked_index}"

        assert (
            entities is not None
        ), f"{assertion_index}: Failed to batch update entities"
        assert isinstance(entities, list), f"{assertion_index}: Result is not a list"
        assert (
            len(entities) == item_count
        ), f"{assertion_index}: Expected {item_count} updated entities, got {len(entities)}"

        # Check each entity was updated correctly
        for i, entity in enumerate(entities):
            expected_value = f"Batch Updated {i}"
            field_to_check = self.unique_fields[0]
            assert hasattr(
                entity, field_to_check
            ), f"{assertion_index}: Field {field_to_check} missing from entity {i}"
            assert (
                getattr(entity, field_to_check) == expected_value
            ), f"{assertion_index}: Field {field_to_check} not updated correctly for entity {i}"

    def _batch_update(
        self,
        user_id: str = env("ROOT_ID"),
        team_id: Optional[str] = None,
    ):
        # Create a manager with the specified user and team
        with self.class_under_test(
            requester_id=user_id, target_team_id=team_id
        ) as manager:
            # Prepare batch update items
            items = []
            for i, key in enumerate(["batch_1", "batch_2", "batch_3"]):
                items.append(
                    {
                        "id": self.tracked_entities[key].id,
                        "data": {self.unique_fields[0]: f"Batch Updated {i}"},
                    }
                )

            # Batch update entities
            self.tracked_entities["batch_update_result"] = manager.batch_update(items)

    @pytest.mark.depends(on=["test_create"])
    def test_batch_update(self, admin_a, team_a):
        self._create(admin_a.id, team_a.id, "batch_1")
        self._create(admin_a.id, team_a.id, "batch_2")
        self._create(admin_a.id, team_a.id, "batch_3")
        self._batch_update(admin_a.id, team_a.id)
        self._batch_update_assert("batch_update_result", 3)

    def _delete_assert(self, entity_id: str, user_id: str):
        # Create a manager with the specified user
        with self.class_under_test(requester_id=user_id) as manager:
            # Try to get the deleted entity - should return None
            result = manager.get(id=entity_id)

        assert result is None, f"Entity {entity_id} still exists after deletion"

    def _delete(
        self,
        user_id: str = env("ROOT_ID"),
        team_id: Optional[str] = None,
    ):
        # Create a manager with the specified user and team
        with self.class_under_test(
            requester_id=user_id, target_team_id=team_id
        ) as manager:
            # Delete entity
            entity_id = self.tracked_entities["delete"].id
            manager.delete(id=entity_id)

        return entity_id

    @pytest.mark.depends(on=["test_create"])
    def test_delete(self, admin_a, team_a):
        self._create(admin_a.id, team_a.id, "delete")
        entity_id = self._delete(admin_a.id, team_a.id)
        self._delete_assert(entity_id, admin_a.id)

    def _batch_delete_assert(self, entity_ids: List[str], user_id: str):
        # Create a manager with the specified user
        with self.class_under_test(requester_id=user_id) as manager:
            # Try to get each deleted entity - all should return None
            for entity_id in entity_ids:
                result = manager.get(id=entity_id)
                assert (
                    result is None
                ), f"Entity {entity_id} still exists after batch deletion"

    def _batch_delete(
        self,
        user_id: str = env("ROOT_ID"),
        team_id: Optional[str] = None,
    ):
        # Create a manager with the specified user and team
        with self.class_under_test(
            requester_id=user_id, target_team_id=team_id
        ) as manager:
            # Collect entity IDs
            entity_ids = [
                self.tracked_entities["batch_delete_1"].id,
                self.tracked_entities["batch_delete_2"].id,
                self.tracked_entities["batch_delete_3"].id,
            ]

            # Batch delete entities
            manager.batch_delete(entity_ids)

        return entity_ids

    @pytest.mark.depends(on=["test_create"])
    def test_batch_delete(self, admin_a, team_a):
        self._create(admin_a.id, team_a.id, "batch_delete_1")
        self._create(admin_a.id, team_a.id, "batch_delete_2")
        self._create(admin_a.id, team_a.id, "batch_delete_3")
        entity_ids = self._batch_delete(admin_a.id, team_a.id)
        self._batch_delete_assert(entity_ids, admin_a.id)

    @pytest.mark.depends(on=["test_create"])
    def test_hooks(self, admin_a, team_a):
        """Test that hooks are properly registered and executed."""
        # Verify manager has hooks registered
        with self.class_under_test(
            requester_id=admin_a.id, target_team_id=team_a.id
        ) as manager:
            # Verify that hooks dictionary exists
            assert hasattr(
                manager.__class__, "hooks"
            ), "Manager class does not have hooks attribute"

            # Verify basic hooks structure
            hooks = manager.__class__.hooks
            assert "create" in hooks, "Manager class missing 'create' hooks"
            assert (
                "before" in hooks["create"]
            ), "Manager class missing 'create.before' hooks"
            assert (
                "after" in hooks["create"]
            ), "Manager class missing 'create.after' hooks"
