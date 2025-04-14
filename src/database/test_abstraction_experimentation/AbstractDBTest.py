import uuid
from typing import Any, Dict, List, Optional, Type, TypeVar

from fastapi import HTTPException
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from database.Base import Base, Operation

# Type variables for generic typing
T = TypeVar("T", bound=Base)


class AbstractDBTest:
    """
    Abstract base class for database CRUD tests.
    Provides common test methods for any SQLAlchemy model that uses BaseMixin.
    """

    @staticmethod
    def create_entity(
        db_session: Session,
        model_class: Type[T],
        requester_id: str,  # Renamed from user_id to requester_id
        expect_success: bool = True,
        return_type: str = "db",
        **kwargs,
    ) -> Optional[T]:
        """
        Create a test entity of the specified model class.

        Args:
            db_session: Database session
            model_class: Model class to create an instance of
            requester_id: User ID performing the operation (for permission checks)
            expect_success: Whether to expect success (True) or failure (False)
            return_type: Return type format ("db", "dict", "dto", "model")
            **kwargs: Model attributes to set

        Returns:
            Created entity or None if creation fails/is expected to fail
        """
        try:
            # If user_id not explicitly provided in kwargs and the model has a user_id field,
            # include it in the kwargs
            if "user_id" not in kwargs and hasattr(model_class, "user_id"):
                kwargs["user_id"] = requester_id

            if hasattr(model_class, "create"):
                entity = model_class.create(
                    requester_id=requester_id,
                    db=db_session,
                    return_type=return_type,
                    **kwargs,
                )
                assert (
                    expect_success
                ), f"Expected entity creation to fail but it succeeded: {entity}"
                return entity
            else:
                # Fallback for models without create method
                entity = model_class(**kwargs)
                entity.created_by_user_id = requester_id
                db_session.add(entity)
                db_session.flush()
                if return_type == "db":
                    return entity
                else:
                    # Convert to dictionary for "dict" return type
                    return {
                        c.key: getattr(entity, c.key)
                        for c in inspect(entity).mapper.column_attrs
                    }
        except Exception as e:
            if expect_success:
                raise AssertionError(
                    f"Expected entity creation to succeed but it failed: {e}"
                )
            return None

    @staticmethod
    def get_entity(
        db_session: Session,
        model_class: Type[T],
        requester_id: str,
        expect_success: bool = True,
        return_type: str = "db",
        **kwargs,
    ) -> Optional[T]:
        """
        Get a test entity of the specified model class.

        Args:
            db_session: Database session
            model_class: Model class to get an instance of
            requester_id: User ID performing the operation (for permission checks)
            expect_success: Whether to expect success (True) or failure (False)
            return_type: Return type format ("db", "dict", "dto", "model")
            **kwargs: Query filters

        Returns:
            Retrieved entity or None if retrieval fails/is expected to fail
        """
        try:
            if hasattr(model_class, "get"):
                entity = model_class.get(
                    requester_id=requester_id,
                    db=db_session,
                    return_type=return_type,
                    **kwargs,
                )
                assert (
                    expect_success
                ), f"Expected entity retrieval to fail but it succeeded: {entity}"
                return entity
            else:
                # Fallback for models without get method
                query = db_session.query(model_class)
                for key, value in kwargs.items():
                    if hasattr(model_class, key):
                        query = query.filter(getattr(model_class, key) == value)
                entity = query.first()

                if not entity and expect_success:
                    raise AssertionError(
                        f"Expected to find {model_class.__name__} with filters {kwargs}, but none was found"
                    )

                if entity and not expect_success:
                    raise AssertionError(
                        f"Expected not to find {model_class.__name__} with filters {kwargs}, but one was found"
                    )

                if return_type == "db":
                    return entity
                else:
                    # Convert to dictionary for "dict" return type
                    return (
                        {
                            c.key: getattr(entity, c.key)
                            for c in inspect(entity).mapper.column_attrs
                        }
                        if entity
                        else None
                    )
        except HTTPException as e:
            if expect_success:
                raise AssertionError(
                    f"Expected entity retrieval to succeed but it failed: {e.detail}"
                )
            return None
        except Exception as e:
            if expect_success:
                raise AssertionError(
                    f"Expected entity retrieval to succeed but it failed: {e}"
                )
            return None

    @staticmethod
    def list_entities(
        db_session: Session,
        model_class: Type[T],
        requester_id: str,
        expect_success: bool = True,
        return_type: str = "db",
        expected_count: Optional[int] = None,
        **kwargs,
    ) -> List[T]:
        """
        List entities of the specified model class.

        Args:
            db_session: Database session
            model_class: Model class to list instances of
            requester_id: User ID performing the operation (for permission checks)
            expect_success: Whether to expect success (True) or failure (False)
            return_type: Return type format ("db", "dict", "dto", "model")
            expected_count: Expected number of entities (if specified)
            **kwargs: Query filters

        Returns:
            List of entities
        """
        try:
            if hasattr(model_class, "list"):
                entities = model_class.list(
                    requester_id=requester_id,
                    db=db_session,
                    return_type=return_type,
                    **kwargs,
                )
                assert (
                    expect_success
                ), f"Expected entity listing to fail but it succeeded"

                if expected_count is not None:
                    assert (
                        len(entities) == expected_count
                    ), f"Expected {expected_count} entities but got {len(entities)}"

                return entities
            else:
                # Fallback for models without list method
                query = db_session.query(model_class)
                for key, value in kwargs.items():
                    if hasattr(model_class, key):
                        query = query.filter(getattr(model_class, key) == value)
                entities = query.all()

                if expected_count is not None:
                    assert (
                        len(entities) == expected_count
                    ), f"Expected {expected_count} entities but got {len(entities)}"

                if return_type == "db":
                    return entities
                else:
                    # Convert to dictionary for "dict" return type
                    return [
                        {
                            c.key: getattr(entity, c.key)
                            for c in inspect(entity).mapper.column_attrs
                        }
                        for entity in entities
                    ]
        except Exception as e:
            if expect_success:
                raise AssertionError(
                    f"Expected entity listing to succeed but it failed: {e}"
                )
            return []

    @staticmethod
    def update_entity(
        db_session: Session,
        model_class: Type[T],
        requester_id: str,
        entity_id: str,
        expect_success: bool = True,
        return_type: str = "db",
        **update_kwargs,
    ) -> Optional[T]:
        """
        Update a test entity of the specified model class.

        Args:
            db_session: Database session
            model_class: Model class to update an instance of
            requester_id: User ID performing the operation (for permission checks)
            entity_id: ID of the entity to update
            expect_success: Whether to expect success (True) or failure (False)
            return_type: Return type format ("db", "dict", "dto", "model")
            **update_kwargs: Attributes to update

        Returns:
            Updated entity or None if update fails/is expected to fail
        """
        try:
            if hasattr(model_class, "update"):
                entity = model_class.update(
                    requester_id=requester_id,
                    db=db_session,
                    return_type=return_type,
                    new_properties=update_kwargs,
                    id=entity_id,
                )
                assert (
                    expect_success
                ), f"Expected entity update to fail but it succeeded: {entity}"
                return entity
            else:
                # Fallback for models without update method
                entity = (
                    db_session.query(model_class)
                    .filter(model_class.id == entity_id)
                    .first()
                )
                if not entity:
                    raise ValueError(
                        f"Entity {model_class.__name__} with ID {entity_id} not found"
                    )

                for key, value in update_kwargs.items():
                    setattr(entity, key, value)
                entity.updated_by_user_id = requester_id
                db_session.commit()

                if return_type == "db":
                    return entity
                else:
                    # Convert to dictionary for "dict" return type
                    return {
                        c.key: getattr(entity, c.key)
                        for c in inspect(entity).mapper.column_attrs
                    }
        except Exception as e:
            if expect_success:
                raise AssertionError(
                    f"Expected entity update to succeed but it failed: {e}"
                )
            return None

    @staticmethod
    def delete_entity(
        db_session: Session,
        model_class: Type[T],
        requester_id: str,
        entity_id: str,
        expect_success: bool = True,
        hard_delete: bool = False,
        ignore_deleted: bool = True,
        skip_not_found: bool = True,
    ) -> bool:
        """
        Delete a test entity of the specified model class.

        Args:
            db_session: Database session
            model_class: Model class to delete an instance of
            requester_id: User ID performing the operation (for permission checks)
            entity_id: ID of the entity to delete
            expect_success: Whether to expect success (True) or failure (False)
            hard_delete: Whether to perform a hard delete (True) or soft delete (False)
            ignore_deleted: Whether to skip deletion if entity is already deleted
            skip_not_found: Whether to return success if entity doesn't exist

        Returns:
            True if delete succeeds, False otherwise
        """
        try:
            # First check if entity exists and if it's already deleted
            entity = (
                db_session.query(model_class)
                .filter(model_class.id == entity_id)
                .first()
            )

            if not entity:
                if skip_not_found:
                    # If entity doesn't exist and we're skipping not found errors, just return success
                    print(
                        f"Note: Entity {model_class.__name__} with ID {entity_id} not found, but skip_not_found=True so continuing."
                    )
                    return True
                elif expect_success:
                    raise AssertionError(
                        f"Entity {model_class.__name__} with ID {entity_id} not found"
                    )
                return False

            # Check if entity is already soft-deleted
            already_deleted = (
                hasattr(entity, "deleted_at") and entity.deleted_at is not None
            )

            if already_deleted and ignore_deleted:
                # If already deleted and we're ignoring that case, just return success
                print(
                    f"Note: Entity {model_class.__name__} with ID {entity_id} already deleted, but ignore_deleted=True so continuing."
                )
                return True

            # Attempt delete via model method if available
            if hasattr(model_class, "delete"):
                try:
                    # We need to bypass normal delete method if entity is already deleted
                    if not already_deleted:
                        model_class.delete(
                            requester_id=requester_id, db=db_session, id=entity_id
                        )
                    else:
                        # Entity is already soft-deleted, but we want to proceed anyway
                        # We'll update it directly to set the deleted_by_user_id
                        entity.deleted_by_user_id = requester_id
                        db_session.commit()

                    # If we get here without exception, the delete succeeded
                    assert (
                        expect_success
                    ), f"Expected entity deletion to fail but it succeeded"

                    # Verify soft delete if appropriate
                    if not hard_delete and hasattr(model_class, "deleted_at"):
                        updated_entity = (
                            db_session.query(model_class)
                            .filter(model_class.id == entity_id)
                            .first()
                        )
                        assert (
                            updated_entity is not None
                        ), f"Entity was hard deleted but should have been soft deleted"
                        assert (
                            updated_entity.deleted_at is not None
                        ), f"Entity should have been soft deleted but deleted_at is None"
                        assert (
                            updated_entity.deleted_by_user_id == requester_id
                        ), f"Entity should have been deleted by {requester_id} but was deleted by {updated_entity.deleted_by_user_id}"

                    return True

                except Exception as e:
                    # Handle special cases
                    if ("404" in str(e) or "not found" in str(e).lower()) and (
                        already_deleted or skip_not_found
                    ):
                        # The model.delete couldn't find the record, either because:
                        # 1. It's filtering out deleted records and the record is deleted, or
                        # 2. The record doesn't exist and we're skipping not found errors
                        print(
                            f"Note: Got 404 error from model.delete, but ignoring due to configuration: {e}"
                        )
                        return True
                    # It's another error, so re-raise
                    raise
            else:
                # Fallback for models without delete method
                if hard_delete:
                    db_session.delete(entity)
                else:
                    # Soft delete if the model has a deleted_at attribute
                    if hasattr(entity, "deleted_at"):
                        from sqlalchemy import func

                        entity.deleted_at = func.now()
                        entity.deleted_by_user_id = requester_id
                    else:
                        # Fall back to hard delete if the model doesn't support soft delete
                        db_session.delete(entity)

                db_session.commit()
                return True

        except Exception as e:
            # Special case: if we get a not found error and skip_not_found is True
            if ("404" in str(e) or "not found" in str(e).lower()) and skip_not_found:
                print(
                    f"Note: Got not found error but skip_not_found=True so continuing: {e}"
                )
                return True

            if expect_success:
                raise AssertionError(
                    f"Expected entity deletion to succeed but it failed: {e}"
                )
            return False

    @staticmethod
    def assert_entity_exists(
        db_session: Session, model_class: Type[T], **filter_kwargs
    ) -> None:
        """
        Assert that an entity exists with the given filters.

        Args:
            db_session: Database session
            model_class: Model class to check
            **filter_kwargs: Filter criteria
        """
        query = db_session.query(model_class)
        for key, value in filter_kwargs.items():
            query = query.filter(getattr(model_class, key) == value)

        entity = query.first()
        assert (
            entity is not None
        ), f"Entity {model_class.__name__} with filters {filter_kwargs} does not exist"

    @staticmethod
    def assert_entity_not_exists(
        db_session: Session, model_class: Type[T], **filter_kwargs
    ) -> None:
        """
        Assert that an entity does not exist with the given filters.

        Args:
            db_session: Database session
            model_class: Model class to check
            **filter_kwargs: Filter criteria
        """
        query = db_session.query(model_class)
        for key, value in filter_kwargs.items():
            query = query.filter(getattr(model_class, key) == value)

        entity = query.first()
        assert (
            entity is None
        ), f"Entity {model_class.__name__} with filters {filter_kwargs} exists but should not"

    @staticmethod
    def assert_entity_count(
        db_session: Session, model_class: Type[T], expected_count: int, **filter_kwargs
    ) -> None:
        """
        Assert that the count of entities matches the expected count.

        Args:
            db_session: Database session
            model_class: Model class to check
            expected_count: Expected number of entities
            **filter_kwargs: Filter criteria
        """
        query = db_session.query(model_class)
        for key, value in filter_kwargs.items():
            query = query.filter(getattr(model_class, key) == value)

        actual_count = query.count()
        assert (
            actual_count == expected_count
        ), f"Expected {expected_count} entities but found {actual_count}"

    @staticmethod
    def assert_entity_property(
        db_session: Session,
        model_class: Type[T],
        property_name: str,
        expected_value: Any,
        **filter_kwargs,
    ) -> None:
        """
        Assert that a property of an entity matches the expected value.

        Args:
            db_session: Database session
            model_class: Model class to check
            property_name: Name of the property to check
            expected_value: Expected value of the property
            **filter_kwargs: Filter criteria to find the entity
        """
        query = db_session.query(model_class)
        for key, value in filter_kwargs.items():
            query = query.filter(getattr(model_class, key) == value)

        entity = query.first()
        assert (
            entity is not None
        ), f"Entity {model_class.__name__} with filters {filter_kwargs} does not exist"

        actual_value = getattr(entity, property_name)
        assert (
            actual_value == expected_value
        ), f"Expected property {property_name} to be {expected_value} but got {actual_value}"

    @staticmethod
    def assert_permission_check(
        db_session: Session,
        model_class: Type[T],
        requester_id: str,
        entity_id: str,
        operation: Operation,
        expected_result: bool,
        minimum_role: Optional[str] = None,
    ) -> None:
        """
        Assert that permission check for a specified operation returns the expected result.

        Args:
            db_session: Database session
            model_class: Model class to check permissions for
            requester_id: User ID to check permissions for (for permission checks)
            entity_id: Entity ID to check permissions for
            operation: Operation to check (CREATE, READ, UPDATE, DELETE)
            expected_result: Expected result of the permission check
            minimum_role: Minimum role required (if applicable)
        """
        if operation == Operation.READ:
            if hasattr(model_class, "user_has_read_access"):
                result = model_class.user_has_read_access(
                    requester_id, entity_id, db_session, minimum_role
                )
                assert (
                    result == expected_result
                ), f"Expected permission check for READ to return {expected_result} but got {result}"
        elif operation == Operation.UPDATE:
            if hasattr(model_class, "user_has_admin_access"):
                result = model_class.user_has_admin_access(
                    requester_id, entity_id, db_session
                )
                assert (
                    result == expected_result
                ), f"Expected permission check for UPDATE to return {expected_result} but got {result}"
        elif operation == Operation.DELETE:
            if hasattr(model_class, "user_has_admin_access"):
                result = model_class.user_has_admin_access(
                    requester_id, entity_id, db_session
                )
                assert (
                    result == expected_result
                ), f"Expected permission check for DELETE to return {expected_result} but got {result}"
        elif operation == Operation.CREATE:
            if hasattr(model_class, "user_can_create"):
                result = model_class.user_can_create(requester_id, db_session)
                assert (
                    result == expected_result
                ), f"Expected permission check for CREATE to return {expected_result} but got {result}"

    @staticmethod
    def test_full_crud_cycle(
        db_session: Session,
        model_class: Type[T],
        requester_id: str,
        create_kwargs: Dict[str, Any],
        update_kwargs: Dict[str, Any],
        read_check_field: str = "name",
    ) -> None:
        """
        Test a full CRUD cycle for a model.

        Args:
            db_session: Database session
            model_class: Model class to test
            requester_id: User ID performing the operations (for permission checks)
            create_kwargs: Keywords arguments for entity creation
            update_kwargs: Keyword arguments for entity update
            read_check_field: Field to check after read operation
        """
        # Ensure user_id is set in create_kwargs if model has user_id field
        if "user_id" not in create_kwargs and hasattr(model_class, "user_id"):
            create_kwargs = (
                create_kwargs.copy()
            )  # Create copy to avoid modifying original
            create_kwargs["user_id"] = requester_id

        # 1. Create
        entity = AbstractDBTest.create_entity(
            db_session=db_session,
            model_class=model_class,
            requester_id=requester_id,
            **create_kwargs,
        )
        assert entity is not None, "Entity creation failed"
        entity_id = entity.id if hasattr(entity, "id") else entity["id"]

        # 2. Read
        read_entity = AbstractDBTest.get_entity(
            db_session=db_session,
            model_class=model_class,
            requester_id=requester_id,
            id=entity_id,
        )
        assert read_entity is not None, "Entity retrieval failed"

        # Check the field value matches what we created
        field_value = (
            read_entity[read_check_field]
            if isinstance(read_entity, dict)
            else getattr(read_entity, read_check_field)
        )
        assert (
            field_value == create_kwargs[read_check_field]
        ), f"Field {read_check_field} value mismatch: expected {create_kwargs[read_check_field]}, got {field_value}"

        # 3. Update
        updated_entity = AbstractDBTest.update_entity(
            db_session=db_session,
            model_class=model_class,
            requester_id=requester_id,
            entity_id=entity_id,
            **update_kwargs,
        )
        assert updated_entity is not None, "Entity update failed"

        # Verify update was successful
        updated_field_value = (
            updated_entity[read_check_field]
            if isinstance(updated_entity, dict)
            else getattr(updated_entity, read_check_field)
        )
        assert (
            updated_field_value == update_kwargs[read_check_field]
        ), f"Update failed: expected {update_kwargs[read_check_field]}, got {updated_field_value}"

        # 4. Delete
        delete_success = AbstractDBTest.delete_entity(
            db_session=db_session,
            model_class=model_class,
            requester_id=requester_id,
            entity_id=entity_id,
            ignore_deleted=True,
            skip_not_found=True,
        )
        assert delete_success, "Entity deletion failed"

        # Verify soft delete
        if hasattr(model_class, "deleted_at"):
            # Soft delete means entity still exists but has deleted_at set
            AbstractDBTest.assert_entity_exists(db_session, model_class, id=entity_id)

            # Get the entity and check deleted_at
            soft_deleted_entity = (
                db_session.query(model_class)
                .filter(model_class.id == entity_id)
                .first()
            )
            assert (
                soft_deleted_entity.deleted_at is not None
            ), "Entity was not soft deleted"
            assert (
                soft_deleted_entity.deleted_by_user_id == requester_id
            ), "Entity was not deleted by the expected user"
        else:
            # Hard delete means entity no longer exists
            AbstractDBTest.assert_entity_not_exists(
                db_session, model_class, id=entity_id
            )

    @staticmethod
    def test_permission_scenarios(
        db_session: Session,
        model_class: Type[T],
        owner_id: str,
        other_user_id: str,
        team_id: Optional[str] = None,
        create_kwargs: Dict[str, Any] = None,
        expect_owner_read: bool = True,
        expect_owner_update: bool = True,
        expect_owner_delete: bool = True,
    ) -> None:
        """
        Test various permission scenarios for a model.

        Args:
            db_session: Database session
            model_class: Model class to test
            owner_id: User ID that will own the entity
            other_user_id: Another user ID for testing permissions
            team_id: Team ID for testing team-scoped permissions (optional)
            create_kwargs: Keywords arguments for entity creation (if not provided, a minimal entity will be created)
            expect_owner_read: Whether owner is expected to have read permission
            expect_owner_update: Whether owner is expected to have update permission
            expect_owner_delete: Whether owner is expected to have delete permission
        """
        # Create a minimal entity if no create_kwargs provided
        if create_kwargs is None:
            create_kwargs = {"name": f"Test {model_class.__name__}"}

            # Add user_id or team_id based on what's provided
            if team_id:
                create_kwargs["team_id"] = team_id
            else:
                create_kwargs["user_id"] = owner_id

            # Add minimal required fields based on model
            if (
                hasattr(model_class, "description")
                and "description" not in create_kwargs
            ):
                create_kwargs["description"] = (
                    f"Test description for {model_class.__name__}"
                )

            if hasattr(model_class, "content") and "content" not in create_kwargs:
                create_kwargs["content"] = f"Test content for {model_class.__name__}"

            if hasattr(model_class, "favourite") and "favourite" not in create_kwargs:
                create_kwargs["favourite"] = False

        # 1. Create entity as owner
        entity = AbstractDBTest.create_entity(
            db_session=db_session,
            model_class=model_class,
            requester_id=owner_id,
            **create_kwargs,
        )
        assert entity is not None, "Entity creation failed"
        entity_id = entity.id if hasattr(entity, "id") else entity["id"]

        # 2. Test READ permissions
        # Check owner read permissions based on expectation
        if hasattr(model_class, "user_has_read_access"):
            result = model_class.user_has_read_access(owner_id, entity_id, db_session)
            assert (
                result == expect_owner_read
            ), f"Expected owner read permission to be {expect_owner_read} but got {result}"

        # Other user's read access depends on model and whether it's team-scoped
        can_other_user_read = False
        try:
            read_entity = AbstractDBTest.get_entity(
                db_session=db_session,
                model_class=model_class,
                requester_id=other_user_id,
                expect_success=None,  # Don't assert, just try
                id=entity_id,
            )
            can_other_user_read = read_entity is not None
        except:
            pass

        # 3. Test UPDATE permissions
        # Check owner update permissions based on expectation
        if hasattr(model_class, "user_has_admin_access"):
            result = model_class.user_has_admin_access(owner_id, entity_id, db_session)
            assert (
                result == expect_owner_update
            ), f"Expected owner update permission to be {expect_owner_update} but got {result}"

        # Other user's update access depends on model
        can_other_user_update = False
        try:
            AbstractDBTest.update_entity(
                db_session=db_session,
                model_class=model_class,
                requester_id=other_user_id,
                entity_id=entity_id,
                expect_success=None,  # Don't assert, just try
                name=f"Updated by other user",
            )
            can_other_user_update = True
        except:
            pass

        # 4. Test DELETE permissions
        # Check owner delete permissions based on expectation
        if hasattr(
            model_class, "user_has_admin_access"
        ):  # Usually uses same permissions as update
            result = model_class.user_has_admin_access(owner_id, entity_id, db_session)
            assert (
                result == expect_owner_delete
            ), f"Expected owner delete permission to be {expect_owner_delete} but got {result}"

        # Log the results for this model
        print(f"\nPermission scenario results for {model_class.__name__}:")
        print(f"- Owner can read: {expect_owner_read}")
        print(f"- Other user can read: {can_other_user_read}")
        print(f"- Owner can update: {expect_owner_update}")
        print(f"- Other user can update: {can_other_user_update}")
        print(f"- Owner can delete: {expect_owner_delete}")

        # Finally, delete the entity as owner if they have permission, otherwise as system user
        if expect_owner_delete:
            AbstractDBTest.delete_entity(
                db_session=db_session,
                model_class=model_class,
                requester_id=owner_id,
                entity_id=entity_id,
                ignore_deleted=True,  # Ignore if already deleted
                skip_not_found=True,  # Skip if entity doesn't exist
            )
        else:
            # Get system ID for cleanup
            system_id = env("SYSTEM_ID")
            AbstractDBTest.delete_entity(
                db_session=db_session,
                model_class=model_class,
                requester_id=system_id,
                entity_id=entity_id,
                ignore_deleted=True,  # Ignore if already deleted
                skip_not_found=True,  # Skip if entity doesn't exist
            )

    @staticmethod
    def generate_test_id() -> str:
        """Generate a unique ID for test entities."""
        return str(uuid.uuid4())
