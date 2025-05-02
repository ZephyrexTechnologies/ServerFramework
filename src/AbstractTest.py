import logging
import random
import string
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

import pytest
from faker import Faker
from pydantic import BaseModel, Field

from database import Base
from lib.Environment import env
from lib.Pydantic import obj_to_dict

# Set up logging
logger = logging.getLogger(__name__)


class ParentEntity(BaseModel):
    """Model for parent entity configuration"""

    name: str
    foreign_key: str
    path_level: Optional[int] = None  # 1 for first level nesting, 2 for second level
    test_class: Any


class TestCategory(str, Enum):
    """Categories of tests for organization and selective execution."""

    UNIT = "unit"
    DATABASE = "database"
    LOGIC = "business_logic"
    ENDPOINT = "endpoint"
    REST = "rest"
    GRAPHQL = "graphql"
    PERFORMANCE = "performance"
    INTEGRATION = "integration"
    SMOKE = "smoke"
    REGRESSION = "regression"
    SECURITY = "security"
    SEED = "seed_data"
    EXTENSION = "extension"
    SDK = "sdk"
    MIGRATION = "migration"


class SkipReason(str, Enum):
    IRRELEVANT = "irrelevant"
    NOT_IMPLEMENTED = "not_implemented"


class TestToSkip(BaseModel):
    """Model for a skipped test with a reason."""

    name: str = Field(..., description="Name of the test method to skip")
    reason: SkipReason = Field(
        SkipReason.IRRELEVANT, description="Reason for skipping the test"
    )
    details: str = Field(None, description="Additional details about the test to skip")
    gh_issue_number: Optional[int] = Field(
        None, description="Optional GitHub ticket reference number"
    )


class TestClassConfig(BaseModel):
    """Configuration for test execution and behavior."""

    categories: List[TestCategory] = Field(
        default=[TestCategory.UNIT], description="Categories this test belongs to"
    )
    timeout: Optional[int] = Field(
        None, description="Optional timeout in seconds for tests in this class"
    )
    parallel: bool = Field(
        False, description="Whether tests in this class can be run in parallel"
    )
    cleanup: bool = Field(
        True, description="Whether to clean up resources after each test"
    )
    gh_action_skip: bool = Field(
        False,
        description="Whether to skip these tests in GitHub action CI/CD environments",
    )


class AbstractTest:
    """
    Base class for all abstract test suites in the application.

    Provides common utilities for test organization, categorization,
    skipping logic, and other shared test functionality.

    Features:
    - Test categorization
    - Test skipping with reasons
    - Test configuration
    - Common assertion utilities
    - Required fixture documentation

    To use this class, extend it and override the class attributes as needed.

    Available centralized fixtures (defined in conftest.py):
    - db: Session-wide database fixture
    - db_session: Database session for testing
    - standard_user_ids: Dictionary of standard user IDs
    - standard_team_ids: Dictionary of standard team IDs
    - standard_role_ids: Dictionary of standard role IDs
    - standard_users: Dictionary of standard user objects
    - standard_teams: Dictionary of standard team objects
    - requester_id, test_user_id, test_team_id: Commonly used test IDs
    - seed_database: Fixture to seed database with common test data
    - server: TestClient instance for endpoint testing
    - bll_test_data_generator, bll_test_validator: Helpers for BLL tests
    - create_test_entity: Helper for creating test entities
    """

    class_under_test: Type = None
    debug: bool = False
    # Tests to skip - List of SkippedTest objects, should be overridden by subclasses
    skip_tests: List[TestToSkip] = []

    # Test configuration - should be overridden by subclasses if needed
    test_config: TestClassConfig = TestClassConfig()

    # Create a faker instance for generating test data
    faker = Faker()
    create_fields: Dict[str, Any] = None
    update_fields: Dict[str, Any] = None
    unique_fields: List[str] = ["name"]
    parent_entities: List[ParentEntity] = []  # List of ParentEntity objects
    # A dict of entities to clean up
    tracked_entities: Dict[str, Any] = {}
    abstract_creation_method: Callable

    def build_entities(
        self,
        user_id: str = "",
        team_id: str = "",
        count=1,
        unique_fields: List[str] = None,
    ):
        entities = []
        unique_fields = unique_fields or []

        for i in range(count):
            entity_data = self.create_fields.copy()
            for field in self.create_fields:
                if callable(self.create_fields[field]):
                    entity_data[field] = self.create_fields[field]()
            # Handle multiple unique fields
            for field in unique_fields:
                if field in self.create_fields:
                    base_value = entity_data[field]
                    if field == "email":
                        random_part = "".join(
                            random.choices(string.ascii_lowercase + string.digits, k=8)
                        )
                        timestamp = datetime.now().strftime("%H%M%S%f")
                        entity_data[field] = (
                            f"test_{random_part}_{timestamp}@example.com"
                        )
                    elif field == "username":
                        random_part = "".join(
                            random.choices(string.ascii_lowercase + string.digits, k=8)
                        )
                        entity_data[field] = f"{base_value}_{random_part}_{i}"
                    else:
                        # Generic uniqueness for other fields
                        entity_data[field] = f"{base_value}-{i}"

            if user_id and "user_id" in entity_data:
                entity_data["user_id"] = user_id
            if team_id and "team_id" in entity_data:
                entity_data["team_id"] = team_id
            for parent in self.parent_entities:
                parent_entity_test_class = parent.test_class()
                parent_entity_test_class.db_session = self.db_session
                new_parent_entity = parent_entity_test_class.abstract_creation_method(
                    user_id=user_id, team_id=team_id
                )
                entity_data[parent.foreign_key] = new_parent_entity["id"]
            entities.append(entity_data)
        return entities

    @property
    def db_class(self) -> Base:
        if TestCategory.DATABASE in self.test_config.categories:
            return self.class_under_test
        elif TestCategory.LOGIC in self.test_config.categories:
            return self.class_under_test.DBClass
        elif TestCategory.ENDPOINT in self.test_config.categories:
            return self.class_under_test.manager_class.DBClass
        else:
            return None

    @property
    def is_system_entity(self) -> bool:
        """
        Check if the test entity is a system entity.
        """
        if (
            TestCategory.DATABASE in self.test_config.categories
            or TestCategory.LOGIC in self.test_config.categories
            or TestCategory.ENDPOINT in self.test_config.categories
        ):
            return self.db_class.system
        else:
            return False

    def reason_to_skip(self, test_name: str) -> Optional[SkipReason]:
        """
        Check if a specific test method should be skipped based on the skip_tests list of the enclosing class.

        Args:
            test_name: The name of the test method.

        Returns:
            True if the test should be skipped, False otherwise. If True, pytest.skip()
            will be called with the reason.
        """
        if skip := next(
            (skip for skip in self.skip_tests if skip.name == test_name), None
        ):
            reason = skip.details + (
                (f" (GitHub: {env('APP_REPOSITORY')}/issues/{skip.gh_issue_number})")
                if skip.gh_issue_number
                else ""
            )
            (
                pytest.skip(reason)
                if skip.reason == SkipReason.IRRELEVANT
                else pytest.xfail(reason)
            )

    @classmethod
    def setup_class(cls):
        """
        Set up resources for the entire test class.

        This method is called once before any tests in the class are run.
        Override in subclasses to set up shared resources.
        """
        logger.info(f"Setting up test class: {cls.__name__}")

        # Apply timeout if configured
        if cls.test_config.timeout:
            pytest.mark.timeout(cls.test_config.timeout)

        # Skip in CI if configured
        if cls.test_config.gh_action_skip:
            pytest.mark.skipif(
                "env('ENVIRONMENT') == 'ci'",
                reason="Test configured to skip in CI environment",
            )

    @classmethod
    def teardown_class(cls):
        """
        Clean up resources for the entire test class.

        This method is called once after all tests in the class have run.
        Override in subclasses to clean up shared resources.
        """
        logger.info(f"Tearing down test class: {cls.__name__}")

    def setup_method(self, method):
        """
        Set up resources for each test method.

        This method is called before each test method in the class.
        Override in subclasses to set up test-specific resources.

        Args:
            method: The test method that will be executed
        """
        logger.info(f"Setting up method: {method.__name__}")

        # Check if test should be skipped
        self.reason_to_skip(method.__name__)

    def teardown_method(self, method):
        """
        Clean up resources for each test method.

        This method is called after each test method in the class.
        Override in subclasses to clean up test-specific resources.

        Args:
            method: The test method that was executed
        """
        if self.test_config.cleanup:
            logger.info(f"Tearing down method: {method.__name__}")

    # Common assertion methods
    def assert_objects_equal(
        self, actual: Any, expected: Any, fields_to_check: List[str] = None
    ):
        """
        Assert that two objects have equal values for specified fields.

        Args:
            actual: The actual object or dictionary
            expected: The expected object or dictionary
            fields_to_check: Optional list of fields to check, if None checks all fields in expected
        """

        # Convert objects to dictionaries if they're not already
        if not isinstance(actual, dict):
            actual = obj_to_dict(actual)

        if not isinstance(expected, dict):
            expected = obj_to_dict(expected)

        # Determine which fields to check
        if fields_to_check is None:
            fields_to_check = expected.keys()

        # Check each field
        for field in fields_to_check:
            if field in expected:
                assert field in actual, f"Field '{field}' missing from actual object"
                assert actual[field] == expected[field], (
                    f"Field '{field}' value mismatch: "
                    f"expected {expected[field]}, got {actual[field]}"
                )

    def assert_has_audit_fields(self, obj: Any, updated: bool = False):
        """
        Assert that an object has the required audit fields.

        Args:
            obj: The object or dictionary to check
            updated: Whether to check update audit fields too
        """

        # Convert object to dictionary if it's not already
        obj = obj_to_dict(obj)

        # Check created fields
        assert (
            "created_at" in obj and obj["created_at"] is not None
        ), "created_at missing or None"
        assert (
            "created_by_user_id" in obj and obj["created_by_user_id"] is not None
        ), "created_by_user_id missing or None"

        # Check updated fields if requested
        if updated:
            assert (
                "updated_at" in obj and obj["updated_at"] is not None
            ), "updated_at missing or None"
            assert (
                "updated_by_user_id" in obj and obj["updated_by_user_id"] is not None
            ), "updated_by_user_id missing or None"

    @staticmethod
    def verify_permissions(
        manager, operation: str, entity_id: str, should_succeed: bool, **kwargs
    ):
        """
        Verify that a permission check works as expected.

        Args:
            manager: The BLL manager instance
            operation: The operation to test ('get', 'update', 'delete')
            entity_id: The entity ID to operate on
            should_succeed: Whether the operation should succeed
            **kwargs: Additional arguments for the operation
        """
        try:
            if operation == "get":
                result = manager.get(id=entity_id)
            elif operation == "update":
                result = manager.update(id=entity_id, **kwargs)
            elif operation == "delete":
                manager.delete(id=entity_id)
                result = None
            else:
                raise ValueError(f"Unknown operation: {operation}")

            # If we expected failure but got success
            if not should_succeed:
                raise AssertionError(
                    f"Operation '{operation}' succeeded but should have failed"
                )
            return result

        except Exception as e:
            # If we expected success but got failure
            if should_succeed:
                raise AssertionError(
                    f"Operation '{operation}' failed but should have succeeded: {e}"
                )
            # Expected failure - all good
            return None

    # @classmethod
    # def create_test_entities(
    #     cls,
    #     manager,
    #     count: int,
    #     data_generator,
    #     field_overrides: Optional[Dict[str, Any]] = None,
    # ) -> List[Any]:
    #     """Create multiple test entities using a manager."""
    #     entities = []
    #     for i in range(count):
    #         if field_overrides and callable(field_overrides):
    #             overrides = field_overrides(i)
    #         elif field_overrides:
    #             overrides = field_overrides.copy()
    #             # If there's a field that should be unique per entity
    #             if "name" in overrides:
    #                 overrides["name"] = f"{overrides['name']} {i}"
    #         else:
    #             overrides = {
    #                 "name": f"{cls.faker.word().capitalize()} {cls.faker.random_int(min=1000, max=9999)}"
    #             }

    #         entity_data = data_generator.generate_for_model(
    #             manager.Model.Create, overrides=overrides
    #         )
    #         entity = manager.create(**entity_data)
    #         entities.append(entity)

    #     return entities

    @staticmethod
    def validate_required_fields(
        entity: Dict[str, Any], required_fields: List[str]
    ) -> List[str]:
        """
        Validate that all required fields are present in an entity.

        Args:
            entity: The entity to validate
            required_fields: List of required field names

        Returns:
            List of missing field names (empty if all present)
        """
        missing_fields = []
        for field in required_fields:
            if field not in entity or entity[field] is None:
                missing_fields.append(field)
        return missing_fields

    @staticmethod
    def validate_entity_matches(
        entity: Dict[str, Any],
        expected_data: Dict[str, Any],
        fields_to_check: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Validate that entity fields match expected values.

        Args:
            entity: The entity to validate
            expected_data: Dictionary of expected field values
            fields_to_check: Optional list of specific fields to check (if None, checks all fields in expected_data)

        Returns:
            List of mismatched field names (empty if all match)
        """
        mismatched_fields = []

        # Determine which fields to check
        fields = fields_to_check if fields_to_check else expected_data.keys()

        for field in fields:
            if field in expected_data:
                if field not in entity:
                    mismatched_fields.append(field)
                elif entity[field] != expected_data[field]:
                    mismatched_fields.append(field)

        return mismatched_fields

    @staticmethod
    def validate_audit_fields(
        entity: Dict[str, Any],
        created_by: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> List[str]:
        """
        Validate audit fields in an entity.

        Args:
            entity: The entity to validate
            created_by: Expected user ID for created_by_user_id field
            updated_by: Expected user ID for updated_by_user_id field

        Returns:
            List of invalid audit field names (empty if all valid)
        """
        invalid_fields = []

        # Check created_at and created_by_user_id
        if "created_at" not in entity or not entity["created_at"]:
            invalid_fields.append("created_at")

        if created_by and (
            "created_by_user_id" not in entity
            or entity["created_by_user_id"] != created_by
        ):
            invalid_fields.append("created_by_user_id")

        # Check updated_at and updated_by_user_id if provided
        if updated_by:
            if "updated_at" not in entity or not entity["updated_at"]:
                invalid_fields.append("updated_at")

            if (
                "updated_by_user_id" not in entity
                or entity["updated_by_user_id"] != updated_by
            ):
                invalid_fields.append("updated_by_user_id")

        return invalid_fields
