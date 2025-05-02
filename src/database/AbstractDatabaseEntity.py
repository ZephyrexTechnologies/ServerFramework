import functools
import logging
import uuid
from typing import List, Literal, Optional, Type, TypeVar, Union, get_args, get_origin

from fastapi import HTTPException
from sqlalchemy import UUID, Column, DateTime, ForeignKey, String, func, inspect
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Session, declared_attr, relationship
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from database.Base import DATABASE_TYPE, PK_TYPE, get_session
from database.StaticPermissions import (
    PermissionType,
    check_permission,
    gen_not_found_msg,
    generate_permission_filter,
    validate_columns,
)
from lib.Environment import env
from lib.Pydantic import obj_to_dict


def with_session(func):
    """
    Decorator to handle session creation, commit, rollback, and closing.
    """

    @functools.wraps(func)
    def wrapper(
        cls, requester_id: String, db: Optional[Session] = None, *args, **kwargs
    ):
        session = db if db else get_session()
        logging.debug(f"Executing {func.__name__} on {cls.__name__}: {str(kwargs)}")
        try:
            result = func(cls, requester_id, session, *args, **kwargs)
            return result
        except Exception as e:
            logging.error(e)
            logging.debug(f"Rolling back {func.__name__}...")
            session.rollback()
            raise e
        finally:
            if db is None:
                logging.debug("Closing session...")
                session.close()

    return wrapper


def get_dto_class(cls, override_dto=None):
    """
    Determine which DTO class to use based on provided override or class default.
    """
    if override_dto:
        return override_dto
    elif hasattr(cls, "dto") and cls.dto is not None:
        return cls.dto
    return None


T = TypeVar("T")
DtoT = TypeVar("DtoT")
ModelT = TypeVar("ModelT")


def validate_fields(cls, fields):
    """
    Validate that the fields exist on the model class.

    Args:
        cls: The model class
        fields: List of field names to validate

    Raises:
        HTTPException: If any field is invalid
    """
    if not fields:
        return

    # Get all column names from the model
    mapper = inspect(cls)
    valid_columns = set(column.key for column in mapper.columns)

    # Check for invalid fields
    invalid_fields = [field for field in fields if field not in valid_columns]
    if invalid_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid field(s) requested: {', '.join(invalid_fields)}",
        )


def build_query(
    session,
    cls,
    joins=[],
    options=[],
    filters=[],
    order_by=None,
    limit=None,
    offset=None,
    **kwargs,
):
    to_return = session.query(cls)

    if len(joins) > 0:
        for join in joins:
            to_return = to_return.join(join)
    if len(filters) > 0:
        for filter_condition in filters:
            to_return = to_return.filter(filter_condition)
    to_return = to_return.filter_by(**kwargs)
    if len(options) > 0:
        for option in options:
            to_return = to_return.options(option)
    if order_by:
        to_return = to_return.order_by(*order_by)
    if limit:
        to_return = to_return.limit(limit)
    if offset:
        to_return = to_return.offset(offset)
    return to_return


def db_to_return_type(
    entity: Union[T, List[T]],
    return_type: Literal["db", "dict", "dto", "model"] = "dict",
    dto_type: Optional[Type[DtoT]] = None,
    fields: List[str] = [],
) -> Union[T, DtoT, ModelT, List[Union[T, DtoT, ModelT]]]:
    """
    Convert database entity to specified return type, handling nested objects and relationships.
    When return_type is "dict" and fields is provided, only the specified fields will be included.

    Args:
        entity: The database entity or list of entities to convert
        return_type: The desired return type format
        dto_type: The DTO type class to convert to
        fields: List of fields to include in the response (only for return_type="dict")

    Returns:
        The converted entity in the requested format
    """
    if entity is None:
        return None

    if return_type == "db":
        return entity

    elif return_type == "dict":
        # Convert to dictionary
        if isinstance(entity, list):
            if not entity:
                return []

            dict_entities = [obj_to_dict(item) for item in entity]
            # Filter fields if specified
            if fields:
                for entity_dict in dict_entities:
                    # Keep only requested fields
                    keys_to_remove = [
                        key for key in list(entity_dict.keys()) if key not in fields
                    ]
                    for key in keys_to_remove:
                        del entity_dict[key]

            return dict_entities
        else:
            # First convert the entire entity to dict to avoid expired attribute issues
            entity_dict = obj_to_dict(entity)
            # Filter fields if specified
            if fields:
                # Keep only requested fields
                keys_to_remove = [
                    key for key in list(entity_dict.keys()) if key not in fields
                ]
                for key in keys_to_remove:
                    del entity_dict[key]

            return entity_dict

    elif return_type in ["dto", "model"] and dto_type:
        if fields:
            # Fields parameter is only valid for dict return type
            raise HTTPException(
                status_code=400,
                detail="Fields parameter can only be used with return_type='dict'",
            )

        # Convert to DTO or Model
        if isinstance(entity, list):
            dto_instances = []
            for item in entity:
                # Convert each entity to dict first
                item_dict = obj_to_dict(item)
                # Process nested objects in the dict
                item_dict = _process_nested_objects(item_dict, dto_type)
                # Create DTO instance
                dto_instance = dto_type(**item_dict)
                dto_instances.append(dto_instance)

            # Convert to model if requested
            if return_type == "model":
                return [dto.to_model() for dto in dto_instances]
            return dto_instances
        else:
            # Convert entity to dict
            entity_dict = obj_to_dict(entity)
            # Process nested objects in the dict
            entity_dict = _process_nested_objects(entity_dict, dto_type)
            # Create DTO instance
            dto_instance = dto_type(**entity_dict)

            # Convert to model if requested
            if return_type == "model":
                return dto_instance.to_model()
            return dto_instance

    # Default return the original entity
    return entity


def _process_nested_objects(data_dict, parent_dto_type):
    """
    Process nested objects in a dictionary based on parent DTO type annotations.
    Handles recursive conversion of nested objects and lists.
    """
    result = {}

    # Get type hints from the DTO class
    type_hints = getattr(parent_dto_type, "__annotations__", {})

    for key, value in data_dict.items():
        if key not in type_hints:
            # Keep original value if no type hint
            result[key] = value
            continue

        expected_type = type_hints[key]
        result[key] = _convert_based_on_type_hint(value, expected_type)

    return result


def _convert_based_on_type_hint(value, type_hint):
    """
    Convert a value based on its type hint.
    Handles primitive types, lists, optionals, nested objects, and enums.
    """
    # Handle None values
    if value is None:
        return None

    # Get the origin type (for generics like List, Optional)
    origin = get_origin(type_hint)

    # Handle Optional types (Union with NoneType)
    if origin is Union:
        args = get_args(type_hint)
        if type(None) in args:
            # Find the non-None type
            for arg in args:
                if arg is not type(None):
                    return _convert_based_on_type_hint(value, arg)
            return value

    # Handle List types
    if origin is list:
        if not isinstance(value, list):
            return []

        # Get the list item type
        item_type = get_args(type_hint)[0]
        return [_convert_based_on_type_hint(item, item_type) for item in value]

    # Handle Dict types
    if origin is dict:
        if not isinstance(value, dict):
            return {}
        return value

    # Handle Enum types specifically
    if hasattr(type_hint, "__mro__") and "Enum" in [
        c.__name__ for c in type_hint.__mro__
    ]:
        # For enum types, handle differently
        if isinstance(value, type_hint):
            return value

        # If the value is already a valid enum value (like an int or string)
        try:
            # Try direct conversion first
            return type_hint(value)
        except (ValueError, TypeError):
            pass

        # Try to find by name if it's a string
        if isinstance(value, str):
            try:
                return getattr(type_hint, value)
            except (AttributeError, TypeError):
                pass

        # Return as-is if conversion fails
        return value

    # Handle primitive types
    if type_hint in (str, int, float, bool):
        return value

    # Handle model types (custom classes)
    if isinstance(value, dict):
        # Already a dict, convert directly to the target type
        return type_hint(**value)

    if hasattr(value, "__dict__"):
        # Convert to dict first
        value_dict = obj_to_dict(value)

        # For model types with nested fields, process recursively
        if hasattr(type_hint, "__annotations__"):
            value_dict = _process_nested_objects(value_dict, type_hint)

        # Create an instance of the target type
        return type_hint(**value_dict)

    # Default case: return value as is
    return value


class HookDict(dict):
    """Dictionary subclass that allows attribute access to dictionary items"""

    def __getattr__(self, name):
        if name in self:
            value = self[name]
            if isinstance(value, dict):
                return HookDict(value)
            return value
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def __setattr__(self, name, value):
        self[name] = value


# Global hooks registry to properly handle inheritance
_hooks_registry = {}
hook_types = ["create", "update", "delete", "get", "list"]


def get_hooks_for_class(cls):
    """Get or create hooks for a class"""
    if cls not in _hooks_registry:
        # Create a new hooks dictionary for this class with all required hook types
        _hooks_registry[cls] = HookDict(
            {
                hook_type: HookDict({"before": [], "after": []})
                for hook_type in hook_types
            }
        )

    # Ensure all required hook types exist
    hooks = _hooks_registry[cls]

    for hook_type in hook_types:
        if hook_type not in hooks:
            hooks[hook_type] = HookDict({"before": [], "after": []})

    return _hooks_registry[cls]


# Descriptor for class-level hooks
class HooksDescriptor:
    def __get__(self, obj, objtype=None):
        if objtype is None:
            objtype = type(obj)
        return get_hooks_for_class(objtype)


# TODO Add a generator that will create `cls.RefMixin` and `cls.RefMixin.Optional`.
class BaseMixin:
    system = False
    seed_list = []

    @classmethod
    def register_seed_items(cls, items):
        cls.seed_list.extend(items)

    # Class-level hooks property
    hooks = HooksDescriptor()

    @classmethod
    def create_foreign_key(cls, target_entity, **kwargs):
        """
        Create a foreign key column referencing the target entity,
        using the class names for a descriptive constraint name.
        """
        # Default nullable to True if not specified
        if "nullable" not in kwargs:
            kwargs["nullable"] = True

        # Use the mixin's class name and the target entity's name
        constraint_name = kwargs.pop(
            "constraint_name",
            f"fk_{cls.__name__.lower()}_{target_entity.__tablename__}_id",
        )
        ondelete = kwargs.pop("ondelete", None)
        fk = ForeignKey(
            f"{target_entity.__tablename__}.id", ondelete=ondelete, name=constraint_name
        )

        # Adjust column type based on your primary key type
        if PK_TYPE == UUID:
            return Column(UUID(as_uuid=True), fk, **kwargs)
        else:
            return Column(String, fk, **kwargs)

    @declared_attr
    def id(cls):
        return Column(
            PK_TYPE,
            primary_key=True,
            default=lambda: (
                str(uuid.uuid4()) if DATABASE_TYPE == "sqlite" else uuid.uuid4()
            ),
        )

    @declared_attr
    def created_at(cls):
        return Column(DateTime, default=func.now())

    @declared_attr
    def created_by_user_id(cls):
        return Column(PK_TYPE, nullable=True)

    @classmethod
    def user_has_read_access(cls, user_id, id, db, minimum_role=None, referred=False):
        """
        Checks if a user has read access to a specific record.

        Args:
            user_id (str): The ID of the user requesting access
            id (str): The ID of the record to check
            db (Session): Database session
            minimum_role (str, optional): Minimum role required. Defaults to None.
            referred (bool, optional): Whether this check is for a referenced entity.

        Returns:
            bool: True if access is granted, False otherwise
        """
        from database.StaticPermissions import (
            PermissionResult,
            PermissionType,
            check_permission,
            is_root_id,
            is_system_id,
        )

        # Get the record
        record = db.query(cls).filter(cls.id == id).first()
        if not record:
            return False

        # Check for deleted records - only ROOT_ID can see them
        if hasattr(record, "deleted_at") and record.deleted_at is not None:
            return is_root_id(user_id)

        # Check system flag - only ROOT_ID and SYSTEM_ID can access system-flagged tables
        if hasattr(cls, "system") and getattr(cls, "system", False):
            if not is_system_id(user_id):
                return False

        # Check for records created by ROOT_ID - only ROOT_ID can access them
        if hasattr(record, "created_by_user_id") and record.created_by_user_id == env(
            "ROOT_ID"
        ):
            return user_id == env("ROOT_ID")

        # For non-referred checks, use the unified permission system
        if not referred:
            result, _ = check_permission(
                user_id,
                cls,
                id,
                db,
                PermissionType.VIEW if minimum_role is None else None,
                minimum_role=minimum_role,
            )
            return result == PermissionResult.GRANTED

        return False

    @classmethod
    def user_has_admin_access(cls, user_id, id, db):
        """
        Check admin access using the optimized DB-level check (user_can_edit).
        (Consider removing this if not directly used elsewhere)

        Args:
            user_id: The ID of the user to check
            id: The ID of the record to check
            db: Database session

        Returns:
            bool: True if user has admin access, False otherwise
        """
        has_access = check_permission(user_id, cls, id, db, "admin")
        return has_access[0].value == "granted"

    @classmethod
    def user_has_all_access(cls, user_id, id, db):
        """
        Check highest level access using the optimized DB-level check (user_can_share).
        (Consider removing this if not directly used elsewhere)

        Args:
            user_id: The ID of the user to check
            id: The ID of the record to check
            db: Database session

        Returns:
            bool: True if user has all access, False otherwise
        """
        from database.StaticPermissions import (
            PermissionResult,
            PermissionType,
            check_permission,
        )

        result, _ = check_permission(user_id, cls, id, db, PermissionType.SHARE)
        return result == PermissionResult.GRANTED

    @classmethod
    def user_can_create(cls, user_id, db, team_id=None, minimum_role="user", **kwargs):
        """
        Checks if a user can create an entity of this class.

        Args:
            user_id: ID of the user
            db: Database session
            team_id: Team ID if relevant
            minimum_role: Minimum role required
            **kwargs: Additional parameters

        Returns:
            bool: True if the user can create, False otherwise
        """
        from database.StaticPermissions import (
            check_access_to_all_referenced_entities,
            is_root_id,
            is_system_user_id,
            user_can_create_referenced_entity,
        )

        # Root user can create anything
        if is_root_id(user_id):
            return True

        # Check system flag - only ROOT_ID and SYSTEM_ID can create in system-flagged tables
        if hasattr(cls, "system") and getattr(cls, "system", False):
            return is_root_id(user_id) or is_system_user_id(user_id)

        # Check if user has access to all referenced entities
        can_access, missing_entity = check_access_to_all_referenced_entities(
            user_id, cls, db, minimum_role, **kwargs
        )
        if not can_access:
            return False

        # Check create permissions based on create_permission_reference
        can_create, _ = user_can_create_referenced_entity(
            cls, user_id, db, minimum_role, **kwargs
        )
        return can_create

    @classmethod
    @with_session
    def create(
        cls: Type[T],
        requester_id: str,
        db: Optional[Session],
        return_type: Literal["db", "dict", "dto", "model"] = "dict",
        fields=[],
        override_dto: Optional[Type[DtoT]] = None,
        **kwargs,
    ) -> T:
        """Create a new database entity."""
        from database.StaticPermissions import (
            PermissionResult,
            PermissionType,
            is_root_id,
            is_system_user_id,
        )

        # Validate fields parameter
        validate_fields(cls, fields)

        # Check system flag - only ROOT_ID and SYSTEM_ID can create in system-flagged tables
        if hasattr(cls, "system") and getattr(cls, "system", False):
            if not (is_root_id(requester_id) or is_system_user_id(requester_id)):
                raise HTTPException(
                    status_code=403,
                    detail=f"Only system users can create {cls.__name__} records",
                )

        # Check if the user can create this entity
        # Remove user_id from kwargs if it exists to prevent duplicate parameters
        create_kwargs = kwargs.copy()
        if "user_id" in create_kwargs:
            create_kwargs.pop("user_id")

        if not cls.user_can_create(requester_id, db, **create_kwargs):
            raise HTTPException(
                status_code=403, detail=f"Not authorized to create {cls.__name__}"
            )

        # Generate a UUID if not provided
        data = dict(kwargs)
        if "id" not in data:
            data["id"] = str(uuid.uuid4())

        # Add created_by_user_id if the entity has this column
        if hasattr(cls, "created_by_user_id"):
            data["created_by_user_id"] = requester_id

        # Get hooks for before_create
        hooks = cls.hooks
        if "create" in hooks and "before" in hooks["create"]:
            before_hooks = hooks["create"]["before"]
            if before_hooks:
                hook_dict = HookDict(data)
                for hook in before_hooks:
                    hook(hook_dict, db)
                # Extract data from the hook dict
                data = {k: v for k, v in hook_dict.items()}

        # Create the entity
        entity = cls(**data)
        db.add(entity)
        db.flush()
        if cls.__tablename__ == "users":
            entity.created_by_user_id = entity.id
        db.commit()
        db.refresh(entity)

        # Get hooks for after_create
        if "create" in hooks and "after" in hooks["create"]:
            after_hooks = hooks["create"]["after"]
            if after_hooks:
                for hook in after_hooks:
                    hook(entity, db)

        # Convert to requested return type
        return db_to_return_type(entity, return_type, override_dto, fields)

    @classmethod
    @with_session
    def count(
        cls: Type[T],
        requester_id: str,
        db: Optional[Session],
        joins=[],
        options=[],
        filters=[],
        check_permissions=True,
        minimum_role=None,
        **kwargs,
    ) -> int:
        """
        Count records with permission filtering.

        Args:
            requester_id: The ID of the user making the request
            db: Database session
            joins: List of join conditions
            options: List of query options
            filters: List of filter conditions
            check_permissions: Whether to apply permission filtering
            minimum_role: Minimum role required for access
            **kwargs: Additional filter criteria

        Returns:
            int: Number of matching records
        """
        validate_columns(cls, **kwargs)

        # Add permission filtering
        if check_permissions:
            # Import here to avoid circular imports
            from database.StaticPermissions import (
                PermissionType,
                generate_permission_filter,
                is_root_id,
            )

            perm_filter = generate_permission_filter(
                requester_id, cls, db, PermissionType.VIEW, minimum_role
            )
            if filters:
                filters.append(perm_filter)
            else:
                filters = [perm_filter]

            # Only add deleted_at filter for non-ROOT users
            if hasattr(cls, "deleted_at") and not is_root_id(requester_id):
                filters.append(cls.deleted_at == None)

        # Build query with all filters
        query = build_query(db, cls, joins, options, filters, **kwargs)

        # Get count
        return query.count()

    @classmethod
    @with_session
    def exists(
        cls: Type[T],
        requester_id: str,
        db,
        joins=[],
        options=[],
        filters=[],
        **kwargs,
    ) -> bool:
        """Check if at least one record matching the criteria exists and is accessible."""
        from database.StaticPermissions import PermissionType, is_root_id

        # Validate kwargs
        validate_columns(cls, **kwargs)

        # Apply proper permission filtering
        if "id" in kwargs:
            # Specific ID lookup - use direct permission check
            record_id = kwargs["id"]

            # Get the record to check if it exists
            record = db.query(cls).filter(cls.id == record_id).first()
            if record is None:
                return False

            # For User model, handle special cases
            if cls.__tablename__ == "users":
                # Check if the user is looking up their own record
                if (
                    hasattr(record, "deleted_at")
                    and record.deleted_at is not None
                    and not is_root_id(requester_id)
                ):
                    return False

                if requester_id == record_id:
                    return True

                # Check if record was created by ROOT_ID - only ROOT_ID can access
                if (
                    hasattr(record, "created_by_user_id")
                    and record.created_by_user_id == env("ROOT_ID")
                    and not is_root_id(requester_id)
                ):
                    return False

                # Check if deleted - only ROOT_ID can see

            # Otherwise, use permission system with a special direct check for User model
            if cls.__tablename__ == "users":
                # Use the model's user_has_read_access method if available
                return cls.user_has_read_access(requester_id, record_id, db)
            else:
                # Add permission filter
                perm_filter = generate_permission_filter(
                    requester_id, cls, db, PermissionType.VIEW
                )
                if filters:
                    filters.append(perm_filter)
                else:
                    filters = [perm_filter]

                # Add deleted_at filter for non-ROOT users
                if hasattr(cls, "deleted_at") and not is_root_id(requester_id):
                    filters.append(cls.deleted_at == None)

                # Build a query with the filters
                query = build_query(
                    db, cls, joins=joins, options=options, filters=filters, **kwargs
                )

                # Check if any results exist with permission filtering
                return query.first() is not None
        else:
            # Collection lookup - use standard permission filter
            # Add permission filter
            perm_filter = generate_permission_filter(
                requester_id, cls, db, PermissionType.VIEW
            )
            if filters:
                filters.append(perm_filter)
            else:
                filters = [perm_filter]

            # Add deleted_at filter for non-ROOT users
            if hasattr(cls, "deleted_at") and not is_root_id(requester_id):
                filters.append(cls.deleted_at == None)

            # Build a query with the filters
            query = build_query(
                db, cls, joins=joins, options=options, filters=filters, **kwargs
            )

            # Check if any results exist with permission filtering
            return query.first() is not None

    @classmethod
    @with_session
    def get(
        cls: Type[T],
        requester_id: str,
        db: Optional[Session],
        return_type: Literal["db", "dict", "dto", "model"] = "dict",
        joins=[],
        options=[],
        filters=[],
        fields=[],
        override_dto: Optional[Type[DtoT]] = None,
        **kwargs,
    ) -> T:
        validate_columns(cls, **kwargs)

        # Validate fields parameter
        if fields and return_type != "dict":
            raise HTTPException(
                status_code=400,
                detail="Fields parameter can only be used with return_type='dict'",
            )

        # Validate that fields exist on the model
        validate_fields(cls, fields)

        # Only add deleted_at filter for non-ROOT users
        from database.StaticPermissions import is_root_id

        if hasattr(cls, "deleted_at") and not is_root_id(requester_id):
            filters = filters + [cls.deleted_at == None]

        # Apply permission filter
        perm_filter = generate_permission_filter(
            requester_id, cls, db, PermissionType.VIEW
        )  # Default VIEW for get
        if filters:
            filters.append(perm_filter)
        else:
            filters = [perm_filter]

        # Build query with permission filter included
        query = build_query(db, cls, joins, options, filters, **kwargs)

        # Get the single result
        try:
            result = query.one()
            to_return = db_to_return_type(
                result,
                return_type,
                get_dto_class(cls, override_dto),
                fields=fields,
            )

            if to_return is None:
                logging.warning(
                    f"None is about to be returned from {cls.__name__} get(): return type {return_type}/{override_dto}, {joins}, {options}, {filters}, {kwargs}"
                )
            else:
                logging.debug(
                    f"Returning from {cls.__name__} get: {to_return} ({return_type})"
                )
            return to_return
        except NoResultFound:
            # Special case for entity_id="self" and providing self_entity
            if kwargs.get("entity_id") == "self" and "self_entity" in kwargs:
                return db_to_return_type(
                    kwargs["self_entity"],
                    return_type,
                    get_dto_class(cls, override_dto),
                    fields=fields,
                )
            # When using id as a named parameter, return None for not found
            if "id" in kwargs:
                return None
            # Otherwise raise 404
            raise HTTPException(status_code=404, detail=gen_not_found_msg(cls.__name__))
        except MultipleResultsFound:
            raise HTTPException(
                status_code=409,
                detail=f"Request uncovered multiple {cls.__name__} when only one was expected.",
            )

    @classmethod
    @with_session
    def list(
        cls: Type[T],
        requester_id: str,
        db: Optional[Session],
        return_type: Literal["db", "dict", "dto", "model"] = "dict",
        joins=[],
        options=[],
        filters=[],
        order_by=None,
        limit=None,
        offset=None,
        fields=[],
        override_dto: Optional[Type[DtoT]] = None,
        check_permissions=True,
        minimum_role=None,
        **kwargs,
    ) -> List[T]:
        """
        List records with permission filtering.

        Args:
            requester_id: The ID of the user making the request
            db: Database session
            return_type: The return type format ("db", "dict", "dto", "model")
            joins: List of join conditions
            options: List of query options
            filters: List of filter conditions
            order_by: Order by criteria
            limit: Maximum number of records to return
            offset: Number of records to skip
            fields: List of fields to include in the response (only for return_type="dict")
            override_dto: Optional DTO class override
            check_permissions: Whether to apply permission filtering (defaults to True)
            minimum_role: Minimum role required for team access (defaults to None)
            **kwargs: Additional filter criteria

        Returns:
            List of records in the specified return format
        """
        validate_columns(cls, **kwargs)

        # Validate fields parameter
        if fields and return_type != "dict":
            raise HTTPException(
                status_code=400,
                detail="Fields parameter can only be used with return_type='dict'",
            )

        # Validate that fields exist on the model
        validate_fields(cls, fields)

        # Only add deleted_at filter for non-ROOT users
        from database.StaticPermissions import is_root_id

        if hasattr(cls, "deleted_at") and not is_root_id(requester_id):
            if filters:
                filters.append(cls.deleted_at == None)
            else:
                filters = [cls.deleted_at == None]

        # Apply permission filter
        perm_filter = generate_permission_filter(
            requester_id, cls, db, PermissionType.VIEW
        )  # Default VIEW for list
        if filters:
            filters.append(perm_filter)
        else:
            filters = [perm_filter]

        query = build_query(
            db, cls, joins, options, filters, order_by, limit, offset, **kwargs
        )

        # Fetch records based on filtered query
        to_return = query.all()

        logging.debug(f"To return: {', '.join([str(item) for item in to_return])}")
        if to_return is None:
            logging.warning(
                f"None is about to be returned from {cls.__name__} list(): return type {return_type}/{override_dto}, {joins}, {options}, {filters}, {kwargs}"
            )
        else:
            logging.debug(
                f"Returning from {cls.__name__} list: {to_return} ({return_type})"
            )

        return db_to_return_type(
            to_return,
            return_type,
            get_dto_class(cls, override_dto),
            fields=fields,
        )


class UpdateMixin:
    """Adds update and delete hooks to the hooks registry"""

    # Initialize hooks for update and delete
    @classmethod
    def _initialize_update_hooks(cls):
        """Initialize update and delete hooks for this class if not already present"""
        hooks = get_hooks_for_class(cls)

        # Only add the keys if they don't exist yet
        if "update" not in hooks:
            hooks["update"] = HookDict({"before": [], "after": []})
        if "delete" not in hooks:
            hooks["delete"] = HookDict({"before": [], "after": []})

        return hooks

    @declared_attr
    def updated_at(cls):
        return Column(DateTime, default=func.now(), onupdate=func.now())

    @declared_attr
    def updated_by_user_id(cls):
        return Column(PK_TYPE, nullable=True)

    @classmethod
    @with_session
    def update(
        cls: Type[T],
        requester_id: str,
        db: Optional[Session],
        new_properties,
        return_type: Literal["db", "dict", "dto", "model"] = "dict",
        filters=[],
        fields=[],
        override_dto: Optional[Type[DtoT]] = None,
        check_permissions=True,
        **kwargs,
    ) -> T:
        """Update a database entity with new properties."""
        from database.StaticPermissions import (
            PermissionResult,
            PermissionType,
            is_root_id,
            is_system_id,
            is_system_user_id,
        )

        # Validate fields parameter
        validate_fields(cls, fields)

        # Build the query to find the entity
        additional_filters = []
        if check_permissions:
            # Generate permission filter for EDIT access
            from database.StaticPermissions import generate_permission_filter

            permission_filter = generate_permission_filter(
                requester_id, cls, db, PermissionType.EDIT
            )
            additional_filters.append(permission_filter)

        query = build_query(
            db,
            cls,
            filters=filters + additional_filters,
            **kwargs,
        )

        try:
            entity = query.one()
        except NoResultFound:
            raise HTTPException(status_code=404, detail=f"{cls.__name__} not found")
        except MultipleResultsFound:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: Multiple {cls.__name__} matched query criteria",
            )

        # Check for system flag - only ROOT_ID and SYSTEM_ID can modify system-flagged tables
        if hasattr(cls, "system") and getattr(cls, "system", False):
            if not (is_root_id(requester_id) or is_system_user_id(requester_id)):
                raise HTTPException(
                    status_code=403,
                    detail=f"Only system users can modify {cls.__name__} records",
                )

        # Check if the record was created by ROOT_ID or SYSTEM_ID
        if hasattr(entity, "created_by_user_id"):
            if entity.created_by_user_id == env("ROOT_ID") and not is_root_id(
                requester_id
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Only ROOT can modify records created by ROOT",
                )

            if entity.created_by_user_id == env("SYSTEM_ID") and not (
                is_root_id(requester_id) or is_system_user_id(requester_id)
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Only system users can modify records created by SYSTEM",
                )

        # Copy updated properties to avoid modifying the input
        updated = dict(new_properties)

        # Generate field map if needed
        if fields:
            dto_class = cls.get_dto_class(override_dto)
            field_map = {}
            for field in fields:
                field_map = _process_dto_field(field_map, field, dto_class)

        # Ensure created_by_user_id and id cannot be modified
        if "created_by_user_id" in updated:
            del updated["created_by_user_id"]
        if "id" in updated:
            del updated["id"]

        # Set updated_by_user_id and updated_at
        if hasattr(cls, "updated_by_user_id"):
            updated["updated_by_user_id"] = requester_id
        if hasattr(cls, "updated_at"):
            updated["updated_at"] = func.now()

        # Get hooks for before_update
        hooks = cls.hooks
        if "update" in hooks and "before" in hooks["update"]:
            before_hooks = hooks["update"]["before"]
            if before_hooks:
                hook_dict = HookDict(updated)
                for hook in before_hooks:
                    hook(hook_dict, db)
                # Extract updates from the hook dict
                updated = {k: v for k, v in hook_dict.items()}

        # Apply updates
        for key, value in updated.items():
            setattr(entity, key, value)

        # Commit changes
        db.commit()
        db.refresh(entity)

        # Get hooks for after_update
        hooks = cls.hooks["update"]["after"]
        if hooks:
            for hook in hooks:
                hook(entity, updated, db)

        # Convert to requested return type
        return db_to_return_type(entity, return_type, override_dto, fields)

    @declared_attr
    def deleted_at(cls):
        return Column(DateTime, default=None)

    @declared_attr
    def deleted_by_user_id(cls):
        return Column(PK_TYPE, nullable=True)

    @classmethod
    @with_session
    def delete(
        cls: Type[T],
        requester_id: str,
        db: Optional[Session],
        filters=[],
        check_permissions=True,
        **kwargs,
    ):
        """
        Soft delete a database entity by setting deleted_at and deleted_by_user_id.
        Enforces permission checks and system flag restrictions.
        """
        from database.StaticPermissions import (
            PermissionResult,
            PermissionType,
            is_root_id,
            is_system_id,
            is_system_user_id,
        )

        # Build the query with permission checks
        additional_filters = []
        if check_permissions:
            # Generate permission filter for DELETE access
            from database.StaticPermissions import generate_permission_filter

            permission_filter = generate_permission_filter(
                requester_id, cls, db, PermissionType.DELETE
            )
            additional_filters.append(permission_filter)

        query = build_query(
            db,
            cls,
            filters=filters + additional_filters,
            **kwargs,
        )

        try:
            entity = query.one()
        except NoResultFound:
            raise HTTPException(status_code=404, detail=f"{cls.__name__} not found")
        except MultipleResultsFound:
            raise HTTPException(
                status_code=500, detail=f"Multiple {cls.__name__} found"
            )

        # Check for system flag - only ROOT_ID and SYSTEM_ID can delete from system-flagged tables
        if hasattr(cls, "system") and getattr(cls, "system", False):
            if not (is_root_id(requester_id) or is_system_user_id(requester_id)):
                raise HTTPException(
                    status_code=403,
                    detail=f"Only system users can delete {cls.__name__} records",
                )

        # Check if the record was created by ROOT_ID or SYSTEM_ID
        if hasattr(entity, "created_by_user_id"):
            if entity.created_by_user_id == env("ROOT_ID") and not is_root_id(
                requester_id
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Only ROOT can delete records created by ROOT",
                )

            if entity.created_by_user_id == env("SYSTEM_ID") and not (
                is_root_id(requester_id) or is_system_user_id(requester_id)
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Only system users can delete records created by SYSTEM",
                )
        if hasattr(entity, "created_by_user_id"):
            if (
                entity.created_by_user_id is not None
                and entity.created_by_user_id != requester_id
                and not (is_root_id(requester_id) or is_system_user_id(requester_id))
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Only the creator can delete this record",
                )
        # Get hooks for before_delete
        hooks = cls.hooks
        if "delete" in hooks and "before" in hooks["delete"]:
            before_hooks = hooks["delete"]["before"]
            if before_hooks:
                for hook in before_hooks:
                    hook(entity, db)

        # Set deleted fields
        if hasattr(cls, "deleted_at"):
            setattr(entity, "deleted_at", func.now())
        if hasattr(cls, "deleted_by_user_id"):
            setattr(entity, "deleted_by_user_id", requester_id)

        # Commit changes
        db.commit()

        # Get hooks for after_delete
        hooks = cls.hooks["delete"]["after"]
        if hooks:
            for hook in hooks:
                hook(entity, db)


class ParentMixin:
    @declared_attr
    def parent_id(cls):
        return Column(
            PK_TYPE,
            ForeignKey(f"{cls.__tablename__}.id"),
            nullable=True,
            index=True,
        )

    @declared_attr
    def parent(cls):
        return relationship(
            cls,
            remote_side=[cls.id],
            backref="children",
            primaryjoin=lambda: cls.id == cls.parent_id,
        )


class ImageMixin:
    @declared_attr
    def image_url(cls):
        return Column(String, nullable=True)


def create_reference_mixin(target_entity, **kwargs):
    """
    Create a reference mixin class for a target entity.

    This function dynamically generates a reference mixin class for an entity,
    which provides a standard way to create foreign key relationships and
    associated SQLAlchemy relationships. Each generated mixin includes both
    a required version (non-nullable foreign key) and an Optional inner class
    (nullable foreign key).

    Args:
        target_entity: The target entity class to reference
        **kwargs: Additional parameters:
            - comment: Optional comment for the foreign key
            - backref_name: Custom backref name (defaults to tablename)
            - nullable: Whether the non-Optional version should be nullable (defaults to False)

    Returns:
        type: A reference mixin class with an Optional inner class

    Example:
        ```python
        # Create a reference mixin for the User entity
        UserRefMixin = create_reference_mixin(User)

        # Use the mixin in a new entity class (required user relationship)
        class Document(Base, BaseMixin, UserRefMixin):
            __tablename__ = "documents"
            title = Column(String, nullable=False)
            content = Column(String)

        # Use the Optional version for nullable relationships
        class Comment(Base, BaseMixin, UserRefMixin.Optional):
            __tablename__ = "comments"
            text = Column(String, nullable=False)

        # Create a customized reference mixin
        CustomUserRefMixin = create_reference_mixin(
            User,
            comment="Reference to the document owner",
            backref_name="owned_documents",
            nullable=True  # Even the non-Optional version will be nullable
        )
        ```
    """
    entity_name = target_entity.__name__
    lower_name = entity_name.lower()
    comment = kwargs.get("comment", None)
    backref_name = kwargs.get("backref_name", None)
    nullable = kwargs.get("nullable", False)

    # Define the main mixin class
    class RefMixin:
        """Reference mixin for providing a relationship to another entity."""

        pass

    # Create and set the ID attribute
    @declared_attr
    def id_attr(cls):
        fk_kwargs = {}
        if comment:
            fk_kwargs["comment"] = comment
        return cls.create_foreign_key(target_entity, nullable=nullable, **fk_kwargs)

    # Set the foreign key attribute
    setattr(RefMixin, f"{lower_name}_id", id_attr)

    # Create and set the relationship attribute
    @declared_attr
    def rel_attr(cls):
        # Use provided backref_name or generate one based on the class's tablename
        # This will be evaluated at class definition time
        if backref_name is not None:
            backref_val = backref_name
        else:
            # Get the tablename from the class that's using this mixin
            backref_val = cls.__tablename__ if hasattr(cls, "__tablename__") else None

        return relationship(
            target_entity.__name__,
            backref=backref_val,
        )

    # Set the relationship attribute
    setattr(RefMixin, lower_name, rel_attr)

    # Set proper class name and module
    RefMixin.__name__ = f"{entity_name}RefMixin"
    RefMixin.__module__ = "database.AbstractDatabaseEntity"

    # Define the optional variant
    class OptionalRefMixin:
        """Optional reference mixin where the foreign key is nullable."""

        pass

    # Create and set the nullable ID attribute
    @declared_attr
    def opt_id_attr(cls):
        fk_kwargs = {}
        if comment:
            fk_kwargs["comment"] = comment
        return cls.create_foreign_key(
            target_entity, **fk_kwargs
        )  # nullable=True by default

    # Set the foreign key attribute for the optional variant
    setattr(OptionalRefMixin, f"{lower_name}_id", opt_id_attr)

    # Create the relationship for the optional variant
    @declared_attr
    def opt_rel_attr(cls):
        # Use provided backref_name or generate one based on the class's tablename
        if backref_name is not None:
            backref_val = backref_name
        else:
            # Get the tablename from the class that's using this mixin
            backref_val = cls.__tablename__ if hasattr(cls, "__tablename__") else None

        return relationship(
            target_entity.__name__,
            backref=backref_val,
        )

    # Set the relationship attribute for the optional variant
    setattr(OptionalRefMixin, lower_name, opt_rel_attr)

    # Set proper class name and module
    OptionalRefMixin.__name__ = f"_{entity_name}Optional"
    OptionalRefMixin.__module__ = "database.AbstractDatabaseEntity"

    # Attach the optional variant to the main mixin
    RefMixin.Optional = OptionalRefMixin

    return RefMixin


# TODO Why is this function here?
def get_reference_mixin(entity_name, **kwargs):
    """
    Dynamically import an entity and create a reference mixin.

    This function allows you to create reference mixins without
    having to import the target entity directly, which can help
    avoid circular import issues.

    Args:
        entity_name: The name of the entity class (e.g., "User", "Team")
        **kwargs: Additional parameters for create_reference_mixin:
            - comment: Optional comment for the foreign key
            - backref_name: Custom backref name (defaults to tablename)
            - nullable: Whether the non-Optional version should be nullable (defaults to False)

    Returns:
        type: A reference mixin class with an Optional inner class

    Raises:
        ValueError: If entity_name is not in the known entities mapping
        ImportError: If the module or entity cannot be imported

    Example:
        ```python
        # Get a reference mixin for User without importing it directly
        UserRefMixin = get_reference_mixin("User")

        # Use the mixin in a new entity class
        class Document(Base, BaseMixin, UserRefMixin):
            __tablename__ = "documents"
            title = Column(String, nullable=False)
            content = Column(String)

        # Get a customized reference mixin
        TeamRefMixin = get_reference_mixin(
            "Team",
            backref_name="team_documents",
            nullable=True
        )
        ```
    """
    # Map entity names to their module paths
    entity_modules = {
        "User": "database.DB_Auth",
        "Team": "database.DB_Auth",
        "Role": "database.DB_Auth",
        "Provider": "database.DB_Providers",
        # Add other entities as needed
    }

    if entity_name not in entity_modules:
        raise ValueError(f"Unknown entity: {entity_name}")

    # Import the entity dynamically
    import importlib

    module = importlib.import_module(entity_modules[entity_name])
    entity = getattr(module, entity_name)

    # Create and return the reference mixin
    return create_reference_mixin(entity, **kwargs)
