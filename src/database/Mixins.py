import functools
import logging
import uuid
from typing import List, Literal, Optional, Type, TypeVar, Union, get_args, get_origin

from fastapi import HTTPException
from sqlalchemy import UUID, Column, DateTime, ForeignKey, String, func, inspect
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Session, declared_attr, relationship

from database.Base import DATABASE_TYPE, PK_TYPE, Operation, get_session
from database.Permissions import (
    check_access_to_all_referenced_entities,
    gen_not_found_msg,
    is_root_id,
    is_system_id,
    is_template_id,
    user_can_create_referenced_entity,
    validate_columns,
)


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
    if return_type == "db":
        return entity

    elif return_type == "dict":
        # Convert to dictionary
        if isinstance(entity, list):
            dict_entities = [_entity_to_dict(item) for item in entity]
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
            entity_dict = _entity_to_dict(entity)
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
                item_dict = _entity_to_dict(item)
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
            entity_dict = _entity_to_dict(entity)
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


def _entity_to_dict(entity):
    """Convert an entity to a dictionary, handling both DB entities and regular objects."""
    if hasattr(entity, "__dict__"):
        # For SQLAlchemy entities, skip internal attributes
        return {
            key: value
            for key, value in entity.__dict__.items()
            if not key.startswith("_")
        }
    # For other objects, return as is
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
        value_dict = _entity_to_dict(value)

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
        Backward compatibility method for checking read access.
        Delegates to user_can_view internally.

        Args:
            user_id: The ID of the user requesting access
            id: The ID of the record to check
            db: Database session
            minimum_role: Minimum role name required for team access
            referred: Whether this is a recursive call from a referring entity

        Returns:
            bool: True if user has access, False otherwise
        """
        from database.Permissions import user_can_view

        # For compatibility with minimum_role parameter:
        # - If minimum_role is "admin" or higher, use user_can_edit
        # - If minimum_role is "superadmin", use user_can_share
        if minimum_role == "superadmin":
            from database.Permissions import user_can_share

            return user_can_share(user_id, cls, id, db)
        elif minimum_role == "admin":
            from database.Permissions import user_can_edit

            return user_can_edit(user_id, cls, id, db)
        else:
            return user_can_view(user_id, cls, id, db)

    @classmethod
    def user_has_admin_access(cls, user_id, id, db):
        """
        Backward compatibility method for checking admin access.
        Delegates to user_can_edit internally.

        Args:
            user_id: The ID of the user to check
            id: The ID of the record to check
            db: Database session

        Returns:
            bool: True if user has admin access, False otherwise
        """
        from database.Permissions import user_can_edit

        return user_can_edit(user_id, cls, id, db)

    @classmethod
    def user_has_all_access(cls, user_id, id, db):
        """
        Backward compatibility method for checking highest level access.
        Delegates to user_can_share internally.

        Args:
            user_id: The ID of the user to check
            id: The ID of the record to check
            db: Database session

        Returns:
            bool: True if user has all access, False otherwise
        """
        from database.Permissions import user_can_share

        return user_can_share(user_id, cls, id, db)

    @classmethod
    def user_can_create(cls, user_id, db, team_id=None, minimum_role="user", **kwargs):
        """
        Check if user has permission to create a new record.
        Checks both create_permission_reference and permission_references.

        Args:
            user_id: The ID of the user requesting to create
            db: Database session
            team_id: The team ID for which the record is being created (if applicable)
            minimum_role: Minimum role required to create records in the specified team
            **kwargs: Additional parameters that may contain referenced entity IDs

        Returns:
            bool: True if user has permission to create, False otherwise
        """
        # Special handling for system users
        if is_root_id(user_id):
            return True  # ROOT_ID can create anything

        # Special check for SYSTEM_ID and TEMPLATE_ID - they can only create within their domains
        if is_system_id(user_id) or is_template_id(user_id):
            # These users can only create if the user_id field (if exists) matches their ID
            if (
                hasattr(cls, "user_id")
                and kwargs.get("user_id")
                and kwargs["user_id"] != user_id
            ):
                return False

        # Check create_permission_reference first
        if (
            hasattr(cls, "create_permission_reference")
            and cls.create_permission_reference
        ):
            can_create, error_msg = user_can_create_referenced_entity(
                cls, user_id, db, minimum_role, **kwargs
            )
            if not can_create:
                logging.warning(
                    f"User {user_id} denied create permission via create_permission_reference: {error_msg}"
                )
                return False

        # Check access to all referenced entities
        has_access, missing_entity = check_access_to_all_referenced_entities(
            user_id, cls, db, minimum_role, **kwargs
        )
        if not has_access:
            if missing_entity[3] == "not_found":
                error = gen_not_found_msg(missing_entity[0])
                logging.warning(
                    f"User {user_id} attempted to reference non-existent {missing_entity[0]}: {missing_entity[2]}"
                )
                raise HTTPException(status_code=404, detail=error)
            else:
                error = f"User {user_id} does not have permission to create a {cls.__name__} record referencing {missing_entity[0]} {missing_entity[2]}"
                logging.warning(error)
                raise HTTPException(status_code=403, detail=error)

        # User can always create their own records if they have a user_id field
        if hasattr(cls, "user_id") and not team_id:
            return True

        # For team-scoped records, check team membership with sufficient role
        if team_id and hasattr(cls, "team_id"):
            from database.Permissions import is_user_on_team_recursive

            return is_user_on_team_recursive(user_id, team_id, db, minimum_role)

        # If we get here, there was no user_id, team_id, or permission references
        # This is typically a user-scoped record without explicit ownership
        return True

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
        # Validate fields parameter
        if fields and return_type != "dict":
            raise HTTPException(
                status_code=400,
                detail="Fields parameter can only be used with return_type='dict'",
            )

        # Validate that fields exist on the model
        validate_fields(cls, fields)

        team_id = kwargs.get("team_id")

        if not cls.user_can_create(
            requester_id,
            db,
            team_id=team_id,
            **{k: v for k, v in kwargs.items() if k not in ["user_id", "team_id"]},
        ):
            raise HTTPException(
                status_code=403,
                detail=f"User {requester_id} does not have permission to create record in table {cls.__tablename__}{' for team ' + team_id if team_id else ''}.",
            )

        if hasattr(cls, "has_permission") and not cls.has_permission(
            cls, Operation.CREATE.value, requester_id
        ):
            raise HTTPException(
                status_code=403,
                detail=f"User {requester_id} does not have permission to create record in table {cls.__tablename__}.",
            )

        validate_columns(cls, **kwargs)

        # Call before hooks
        hooks = cls.hooks
        for hook in hooks["create"]["before"]:
            hook(cls, requester_id, db, return_type, override_dto, **kwargs)

        created = cls()
        for key, value in kwargs.items():
            setattr(created, key, value)
        created.created_by_user_id = requester_id
        db.add(created)
        db.commit()
        db.refresh(created)

        # Call after hooks
        for hook in hooks["create"]["after"]:
            hook(created, requester_id, db, return_type, override_dto, **kwargs)

        if created is None:
            logging.warning(
                f"None is about to be returned from {cls.__name__} create(): return type {return_type}/{override_dto}, {kwargs}"
            )
        else:
            logging.debug(
                f"Returning from {cls.__name__} create: {created} ({return_type})"
            )
        return db_to_return_type(
            created,
            return_type,
            get_dto_class(cls, override_dto),
            fields=fields,
        )

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
            check_permissions: Whether to apply permission filtering (defaults to True)
            minimum_role: Minimum role required for team access (defaults to None)
            **kwargs: Additional filter criteria

        Returns:
            int: Count of records matching criteria and permission filters
        """
        validate_columns(cls, **kwargs)

        # Add deleted_at filter if column exists
        if hasattr(cls, "deleted_at"):
            filters = filters + [cls.deleted_at == None]

        # Build base query and fetch all matching results
        query = build_query(db, cls, joins, options, filters, **kwargs)

        # If permissions check is disabled or no requester_id, return result directly
        if not check_permissions or not requester_id or is_root_id(requester_id):
            return query.count()

        # Get all results
        results = query.all()

        # Use list comprehension to filter based on user access
        accessible_results = [
            result
            for result in results
            if cls.user_has_read_access(requester_id, result.id, db, minimum_role)
        ]

        # Return the count of accessible records
        return len(accessible_results)

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
        """
        Check if any records exist that match criteria and permission filters.

        Args:
            requester_id: The ID of the user making the request
            db: Database session
            joins: List of join conditions
            options: List of query options
            filters: List of filter conditions
            **kwargs: Additional filter criteria

        Returns:
            bool: True if at least one matching and accessible record exists
        """
        return cls.count(requester_id, db, joins, options, filters, **kwargs) > 0

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

        # Add deleted_at filter if column exists
        if hasattr(cls, "deleted_at"):
            filters = filters + [cls.deleted_at == None]

        # Get all matching results instead of just one
        results = build_query(db, cls, joins, options, filters, **kwargs).all()

        # Filter results based on user access permissions
        accessible_results = [
            result
            for result in results
            if cls.user_has_read_access(requester_id, result.id, db)
        ]

        # Ensure there's exactly one result after filtering
        if len(accessible_results) == 0:
            raise HTTPException(status_code=404, detail=gen_not_found_msg(cls.__name__))
        elif len(accessible_results) > 1:
            raise HTTPException(
                status_code=409,
                detail=f"Request uncovered multiple {cls.__name__} when only one was expected.",
            )

        # Get the single result
        result = accessible_results[0]

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

        # Add deleted_at filter if column exists
        if hasattr(cls, "deleted_at"):
            if filters:
                filters.append(cls.deleted_at == None)
            else: 
                filters = [cls.deleted_at == None]

        # Build base query
        query = build_query(
            db, cls, joins, options, filters, order_by, limit, offset, **kwargs
        )

        # Get all records that match the query
        all_records = query.all()

        # If permissions check is disabled or ROOT_ID, return all records
        if not check_permissions or not requester_id or is_root_id(requester_id):
            to_return = all_records
        else:
            # Filter records based on user permissions
            to_return = []
            for record in all_records:
                if cls.user_has_read_access(requester_id, record.id, db, minimum_role):
                    to_return.append(record)

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
        """
        Update a record with permission check.

        Args:
            requester_id: The ID of the user making the request
            db: Database session
            new_properties: Dictionary of properties to update
            return_type: The return type format ("db", "dict", "dto", "model")
            filters: List of filter conditions
            fields: List of fields to include in the response (only for return_type="dict")
            override_dto: Optional DTO class override
            check_permissions: Whether to apply permission checking
            **kwargs: Additional filter criteria

        Returns:
            Updated record in the specified return format
        """
        # Validate fields parameter
        if fields and return_type != "dict":
            raise HTTPException(
                status_code=400,
                detail="Fields parameter can only be used with return_type='dict'",
            )

        # Validate that fields exist on the model
        validate_fields(cls, fields)

        # Initialize update hooks if not already present
        cls._initialize_update_hooks()

        validate_columns(cls, updated=new_properties, **kwargs)

        # Get all matching results instead of just one
        results = build_query(db, cls, filters=filters, **kwargs).all()

        # Filter results based on user access permissions if check_permissions is enabled
        if check_permissions and not is_root_id(requester_id):
            # Use user_can_edit for update permission check
            from database.Permissions import user_can_edit

            accessible_results = [
                result
                for result in results
                if user_can_edit(requester_id, cls, result.id, db)
            ]
        else:
            accessible_results = results

        # Ensure there's exactly one result after filtering
        if len(accessible_results) == 0:
            raise HTTPException(status_code=404, detail=gen_not_found_msg(cls.__name__))
        elif len(accessible_results) > 1:
            raise HTTPException(
                status_code=409,
                detail=f"Request uncovered multiple {cls.__name__} to update when only one was expected.",
            )

        # Get the single result
        target = accessible_results[0]

        # Special handling for permission_references
        if hasattr(cls, "permission_references") and cls.permission_references:
            # Check if any permission reference is being updated
            for ref_name in cls.permission_references:
                ref_id_field = f"{ref_name}_id"
                if ref_id_field in new_properties and new_properties[
                    ref_id_field
                ] != getattr(target, ref_id_field, None):
                    # User is trying to update a permission reference
                    # Check if they have access to the new referenced entity
                    ref_attr = getattr(cls, ref_name, None)
                    if (
                        not ref_attr
                        or not hasattr(ref_attr, "property")
                        or not hasattr(ref_attr.property, "mapper")
                    ):
                        continue

                    ref_model = ref_attr.property.mapper.class_
                    new_ref_id = new_properties[ref_id_field]

                    # Skip if None (removing reference)
                    if new_ref_id is None:
                        continue

                    # Check if user has admin access to the new referenced entity
                    from database.Permissions import user_can_edit

                    if not user_can_edit(requester_id, ref_model, new_ref_id, db):
                        raise HTTPException(
                            status_code=403,
                            detail=f"User {requester_id} does not have permission to link to {ref_model.__name__} {new_ref_id}",
                        )

        # Call before hooks
        hooks = cls.hooks
        for hook in hooks["update"]["before"]:
            hook(
                cls,
                target,
                requester_id,
                db,
                new_properties,
                return_type,
                filters,
                override_dto,
                check_permissions,
                **kwargs,
            )

        # Update the record
        for key, value in new_properties.items():
            setattr(target, key, value)
        target.updated_by_user_id = requester_id
        db.commit()
        db.refresh(target)

        # Call after hooks
        for hook in hooks["update"]["after"]:
            hook(
                target,
                requester_id,
                db,
                new_properties,
                return_type,
                filters,
                override_dto,
                check_permissions,
                **kwargs,
            )

        logging.debug(f"Committed: {str(target)}")
        if target is None:
            logging.warning(
                f"None is about to be returned from {cls.__name__} update(): return type {return_type}/{override_dto}, {filters}, {kwargs}"
            )
        else:
            logging.debug(
                f"Returning from {cls.__name__} update: {target} ({return_type})"
            )

        return db_to_return_type(
            target,
            return_type,
            get_dto_class(cls, override_dto),
            fields=fields,
        )

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
        Delete (soft delete) a record with permission check.

        Args:
            requester_id: The ID of the user making the request
            db: Database session
            filters: List of filter conditions
            check_permissions: Whether to apply permission checking
            **kwargs: Additional filter criteria
        """
        # Initialize delete hooks if not already present
        cls._initialize_update_hooks()

        validate_columns(cls, **kwargs)

        # Get all matching results instead of just one
        results = build_query(db, cls, filters=filters, **kwargs).all()

        # Filter results based on user access permissions if check_permissions is enabled
        if check_permissions and not is_root_id(requester_id):
            # Use user_can_delete for delete permission check
            from database.Permissions import user_can_delete

            accessible_results = [
                result
                for result in results
                if user_can_delete(requester_id, cls, result.id, db)
            ]
        else:
            accessible_results = results

        # Ensure there's exactly one result after filtering
        if len(accessible_results) == 0:
            raise HTTPException(status_code=404, detail=gen_not_found_msg(cls.__name__))
        elif len(accessible_results) > 1:
            raise HTTPException(
                status_code=409,
                detail=f"Request uncovered multiple {cls.__name__} to delete when only one was expected.",
            )

        # Get the single result
        target = accessible_results[0]

        # Prevent deletion of system entities by non-system users
        if (
            hasattr(target, "user_id")
            and is_system_id(getattr(target, "user_id", None))
            and not is_root_id(requester_id)
        ):
            raise HTTPException(
                status_code=403,
                detail=f"System entities can only be deleted by system users.",
            )

        # Call before hooks
        hooks = cls.hooks
        for hook in hooks["delete"]["before"]:
            hook(cls, target, requester_id, db, filters, check_permissions, **kwargs)

        # Perform soft delete
        target.deleted_at = func.now()
        target.deleted_by_user_id = requester_id
        db.commit()
        db.refresh(target)

        # Call after hooks
        for hook in hooks["delete"]["after"]:
            hook(target, requester_id, db, filters, check_permissions, **kwargs)


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
