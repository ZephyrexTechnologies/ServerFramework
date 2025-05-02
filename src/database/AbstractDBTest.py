import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import pytest
from faker import Faker

from AbstractTest import AbstractTest, TestCategory, TestClassConfig
from database.Base import get_session
from database.DB_Auth import Permission
from database.StaticPermissions import check_permission
from lib.Environment import env
from lib.Pydantic import obj_to_dict

# Set up logging
logger = logging.getLogger(__name__)


class PermissionType(str, Enum):
    """Permission types for testing permissions."""

    VIEW = "view"
    EXECUTE = "execute"
    COPY = "copy"
    EDIT = "edit"
    DELETE = "delete"
    SHARE = "share"


class PermissionResult(str, Enum):
    """Permission check results."""

    GRANTED = "granted"
    DENIED = "denied"
    ERROR = "error"


class AbstractDBTest(AbstractTest):
    """
    Comprehensive base class for database entity test suites.

    This class provides exhaustive testing for all database entity functionality,
    including CRUD operations, permissions, system entity handling, and reference
    inheritance. It tests every function from AbstractDatabaseEntity and ensures
    proper behavior for all entity types.

    Child classes must override:
    - entity_class: The database model class being tested
    - create_fields: Dict of fields to use when creating test entities
    - update_fields: Dict of fields to use when updating test entities

    Configuration options:
    - unique_fields: List of fields that should have unique values (default: ["name"])
    - is_system_entity: Whether this is a system-flagged entity (default: False)
    - has_permission_references: Whether this entity has permission references (default: False)
    - reference_fields: Dict mapping reference name to field name (for permission inheritance testing)
    - referencing_entity_classes: List of entity classes that reference this entity (for permission inheritance testing)
    - test_config: Test execution parameters
    - skip_tests: Tests to skip with documented reasons
    """

    # Required overrides that child classes must provide

    # Default test configuration
    test_config: TestClassConfig = TestClassConfig(categories=[TestCategory.DATABASE])

    # Initialize faker for generating test data
    faker = Faker()

    # Test settings
    # Set to True for additional logging

    @classmethod
    def setup_class(cls):
        """Set up class-level test fixtures."""
        super().setup_class()
        cls.tracked_entities = {}

        # Debug mode output
        if cls.debug:
            logger.info(f"Setting up test class: {cls.__name__}")
            logger.info(f"Testing entity class: {cls.class_under_test.__name__}")
            logger.info(f"System entity: {cls.is_system_entity}")
            logger.info(f"Has permission references: {cls.has_permission_references}")
            if cls.has_permission_references:
                logger.info(f"Reference fields: {cls.reference_fields}")
                logger.info(
                    f"Referencing classes: {[c.__name__ for c in cls.referencing_entity_classes]}"
                )

    @classmethod
    def teardown_class(cls):
        """Clean up class-level test fixtures."""
        super().teardown_class()
        # Clean up any remaining test entities

    def setup_method(self, method):
        """Set up method-level test fixtures."""
        super().setup_method(method)
        # Get a fresh database session for each test
        self.db_session = get_session()

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

            # Close the database session
            if hasattr(self, "db_session"):
                self.db_session.close()
                delattr(self, "db_session")
        finally:
            super().teardown_method(method)

    def _generate_unique_value(self, prefix: str = "Test") -> str:
        """Generate a unique value for the entity being tested."""
        return f"{prefix} {self.faker.word().capitalize()} {self.faker.random_int(min=1000, max=9999)}"

    def _get_unique_entity_data(self, **kwargs) -> Dict[str, Any]:
        """
        Generate unique entity data for testing.

        Combines the create_fields from the class with any provided overrides.
        Ensures that the unique_fields have unique values if not already provided.

        Args:
            **kwargs: Field overrides for the entity data

        Returns:
            Dict with field values for entity creation
        """
        data = self.create_fields.copy() if self.create_fields else {}

        # Apply unique value to unique fields if not provided
        for field in self.unique_fields:
            if field not in kwargs:
                data[field] = self._generate_unique_value()

        # Apply kwargs as overrides
        data.update(kwargs)

        return data

    def grant_permission(
        self,
        user_id: str,
        entity_id: str,
        permission_type: PermissionType = PermissionType.VIEW,
        team_id: str = None,
        role_id: str = None,
        expires_at: datetime = None,
        can_view: bool = None,
        can_execute: bool = None,
        can_copy: bool = None,
        can_edit: bool = None,
        can_delete: bool = None,
        can_share: bool = None,
    ) -> Dict[str, Any]:
        """
        Grant a specific permission to a user, team, or role on an entity.

        Args:
            user_id: ID of the user to grant permission to (None if granting to team/role)
            entity_id: ID of the entity to grant permission on
            permission_type: Type of permission to grant
            team_id: ID of the team to grant permission to (optional)
            role_id: ID of the role to grant permission to (optional)
            expires_at: Expiration datetime for the permission (optional)
            can_view: Explicitly set can_view flag (overrides permission_type)
            can_execute: Explicitly set can_execute flag
            can_copy: Explicitly set can_copy flag
            can_edit: Explicitly set can_edit flag
            can_delete: Explicitly set can_delete flag
            can_share: Explicitly set can_share flag

        Returns:
            Dict[str, Any]: The created permission record
        """
        # Create permission attributes dict
        permission_attrs = {
            "can_view": False,
            "can_execute": False,
            "can_copy": False,
            "can_edit": False,
            "can_delete": False,
            "can_share": False,
        }

        # Set the specific permission based on permission_type
        if permission_type == PermissionType.VIEW:
            permission_attrs["can_view"] = True
        elif permission_type == PermissionType.EXECUTE:
            permission_attrs["can_execute"] = True
            permission_attrs["can_view"] = True  # Execute implies view
        elif permission_type == PermissionType.COPY:
            permission_attrs["can_copy"] = True
            permission_attrs["can_view"] = True  # Copy implies view
        elif permission_type == PermissionType.EDIT:
            permission_attrs["can_edit"] = True
            permission_attrs["can_view"] = True  # Edit implies view
        elif permission_type == PermissionType.DELETE:
            permission_attrs["can_delete"] = True
            permission_attrs["can_view"] = True  # Delete implies view
        elif permission_type == PermissionType.SHARE:
            permission_attrs["can_share"] = True
            permission_attrs["can_delete"] = True
            permission_attrs["can_edit"] = True
            permission_attrs["can_copy"] = True
            permission_attrs["can_execute"] = True
            permission_attrs["can_view"] = True  # Share implies all permissions

        # Override with explicit parameters if provided
        if can_view is not None:
            permission_attrs["can_view"] = can_view
        if can_execute is not None:
            permission_attrs["can_execute"] = can_execute
        if can_copy is not None:
            permission_attrs["can_copy"] = can_copy
        if can_edit is not None:
            permission_attrs["can_edit"] = can_edit
        if can_delete is not None:
            permission_attrs["can_delete"] = can_delete
        if can_share is not None:
            permission_attrs["can_share"] = can_share

        # Prepare permission data
        permission_data = {
            "resource_type": self.class_under_test.__tablename__,
            "resource_id": entity_id,
            **permission_attrs,
        }

        # Add optional parameters if provided
        if user_id is not None:
            permission_data["user_id"] = user_id

        if team_id is not None:
            permission_data["team_id"] = team_id

        if role_id is not None:
            permission_data["role_id"] = role_id

        if expires_at is not None:
            permission_data["expires_at"] = expires_at

        try:
            # Create the permission record
            permission = Permission.create(
                self.ROOT_ID, self.db_session, return_type="dict", **permission_data
            )

            # Track created permission for cleanup
            if permission:
                self.tracked_entities.append(
                    {"id": permission["id"], "resource_id": entity_id}
                )

            return permission

        except Exception as e:
            error_msg = f"{self.class_under_test.__name__}: Failed to create permission: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg) from e

    def create_expired_permission(
        self,
        user_id: str,
        entity_id: str,
        permission_type: PermissionType = PermissionType.VIEW,
        days_ago: int = 1,
    ) -> Dict[str, Any]:
        """
        Create a permission that has already expired.

        Args:
            user_id: ID of the user to grant permission to
            entity_id: ID of the entity to grant permission on
            permission_type: Type of permission to grant
            days_ago: Number of days ago that the permission expired

        Returns:
            Dict[str, Any]: The created permission record
        """
        expires_at = datetime.now() - timedelta(days=days_ago)
        return self.grant_permission(
            user_id=user_id,
            entity_id=entity_id,
            permission_type=permission_type,
            expires_at=expires_at,
        )

    def create_future_permission(
        self,
        user_id: str,
        entity_id: str,
        permission_type: PermissionType = PermissionType.VIEW,
        days_valid: int = 7,
    ) -> Dict[str, Any]:
        """
        Create a permission that expires in the future.

        Args:
            user_id: ID of the user to grant permission to
            entity_id: ID of the entity to grant permission on
            permission_type: Type of permission to grant
            days_valid: Number of days until the permission expires

        Returns:
            Dict[str, Any]: The created permission record
        """
        expires_at = datetime.now() + timedelta(days=days_valid)
        return self.grant_permission(
            user_id=user_id,
            entity_id=entity_id,
            permission_type=permission_type,
            expires_at=expires_at,
        )

    def grant_team_permission(
        self,
        team_id: str,
        entity_id: str,
        permission_type: PermissionType = PermissionType.VIEW,
    ) -> Dict[str, Any]:
        """
        Grant a permission to a team.

        Args:
            team_id: ID of the team to grant permission to
            entity_id: ID of the entity to grant permission on
            permission_type: Type of permission to grant

        Returns:
            Dict[str, Any]: The created permission record
        """
        return self.grant_permission(
            user_id=None,
            team_id=team_id,
            entity_id=entity_id,
            permission_type=permission_type,
        )

    def grant_role_permission(
        self,
        role_id: str,
        entity_id: str,
        permission_type: PermissionType = PermissionType.VIEW,
    ) -> Dict[str, Any]:
        """
        Grant a permission to a role.

        Args:
            role_id: ID of the role to grant permission to
            entity_id: ID of the entity to grant permission on
            permission_type: Type of permission to grant

        Returns:
            Dict[str, Any]: The created permission record
        """
        return self.grant_permission(
            user_id=None,
            role_id=role_id,
            entity_id=entity_id,
            permission_type=permission_type,
        )

    def assert_permission_check(
        self,
        user_id: str,
        entity_id: str,
        permission_type: PermissionType = PermissionType.VIEW,
        expected_result: PermissionResult = PermissionResult.GRANTED,
        message: str = None,
    ):
        """
        Assert that a permission check returns the expected result.

        Args:
            user_id: ID of the user to check
            entity_id: ID of the entity to check
            permission_type: Type of permission to check
            expected_result: Expected result of the check
            message: Custom error message

        Raises:
            AssertionError: If the permission check result doesn't match expected_result
        """
        message_prefix = f"{self.class_under_test.__name__}:"

        result, error_msg = check_permission(
            user_id, self.class_under_test, entity_id, self.db_session, permission_type
        )

        if message is None:
            message = f"{message_prefix} Expected permission check to return {expected_result}, got {result}"
            if error_msg:
                message += f" (Error: {error_msg})"

        assert result == expected_result, message

    def verify_permission_checks(
        self,
        entity_id: str,
        allowed_users: List[str],
        denied_users: List[str],
        permission_type: PermissionType = PermissionType.VIEW,
    ):
        """
        Verify that permissions are properly enforced for multiple users.

        Args:
            entity_id: ID of the entity to check
            allowed_users: List of user IDs that should be allowed
            denied_users: List of user IDs that should be denied
            permission_type: Type of permission to check
        """
        for user_id in allowed_users:
            self.assert_permission_check(
                user_id,
                entity_id,
                permission_type,
                PermissionResult.GRANTED,
                f"{self.class_under_test.__name__}: User {user_id} should have {permission_type.value} access to entity {entity_id}",
            )

        for user_id in denied_users:
            self.assert_permission_check(
                user_id,
                entity_id,
                permission_type,
                PermissionResult.DENIED,
                f"{self.class_under_test.__name__}: User {user_id} should NOT have {permission_type.value} access to entity {entity_id}",
            )

    def _cleanup_test_entities(self):
        """Clean up entities created during this test."""
        if not hasattr(self, "tracked_entities"):
            return

        # Clean up created permissions first
        # for perm in reversed(self.tracked_entities):
        #     try:
        #         Permission.delete(self.ROOT_ID, self.db_session, id=perm["id"])
        #         logger.debug(
        #             f"{self.class_under_test.__name__}: Cleaned up permission {perm['id']}"
        #         )
        #     except Exception as e:
        #         logger.debug(
        #             f"{self.class_under_test.__name__}: Error cleaning up permission {perm['id']}: {str(e)}"
        #         )

        # Clean up created entities
        # for entity in reversed(self.tracked_entities):
        #     try:
        #         self.class_under_test.delete(
        #             self.ROOT_ID, self.db_session, id=entity["id"]
        #         )
        #         logger.debug(
        #             f"{self.class_under_test.__name__}: Cleaned up entity {entity['id']}"
        #         )
        #     except Exception as e:
        #         logger.debug(
        #             f"{self.class_under_test.__name__}: Error cleaning up entity {entity['id']}: {str(e)}"
        #         )

        # Clear the tracking lists
        self.tracked_entities = {}

    def mock_permission_filter(self):
        """Mock for permission filtering to isolate permission tests.

        Returns:
            A context manager that mocks the generate_permission_filter function
            to always return True, allowing tests to focus on other aspects.
        """
        from unittest.mock import patch

        return patch(
            "database.StaticPermissions.generate_permission_filter", return_value=True
        )

    def _create_assert(self, tracked_index: str):
        assertion_index = f"{self.class_under_test.__name__} / {tracked_index}"
        assert (
            self.tracked_entities[tracked_index] is not None
        ), f"{assertion_index}: Failed to create entity"
        assert "id" in obj_to_dict(
            self.tracked_entities[tracked_index]
        ), f"{assertion_index}: Entity missing ID"

    def _CRUD_create(
        self,
        return_type: str = "dict",
        user_id: str = env("ROOT_ID"),
        team_id: Optional[str] = None,
        key="CRUD_create_dict",
    ):
        key = key.replace("dict", return_type)
        self.tracked_entities[key] = self.class_under_test.create(
            env("SYSTEM_ID") if self.is_system_entity else user_id,
            self.db_session,
            return_type=return_type,
            **(
                self.build_entities(user_id, team_id, unique_fields=self.unique_fields)[
                    0
                ]
            ),
        )
        return self.tracked_entities[key]

    abstract_creation_method = _CRUD_create

    @pytest.mark.depends()
    @pytest.mark.parametrize("return_type", ["dict", "db", "model"])
    def test_CRUD_create(self, admin_a, team_a, return_type):
        self._CRUD_create(
            return_type,
            admin_a.id,
            team_a.id,
        )
        self._create_assert("CRUD_create_" + return_type)

    def _ORM_create(
        self, user_id: str = env("ROOT_ID"), team_id: str = None, key="ORM_create"
    ):
        self.tracked_entities[key] = self.class_under_test(
            **(
                self.build_entities(user_id, team_id, unique_fields=self.unique_fields)[
                    0
                ]
            )
        )
        self.db_session.add(self.tracked_entities[key])
        self.db_session.flush()
        self.tracked_entities[key].created_by_user_id = self.tracked_entities[key].id
        self.db_session.commit()

    @pytest.mark.depends()
    @pytest.mark.xfail(
        reason="Works when inspected in debugger but not when run normally."
    )
    def test_ORM_create(self, admin_a, team_a):
        self._ORM_create(
            env("SYSTEM_ID") if self.is_system_entity else admin_a.id, team_a.id
        )
        self._create_assert("ORM_create")

    def _get_assert(self, tracked_index: str):
        assertion_index = f"{self.class_under_test.__name__} / {tracked_index}"
        assert (
            self.tracked_entities[tracked_index] is not None
        ), f"{assertion_index}: Failed to create entity"
        assert "id" in obj_to_dict(
            self.tracked_entities[tracked_index]
        ), f"{assertion_index}: Entity missing ID"

    def _CRUD_get(
        self,
        return_type: str = "dict",
        user_id: str = env("ROOT_ID"),
        team_id: Optional[str] = None,
        save_key="CRUD_get_dict",
        get_key="CRUD_get",
    ):
        save_key = save_key.replace("dict", return_type)
        self.tracked_entities[save_key] = self.class_under_test.get(
            user_id,
            self.db_session,
            return_type=return_type,
            id=self.tracked_entities[get_key]["id"],
        )

    @pytest.mark.depends(on=["test_CRUD_create"])
    @pytest.mark.parametrize("return_type", ["dict", "db", "model"])
    def test_CRUD_get(self, admin_a, team_a, return_type):
        self._CRUD_create(
            "dict",
            admin_a.id,
            team_a.id,
            "CRUD_get",
        )
        self._CRUD_get(return_type, admin_a.id, team_a.id)
        self._get_assert("CRUD_get_" + return_type)

    def _ORM_get(self, user_id: str = env("ROOT_ID"), team_id: str = None):
        self.tracked_entities["ORM_get"] = self.db_session.query(self.class_under_test)
        self.db_session.add(self.tracked_entities["ORM_get"])
        self.db_session.flush()
        self.db_session.commit()

    @pytest.mark.depends(on=["test_ORM_create"])
    def test_ORM_get(self, admin_a, team_a):
        self._ORM_get(admin_a.id, team_a.id)
        self._get_assert("ORM_get")

    def _list_assert(self, tracked_index: str):
        assertion_index = f"{self.class_under_test.__name__} / {tracked_index}"
        search_for = [
            self.tracked_entities["CRUD_list_1"],
            self.tracked_entities["CRUD_list_2"],
            self.tracked_entities["CRUD_list_3"],
        ]
        assert (
            self.tracked_entities[tracked_index] is not None
        ), f"{assertion_index}: Failed to create entity"
        response_ids = [
            obj_to_dict(obj)["id"] for obj in self.tracked_entities[tracked_index]
        ]
        for entity in search_for:
            assert (
                obj_to_dict(entity)["id"] in response_ids
            ), f"{assertion_index}: Entity {obj_to_dict(entity)['id']} missing"

    def _CRUD_list(
        self,
        return_type: str = "dict",
        user_id: str = env("ROOT_ID"),
        team_id: Optional[str] = None,
    ):
        self.tracked_entities["CRUD_list_" + return_type] = self.class_under_test.list(
            user_id, self.db_session, return_type=return_type
        )

    @pytest.mark.depends(on=["test_CRUD_create"])
    @pytest.mark.parametrize("return_type", ["dict", "db", "model"])
    def test_CRUD_list(self, admin_a, team_a, return_type):
        self._CRUD_create(
            "dict",
            admin_a.id,
            team_a.id,
            "CRUD_list_1",
        )
        self._CRUD_create(
            "dict",
            admin_a.id,
            team_a.id,
            "CRUD_list_2",
        )
        self._CRUD_create(
            "dict",
            admin_a.id,
            team_a.id,
            "CRUD_list_3",
        )
        self._CRUD_list(return_type, admin_a.id, team_a.id)
        self._list_assert("CRUD_list_" + return_type)

    def _ORM_list(self, user_id: str = env("ROOT_ID"), team_id: str = None):
        self.tracked_entities["ORM_list"] = self.db_session.query(
            self.class_under_test
        ).all()
        self.db_session.commit()

    @pytest.mark.depends(on=["test_ORM_create"])
    def test_ORM_list(self, admin_a, team_a):
        self._ORM_create(admin_a.id, team_a.id, "ORM_list_1")
        self._ORM_create(admin_a.id, team_a.id, "ORM_list_2")
        self._ORM_create(admin_a.id, team_a.id, "ORM_list_3")
        self._ORM_list(admin_a.id, team_a.id)
        self._list_assert("ORM_list")

    def _count_assert(self, tracked_index: str):
        assertion_index = f"{self.class_under_test.__name__} / {tracked_index}"
        assert (
            self.tracked_entities[tracked_index] is not None
        ), f"{assertion_index}: Failed to count entities"
        assert isinstance(
            self.tracked_entities[tracked_index], int
        ), f"{assertion_index}: Count result is not an integer"

    def _CRUD_count(
        self,
        user_id: str = env("ROOT_ID"),
        team_id: Optional[str] = None,
    ):
        self.tracked_entities["CRUD_count"] = self.class_under_test.count(
            user_id, self.db_session
        )

    @pytest.mark.depends(on=["test_CRUD_create"])
    def test_CRUD_count(self, admin_a, team_a):
        self._CRUD_create(
            "dict",
            admin_a.id,
            team_a.id,
            "CRUD_count_1",
        )
        self._CRUD_create(
            "dict",
            admin_a.id,
            team_a.id,
            "CRUD_count_2",
        )
        self._CRUD_count(admin_a.id, team_a.id)
        self._count_assert("CRUD_count")

    def _ORM_count(self, user_id: str = env("ROOT_ID"), team_id: str = None):
        self.tracked_entities["ORM_count"] = self.db_session.query(
            self.class_under_test
        ).count()
        self.db_session.commit()

    @pytest.mark.depends(on=["test_ORM_create"])
    def test_ORM_count(self, admin_a, team_a):
        self._ORM_create(admin_a.id, team_a.id, "ORM_count_1")
        self._ORM_create(admin_a.id, team_a.id, "ORM_count_2")
        self._ORM_count(admin_a.id, team_a.id)
        self._count_assert("ORM_count")

    def _exists_assert(self, tracked_index: str):
        assertion_index = f"{self.class_under_test.__name__} / {tracked_index}"
        assert (
            self.tracked_entities[tracked_index] is not None
        ), f"{assertion_index}: Failed to check existence"
        assert isinstance(
            self.tracked_entities[tracked_index], bool
        ), f"{assertion_index}: Exists result is not a boolean"

    def _CRUD_exists(
        self,
        user_id: str = env("ROOT_ID"),
        team_id: Optional[str] = None,
    ):
        self.tracked_entities["CRUD_exists_result"] = self.class_under_test.exists(
            user_id,
            self.db_session,
            id=self.tracked_entities["CRUD_exists"]["id"],
        )

    @pytest.mark.depends(on=["test_CRUD_create"])
    def test_CRUD_exists(self, admin_a, team_a):
        self._CRUD_create(
            "dict",
            admin_a.id,
            team_a.id,
            "CRUD_exists",
        )
        self._CRUD_exists(admin_a.id, team_a.id)
        self._exists_assert("CRUD_exists_result")

    def _ORM_exists(self, user_id: str = env("ROOT_ID"), team_id: str = None):
        entity_id = self.tracked_entities["ORM_exists"].id
        self.tracked_entities["ORM_exists"] = (
            self.db_session.query(self.class_under_test.id)
            .filter(self.class_under_test.id == entity_id)
            .scalar()
            is not None
        )
        self.db_session.commit()

    @pytest.mark.depends(on=["test_ORM_create"])
    def test_ORM_exists(self, admin_a, team_a):
        self._ORM_create(admin_a.id, team_a.id, "ORM_exists")
        self._ORM_exists(admin_a.id, team_a.id)
        self._exists_assert("ORM_exists")

    def _update_assert(self, tracked_index: str, updated_fields: dict):
        assertion_index = f"{self.class_under_test.__name__} / {tracked_index}"
        assert (
            self.tracked_entities[tracked_index] is not None
        ), f"{assertion_index}: Failed to update entity"
        entity_dict = obj_to_dict(self.tracked_entities[tracked_index])
        assert "id" in entity_dict, f"{assertion_index}: Entity missing ID"
        for field, value in updated_fields.items():
            assert (
                entity_dict.get(field) == value
            ), f"{assertion_index}: Field {field} not updated correctly"

    def _CRUD_update(
        self,
        return_type: str = "dict",
        user_id: str = env("ROOT_ID"),
        team_id: Optional[str] = None,
    ):
        update_data = {"name": "Updated Name", "description": "Updated Description"}
        self.tracked_entities["CRUD_update_" + return_type] = (
            self.class_under_test.update(
                env("SYSTEM_ID") if self.is_system_entity else user_id,
                self.db_session,
                return_type=return_type,
                id=self.tracked_entities["CRUD_update"]["id"],
                new_properties={**update_data},
            )
        )
        return update_data

    @pytest.mark.depends(on=["test_CRUD_create"])
    @pytest.mark.parametrize("return_type", ["dict", "db", "model"])
    def test_CRUD_update(self, admin_a, team_a, return_type):
        if not hasattr(self.class_under_test, "updated_at"):
            pytest.skip("No ability to update.")
        self._CRUD_create(
            "dict",
            admin_a.id,
            team_a.id,
            "CRUD_update",
        )
        updated_fields = self._CRUD_update(return_type, admin_a.id, team_a.id)
        self._update_assert("CRUD_update_" + return_type, updated_fields)

    def _ORM_update(self, user_id: str = env("ROOT_ID"), team_id: str = None):
        entity = self.tracked_entities["ORM_update"]
        entity.name = "Updated ORM Name"
        entity.description = "Updated ORM Description"
        self.db_session.add(entity)
        self.db_session.flush()
        self.db_session.commit()
        self.tracked_entities["ORM_update"] = entity
        return {"name": "Updated ORM Name", "description": "Updated ORM Description"}

    @pytest.mark.depends(on=["test_ORM_create"])
    def test_ORM_update(self, admin_a, team_a):
        self._ORM_create(admin_a.id, team_a.id, "ORM_update")
        updated_fields = self._ORM_update(admin_a.id, team_a.id)
        self._update_assert("ORM_update", updated_fields)

    def _delete_assert(self, user_id, tracked_index: str):
        assertion_index = f"{self.class_under_test.__name__} / {tracked_index}"
        assert (
            self.tracked_entities[tracked_index] is not None
        ), f"{assertion_index}: Failed to delete entity"
        assert not self.class_under_test.exists(
            user_id, self.db_session, id=self.tracked_entities["CRUD_delete"]["id"]
        ), f"{assertion_index}: Entity still exists after deletion"
        # TODO Also confirm not gettable, listable or countable.

    def _CRUD_delete(
        self,
        user_id: str = env("ROOT_ID"),
        team_id: Optional[str] = None,
    ):
        self.class_under_test.delete(
            env("SYSTEM_ID") if self.is_system_entity else user_id,
            self.db_session,
            id=self.tracked_entities["CRUD_delete"]["id"],
        )

    @pytest.mark.depends(on=["test_CRUD_create"])
    def test_CRUD_delete(self, admin_a, team_a):
        if not hasattr(self.class_under_test, "deleted_at"):
            pytest.skip("No ability to delete.")
        self._CRUD_create(
            "dict",
            admin_a.id,
            team_a.id,
            "CRUD_delete",
        )
        self._CRUD_delete(admin_a.id, team_a.id)
        self._delete_assert(admin_a.id, "CRUD_delete")

    @pytest.mark.depends(on=["test_CRUD_delete", "test_CRUD_get"])
    def test_CRUD_soft_delete(self, admin_a, team_a):
        self._CRUD_create(
            "dict",
            admin_a.id,
            team_a.id,
            "CRUD_delete",
        )
        self._CRUD_delete(admin_a.id, team_a.id)
        self._CRUD_get("dict", env("ROOT_ID"), None, "CRUD_get_deleted", "CRUD_delete")
        self._get_assert("CRUD_get_deleted")

    def _ORM_delete(self, user_id: str = env("ROOT_ID"), team_id: str = None):
        entity = self.tracked_entities["ORM_delete"]
        self.db_session.delete(entity)
        self.db_session.flush()
        self.db_session.commit()
        self.tracked_entities["ORM_delete"] = True

    @pytest.mark.depends(on=["test_ORM_create"])
    def test_ORM_delete(self, admin_a, team_a):
        self._ORM_create(admin_a.id, team_a.id, "ORM_delete")
        self._ORM_delete(admin_a.id, team_a.id)
        self._delete_assert("ORM_delete")
