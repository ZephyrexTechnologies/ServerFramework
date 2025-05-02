import inspect
import logging
from datetime import combine, date, datetime, time, timedelta
from typing import Any, Callable, Dict, List, Optional, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from database.Base import get_session
from database.DB_Auth import Team, User


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


# BLL Hooks registry for all manager classes
_bll_hooks_registry = {}
hook_types = ["create", "update", "delete", "get", "list", "search"]


def get_hooks_for_manager(manager_class):
    """Get or create hooks for a manager class"""
    if manager_class not in _bll_hooks_registry:
        # Create a new hooks dictionary for this manager class with all required hook types
        _bll_hooks_registry[manager_class] = HookDict(
            {
                hook_type: HookDict({"before": [], "after": []})
                for hook_type in hook_types
            }
        )

    # Ensure all required hook types exist
    hooks = _bll_hooks_registry[manager_class]

    for hook_type in hook_types:
        if not hasattr(hooks, hook_type):
            hooks[hook_type] = HookDict({"before": [], "after": []})

    return _bll_hooks_registry[manager_class]


# Decorator for marking methods as hooks
def bll_hook(hook_type: str, time: str = "before"):
    """
    Decorator to mark a method as a hook handler for a specific BLL operation.

    Usage:
        @bll_hook("create", "before")
        def before_create_hook(self, *args, **kwargs):
            # Hook implementation
            pass

    Args:
        hook_type: Operation type ("create", "update", "delete", "get", "list", "search")
        time: Timing identifier ("before" or "after", defaults to "before")

    Returns:
        Decorator function that will mark the method as a hook handler
    """

    def decorator(method):
        # Store hook information directly on the method
        if not hasattr(method, "_bll_hook_info"):
            method._bll_hook_info = []

        hook_path = (hook_type, time)
        method._bll_hook_info.append(hook_path)

        return method

    return decorator


# Descriptor for class-level hooks
class HooksDescriptor:
    def __get__(self, obj, objtype=None):
        if objtype is None:
            objtype = type(obj)
        return get_hooks_for_manager(objtype)


# Function to discover hooks in a class
def discover_hooks(manager_class):
    """
    Discover and register all hook methods in a manager class.

    This examines all methods in the class for methods that have been
    decorated with @bll_hook and automatically registers them.

    Args:
        manager_class: The manager class to inspect for hook methods
    """
    for name, method in inspect.getmembers(manager_class, predicate=inspect.isfunction):
        if hasattr(method, "_bll_hook_info"):
            hooks = get_hooks_for_manager(manager_class)

            for hook_path in method._bll_hook_info:
                hook_type, time = hook_path

                if hook_type in hooks and time in hooks[hook_type]:
                    # Create an unbound method that will work correctly when called
                    def create_handler(method_ref):
                        def handler(*args, **kwargs):
                            return method_ref(*args, **kwargs)

                        # Preserve the original method's metadata
                        handler.__name__ = method_ref.__name__
                        handler.__doc__ = method_ref.__doc__
                        return handler

                    handler = create_handler(method)
                    hooks[hook_type][time].append(handler)
                    logging.debug(
                        f"Discovered and registered BLL hook: {hook_type}.{time} -> {method.__name__}"
                    )


class NumericalSearchModel(BaseModel):
    lt: Optional[Any] = None
    gt: Optional[Any] = None
    lteq: Optional[Any] = None
    gteq: Optional[Any] = None
    neq: Optional[Any] = None
    eq: Optional[Any] = None


class StringSearchModel(BaseModel):
    inc: Optional[str] = None
    sw: Optional[str] = None
    ew: Optional[str] = None


class DateSearchModel(BaseModel):
    before: Optional[datetime] = None
    after: Optional[datetime] = None
    on: Optional[date] = None


class BaseMixinModel(BaseModel):
    """Base mixin for all models with common audit fields."""

    id: str = Field(..., description="The unique identifier")
    created_at: datetime = Field(
        ..., description="The time and date at which this was created"
    )
    created_by_user_id: str = Field(
        ..., description="The ID of the user who performed the creation"
    )

    class Optional(BaseModel):
        id: Optional[str] = None
        created_at: Optional[datetime] = None
        created_by_user_id: Optional[str] = None

    class Search(BaseModel):
        id: Optional[StringSearchModel]
        created_at: Optional[DateSearchModel]
        created_by_user_id: Optional[StringSearchModel]


class UpdateMixinModel:
    updated_at: Optional[datetime] = Field(
        ..., description="The time and date at which this was last updated"
    )
    updated_by_user_id: Optional[str] = Field(
        ..., description="The ID of the user who made the last update"
    )

    class Optional:
        updated_at: Optional[datetime] = None
        updated_by_user_id: Optional[str] = None

    class Search:
        updated_at: Optional[DateSearchModel]
        updated_by_user_id: Optional[StringSearchModel]


class ParentMixinModel:
    parent_id: Optional[str] = Field(..., description="The ID of the relevant parent")

    class Optional:

        parent_id: Optional[str] = None
        parent: Optional[Any] = None
        children: Optional[List[Any]] = []

    class Search:
        parent_id: Optional[StringSearchModel]


class NameMixinModel:
    name: str = Field(..., description="The name")

    class Optional:
        name: Optional[str]

    class Search:
        name: Optional[StringSearchModel]


class DescriptionMixinModel:
    description: str = Field(..., description="The description")

    class Optional:
        description: Optional[str]

    class Search:
        description: Optional[StringSearchModel]


class ImageMixinModel:

    image_url: str = Field(..., description="The path to the image")

    class Optional:
        image_url: Optional[str] = None

    class Search:
        image_url: Optional[StringSearchModel]


# === Begin Template Models For Use Only in AbstractBLLManager ===
class TemplateModel(BaseMixinModel, NameMixinModel):

    class Create(BaseModel):
        pass

    class Update(BaseModel):
        pass

    class Search(BaseMixinModel.Search):
        pass


class TemplateReferenceModel(BaseMixinModel):
    template_id: Optional[str] = None
    template: Optional[TemplateModel] = None


class TemplateNetworkModel:
    class POST(BaseMixinModel):
        template: TemplateModel.Create

    class PUT(BaseMixinModel):
        template: TemplateModel.Update

    class SEARCH(BaseMixinModel):
        template: TemplateModel.Search

    class ResponseSingle(BaseMixinModel):
        template: TemplateModel

    class ResponsePlural(BaseMixinModel):
        templates: List[TemplateModel]


# === End Template Models For Use Only in AbstractBLLManager ===

T = TypeVar("T")
DtoT = TypeVar("DtoT")
ModelT = TypeVar("ModelT")


class BatchUpdateItem(BaseModel):
    """Model for a single item in a batch update operation.

    This should be kept in sync with BatchUpdateItemModel in AbstractEPRouter.py
    """

    id: str
    data: Dict[str, Any]


class IDModel(BaseMixinModel):
    """Model for ID-based operations."""

    id: str


def gen_not_found_msg(classname):
    return f"Request searched {classname} and could not find the required record."


class AbstractBLLManager:
    Model = TemplateModel
    ReferenceModel = TemplateReferenceModel
    NetworkModel = TemplateNetworkModel
    DBClass = User

    # Class-level hooks property
    hooks = HooksDescriptor()

    # Search transformer functions
    search_transformers: Dict[str, Callable] = {}

    def __init__(
        self,
        requester_id: str,
        target_user_id: Optional[str] = None,
        target_team_id: Optional[str] = None,
        db: Optional[Session] = None,
    ):
        self._db: Optional[Session] = db or get_session()
        self.requester = self.db.query(User).filter(User.id == requester_id).first()
        if self.requester is None:
            raise HTTPException(
                status_code=404,
                detail=f"Requesting user with id {requester_id} not found.",
            )
        self.target_user_id: str = target_user_id or requester_id
        self.target_team_id: str = target_team_id

        self._target_user = None
        self._target_team = None

        # Initialize any search transformers
        self._register_search_transformers()

        # Discover and register hooks
        discover_hooks(self.__class__)

    def _register_search_transformers(self):
        """
        Register custom search transformers for this manager.
        Override this method to register specific search transformers.

        Example:
            self.register_search_transformer('overdue', self._transform_overdue_search)
        """
        pass

    def register_search_transformer(self, field_name: str, transformer: Callable):
        """
        Register a search transformer function for a specific field.

        Args:
            field_name: The name of the field or concept to transform
            transformer: A function that takes a value and returns a list of filter conditions
        """
        self.search_transformers[field_name] = transformer

    def __del__(self):
        if hasattr(self, "_db") and self._db is not None:
            self._db.close()
            self._db = None

    def __enter__(self) -> "AbstractBLLManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if hasattr(self, "_db") and self._db is not None:
            self._db.close()
            self._db = None

    def get_field_types(self):
        """Analyzes the Model class to categorize fields by type."""
        string_fields = []
        numeric_fields = []
        date_fields = []
        boolean_fields = []

        # Get all annotations from the model
        for field_name, field_info in self.Model.__annotations__.items():
            # Handle Optional types
            if getattr(field_info, "__origin__", None) == Optional:
                actual_type = field_info.__args__[0]
            else:
                actual_type = field_info

            # Categorize by type
            if actual_type == str:
                string_fields.append(field_name)
            elif actual_type in (int, float):
                numeric_fields.append(field_name)
            elif actual_type == bool:
                boolean_fields.append(field_name)
            elif actual_type in (date, datetime):
                date_fields.append(field_name)

        return string_fields, numeric_fields, date_fields, boolean_fields

    def build_search_filters(
        self,
        search_params: Dict[str, Any],
    ) -> List:
        """Build SQLAlchemy filters from search parameters."""
        filters = []
        string_fields, numeric_fields, date_fields, boolean_fields = (
            self.get_field_types()
        )

        for field_name, value in search_params.items():
            # Skip processing None values
            if value is None:
                continue

            # Check if we have a custom transformer for this field
            if field_name in self.search_transformers:
                # Apply the custom transformer and add the resulting filters
                custom_filters = self.search_transformers[field_name](value)
                if custom_filters:
                    if isinstance(custom_filters, list):
                        filters.extend(custom_filters)
                    else:
                        filters.append(custom_filters)
                continue

            # If not a custom field, check if field exists in the model
            if not hasattr(self.DBClass, field_name):
                continue

            field = getattr(self.DBClass, field_name)

            # Handle string pattern matching operations
            if field_name in string_fields and isinstance(value, dict):
                string_pattern_applied = False

                # Process string pattern operations
                if "inc" in value and value["inc"] is not None:
                    filters.append(field.ilike(f"%{value['inc']}%"))
                    string_pattern_applied = True

                if "sw" in value and value["sw"] is not None:
                    filters.append(field.ilike(f"{value['sw']}%"))
                    string_pattern_applied = True

                if "ew" in value and value["ew"] is not None:
                    filters.append(field.ilike(f"%{value['ew']}"))
                    string_pattern_applied = True

                # Skip to next field if any string pattern was applied
                if string_pattern_applied:
                    continue

            # Handle numeric comparison operators
            elif field_name in numeric_fields and isinstance(value, dict):
                conditions = []

                if "eq" in value and value["eq"] is not None:
                    conditions.append(field == value["eq"])
                if "neq" in value and value["neq"] is not None:
                    conditions.append(field != value["neq"])
                if "lt" in value and value["lt"] is not None:
                    conditions.append(field < value["lt"])
                if "gt" in value and value["gt"] is not None:
                    conditions.append(field > value["gt"])
                if "lteq" in value and value["lteq"] is not None:
                    conditions.append(field <= value["lteq"])
                if "gteq" in value and value["gteq"] is not None:
                    conditions.append(field >= value["gteq"])

                if conditions:
                    filters.append(and_(*conditions))
                    continue

            # Handle date field operations
            elif field_name in date_fields and isinstance(value, dict):
                conditions = []

                if "before" in value and value["before"] is not None:
                    conditions.append(field < value["before"])
                if "after" in value and value["after"] is not None:
                    conditions.append(field > value["after"])
                if "on" in value and value["on"] is not None:
                    # For date equality, typically check for the entire day
                    # Use the full datetime module path now
                    if isinstance(field.type, (date, datetime)):
                        on_date = value["on"]  # This is expected to be a date object
                        # Create datetime objects for start and end of the day using the datetime module
                        start_of_day = combine(on_date, time.min)
                        # Use start of the *next* day for the upper bound (exclusive)
                        start_of_next_day = combine(
                            on_date + timedelta(days=1), time.min
                        )
                        conditions.append(
                            and_(field >= start_of_day, field < start_of_next_day)
                        )

                    else:
                        # Fallback for unexpected field types
                        conditions.append(field == value["on"])

                if conditions:
                    filters.append(and_(*conditions))
                    continue

            # Handle boolean field operations
            elif field_name in boolean_fields and isinstance(value, dict):
                if "is_true" in value and value["is_true"] is not None:
                    filters.append(field == value["is_true"])
                    continue

            # For dictionaries that weren't handled by specific patterns,
            # extract the actual values rather than passing the dict directly
            if isinstance(value, dict):
                # Skip dictionaries that don't match our expected patterns
                continue

            # Handle regular exact match (for non-dict values)
            filters.append(field == value)

        return filters

    @staticmethod
    def generate_joins(model_class, include_fields):
        """Generate join loads based on specified include fields."""
        joins = []

        for field in include_fields:
            if hasattr(model_class, field):
                # Handle nested includes (e.g., 'user.roles')
                if "." in field:
                    parts = field.split(".")
                    current_attr = getattr(model_class, parts[0])
                    joins.append(joinedload(current_attr))

                    # Build nested joinloads for deeper relationships
                    current_join = joins[-1]
                    for part in parts[1:]:
                        if hasattr(current_attr.property.mapper.class_, part):
                            nested_attr = getattr(
                                current_attr.property.mapper.class_, part
                            )
                            current_join = current_join.joinedload(nested_attr)
                else:
                    joins.append(joinedload(getattr(model_class, field)))

        return joins

    @property
    def db(self) -> Session:
        """Property that returns an active database session, creating a new one if needed."""
        if self._db is None or not self._db.is_active:
            self._db = get_session()
        return self._db

    @property
    def target_user(self) -> User:
        if self._target_user is None:
            if self.target_user_id == self.requester.id:
                return self.requester
            else:
                self._target_user = (
                    self.db.query(User).filter(User.id == self.target_user_id).first()
                )
        return self._target_user

    @property
    def target_team(self) -> Team:
        if self._target_team is None:
            self._target_team = (
                self.db.query(Team).filter(Team.id == self.target_team_id).first()
            )
        return self._target_team

    def createValidation(self, entity):
        """Override this method to add validation logic for entity creation."""
        pass

    def create(self, **kwargs) -> Any:
        """Create one or more entities."""
        # Handle single entity or list of entities
        if "entities" in kwargs and isinstance(kwargs["entities"], list):
            entities = kwargs.pop("entities")
            results = []
            for entity_data in entities:
                # Merge entity data with remaining kwargs
                entity_kwargs = {**kwargs, **entity_data}
                results.append(self._create_single_entity(**entity_kwargs))
            return results
        else:
            return self._create_single_entity(**kwargs)

    def _create_single_entity(self, **kwargs) -> Any:
        """Create a single entity."""
        args = self.Model.Create(**kwargs)
        self.createValidation(args)

        # Convert arguments to dictionary, excluding unset values
        create_args = {
            k: v
            for k, v in args.model_dump(exclude_unset=True).items()
            if v is not None
        }

        # Call before hooks
        hooks = self.__class__.hooks
        for hook in hooks["create"]["before"]:
            hook(self, create_args)

        # Check if the database class has a user_id column and add target_user_id if it does
        if hasattr(self.DBClass, "user_id") and "user_id" not in create_args:
            create_args["user_id"] = self.target_user_id

        # Create the entity
        entity = self.DBClass.create(
            requester_id=self.requester.id,
            db=self.db,
            return_type="dto",
            override_dto=self.Model,
            **create_args,
        )

        # Call after hooks
        for hook in hooks["create"]["after"]:
            hook(self, entity, create_args)

        return entity

    def get(
        self,
        include: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
        **kwargs,
    ) -> Any:
        """Get an entity with optional included relationships."""
        options = []

        if include:
            options = self.generate_joins(self.DBClass, include)
        if fields:
            from sqlalchemy.orm import load_only

        return self.DBClass.get(
            requester_id=self.requester.id,
            db=self.db,
            return_type="dto",
            override_dto=self.Model,
            options=options,
            **kwargs,
        )

    def list(
        self,
        include: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "asc",
        filters: Optional[List[Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        **kwargs,
    ) -> List[Any]:
        """List entities with optional included relationships."""
        options = []
        order_by = None
        if include:
            options = self.generate_joins(self.DBClass, include)
        if fields:
            from sqlalchemy.orm import load_only

            options.append(load_only(*fields))
        if sort_by:
            from sqlalchemy import asc, desc

            if hasattr(self.DBClass, sort_by):
                column = getattr(self.DBClass, sort_by)
                if sort_order.lower() == "asc":
                    order_by = [asc(column)]
                else:
                    order_by = [desc(column)]

        return self.DBClass.list(
            requester_id=self.requester.id,
            db=self.db,
            return_type="dto",
            override_dto=self.Model,
            options=options,
            order_by=order_by,
            limit=limit,
            offset=offset,
            filters=filters,
            **kwargs,
        )

    def search(
        self,
        include: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "asc",
        filters: Optional[List[Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        **search_params,
    ) -> List[Any]:
        """Search entities with optional included relationships."""
        options = []
        order_by = None
        # Separate kwargs for simple filter_by and complex dicts for build_search_filters
        simple_kwargs = {}
        complex_search_params = {}
        for key, value in search_params.items():
            if isinstance(value, dict):
                complex_search_params[key] = value
            else:
                simple_kwargs[key] = value

        # Convert include to SQLAlchemy joinedload options
        if include:
            options = self.generate_joins(self.DBClass, include)

        # Convert fields to SQLAlchemy load_only option
        if fields:
            from sqlalchemy.orm import load_only

            options.append(load_only(*fields))

        # Convert sort_by and sort_order to SQLAlchemy order_by expression
        if sort_by:
            from sqlalchemy import asc, desc

            if hasattr(self.DBClass, sort_by):
                column = getattr(self.DBClass, sort_by)
                if sort_order.lower() == "asc":
                    order_by = [asc(column)]
                else:
                    order_by = [desc(column)]

        # Generate filters from complex search_params only
        search_filters = self.build_search_filters(complex_search_params)
        combined_filters = filters + search_filters if filters else search_filters

        # Pass the converted SQLAlchemy constructs to the DBClass.list method
        # Use combined_filters for the 'filters' arg and simple_kwargs for '**kwargs'
        return self.DBClass.list(
            requester_id=self.requester.id,
            db=self.db,
            return_type="dto",
            override_dto=self.Model,
            options=options,
            order_by=order_by,
            limit=limit,
            offset=offset,
            filters=combined_filters,  # Filters from build_search_filters
            **simple_kwargs,  # Simple equality kwargs for filter_by
        )

    def update(self, id: str, **kwargs):
        """Update an entity by ID."""
        args = self.Model.Update(**kwargs)

        # Convert arguments to dictionary, excluding unset values
        update_args = {
            k: v
            for k, v in args.model_dump(exclude_unset=True).items()
            if v is not None
        }

        # Call before hooks
        hooks = self.__class__.hooks
        for hook in hooks["update"]["before"]:
            hook(self, id, update_args)

        # Get the entity before update (for after hooks)
        entity_before = self.get(id=id)

        # Update the entity
        updated_entity = self.DBClass.update(
            requester_id=self.requester.id,
            db=self.db,
            return_type="dto",
            override_dto=self.Model,
            new_properties=update_args,
            id=id,
        )

        # Call after hooks
        for hook in hooks["update"]["after"]:
            hook(self, updated_entity, entity_before, update_args)

        return updated_entity

    def batch_update(self, items: List[Dict[str, Any]]) -> List[Any]:
        """Update multiple entities in a batch.

        Args:
            items: List of dictionaries containing 'id' and 'data' for each entity to update

        Returns:
            List of updated entities
        """
        results = []
        errors = []

        # Process each update
        for item in items:
            try:
                entity_id = item.get("id")
                if not entity_id:
                    raise ValueError("Missing required 'id' field in batch update item")

                update_data = item.get("data", {})
                updated_entity = self.update(id=entity_id, **update_data)
                results.append(updated_entity)
            except Exception as e:
                # Collect errors but continue processing other items
                errors.append({"id": item.get("id", "unknown"), "error": str(e)})

        # If any errors occurred, raise an HTTPException with details
        if errors:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "One or more batch update operations failed",
                    "errors": errors,
                    "successful_updates": len(results),
                    "failed_updates": len(errors),
                },
            )

        return results

    def delete(self, id: str):
        """Delete an entity by ID."""
        # Call before hooks
        hooks = self.__class__.hooks

        # Get the entity before delete (for after hooks)
        entity_before = self.get(id=id)

        for hook in hooks["delete"]["before"]:
            hook(self, id, entity_before)

        # Delete the entity
        self.DBClass.delete(
            requester_id=self.requester.id,
            db=self.db,
            id=id,
        )

        # Call after hooks
        for hook in hooks["delete"]["after"]:
            hook(self, id, entity_before)

    def batch_delete(self, ids: List[str]):
        """Delete multiple entities in a batch.

        Args:
            ids: List of entity IDs to delete

        Returns:
            None
        """
        errors = []
        successful_deletes = 0

        # Process each delete operation
        for entity_id in ids:
            try:
                self.delete(id=entity_id)
                successful_deletes += 1
            except Exception as e:
                # Collect errors but continue processing other items
                errors.append({"id": entity_id, "error": str(e)})

        # If any errors occurred, raise an HTTPException with details
        if errors:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "One or more batch delete operations failed",
                    "errors": errors,
                    "successful_deletes": successful_deletes,
                    "failed_deletes": len(errors),
                },
            )


class BaseCreateModel(NameMixinModel):
    """Base model for create operations."""

    pass


class BaseEntityModel(BaseMixinModel, NameMixinModel):
    """Base model for all entities."""

    pass
