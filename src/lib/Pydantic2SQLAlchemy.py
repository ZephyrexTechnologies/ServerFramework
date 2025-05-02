import inspect
import re
import sys
import uuid
from datetime import datetime
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic import BaseModel, Field
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship

# Import Base class
try:
    from database.Base import Base
except ImportError:
    # Create a placeholder Base class for documentation/testing
    from sqlalchemy.ext.declarative import declarative_base

    Base = declarative_base()

from database.AbstractDatabaseEntity import BaseMixin, ImageMixin, UpdateMixin

# Type variable for generic models
T = TypeVar("T")

# Map Pydantic types to SQLAlchemy types
TYPE_MAPPING = {
    str: String,
    int: Integer,
    bool: Boolean,
    datetime: DateTime,
    uuid.UUID: String,
    float: Float,
    dict: JSON,
    list: JSON,
    # Add more type mappings as needed
}

# Regex to extract tablename from a class name
TABLENAME_REGEX = re.compile(r"(?<!^)(?=[A-Z])")

# Dictionary to store created models - using fully qualified names to avoid conflicts
MODEL_REGISTRY = {}

# Keep track of related model names that should use fully qualified paths
QUALIFIED_RELATIONSHIP_TARGETS = set()

# Current SQLAlchemy base class to use
_CURRENT_BASE = Base


def clear_registry_cache():
    """
    Clear all cached mapper configurations to allow reconfiguration.
    Use this when there are mapper initialization issues.
    """
    # First clear our own MODEL_REGISTRY
    MODEL_REGISTRY.clear()
    QUALIFIED_RELATIONSHIP_TARGETS.clear()


def set_base_model(base_model):
    """
    Set the Base model to use for all model creation.
    This allows for test overrides.
    """
    global _CURRENT_BASE
    _CURRENT_BASE = base_model


def register_model(model_class: Type, model_name: str) -> None:
    """
    Register a model in the registry with proper qualification.

    Args:
        model_class: The SQLAlchemy model class to register
        model_name: The name to use for the model (without module qualification)
    """
    module_name = model_class.__module__
    fully_qualified_name = f"{module_name}.{model_name}"

    # Register with fully qualified name
    MODEL_REGISTRY[fully_qualified_name] = model_class

    # Check for conflicts with the simple name
    if model_name in MODEL_REGISTRY:
        # If there's already a model registered with this name but from a different module
        existing_model = MODEL_REGISTRY[model_name]
        if existing_model.__module__ != module_name:
            # Mark this name as requiring qualification
            QUALIFIED_RELATIONSHIP_TARGETS.add(model_name)
            # Don't overwrite the existing simple name mapping
            return

    # Register with simple name (either no conflict exists or we're from the same module)
    MODEL_REGISTRY[model_name] = model_class


def get_entity_module_class(
    entity_class_name: str,
) -> tuple[Optional[str], Optional[Type]]:
    """
    Get entity class from registry or try to find it in the scope.
    Returns a tuple of (module_name, class).
    """
    # Check registry first (both simple name and fully qualified names)
    if entity_class_name in MODEL_REGISTRY:
        model_class = MODEL_REGISTRY[entity_class_name]
        module_name = model_class.__module__
        return module_name, model_class

    # Look for fully qualified matches
    for key, model_class in MODEL_REGISTRY.items():
        if key.endswith(f".{entity_class_name}"):
            module_name = model_class.__module__
            return module_name, model_class

    # If still not found, check if a similar class name exists
    # For example, looking for User but there's a UserModel
    if f"{entity_class_name}Model" in MODEL_REGISTRY:
        model_class = MODEL_REGISTRY[f"{entity_class_name}Model"]
        module_name = model_class.__module__
        return module_name, model_class

    # Look for similarly named class in qualified names
    for key, model_class in MODEL_REGISTRY.items():
        if key.endswith(f".{entity_class_name}Model"):
            module_name = model_class.__module__
            return module_name, model_class

    # Try to find in modules
    calling_frame = inspect.currentframe().f_back
    if calling_frame:
        # Check the caller's globals first
        caller_globals = calling_frame.f_globals
        if entity_class_name in caller_globals:
            obj = caller_globals[entity_class_name]
            if isinstance(obj, type) and hasattr(obj, "__tablename__"):
                return obj.__module__, obj

    # Check all loaded modules as a last resort
    for module_name, module in sys.modules.items():
        if module and hasattr(module, entity_class_name):
            obj = getattr(module, entity_class_name)
            if isinstance(obj, type) and hasattr(obj, "__tablename__"):
                return module_name, obj

    return None, None


def get_relationship_target(entity_class_name: str) -> str:
    """
    Get the appropriate target string for a relationship.
    Uses fully qualified name if needed to avoid ambiguity.

    Args:
        entity_class_name: The name of the target entity class

    Returns:
        A string suitable for use as the target in a relationship
    """
    # Always use full qualification if the name is known to be ambiguous
    if entity_class_name in QUALIFIED_RELATIONSHIP_TARGETS:
        module_name, entity_class = get_entity_module_class(entity_class_name)
        if module_name:
            return f"{module_name}.{entity_class_name}"

    # Look up the entity to see if we need to qualify it
    module_name, entity_class = get_entity_module_class(entity_class_name)
    if module_name:
        # Check if other classes with the same name exist
        count = 0
        for key, _ in MODEL_REGISTRY.items():
            if key == entity_class_name or key.endswith(f".{entity_class_name}"):
                count += 1

        # Use fully qualified name if there are multiple classes with this name
        if count > 1:
            QUALIFIED_RELATIONSHIP_TARGETS.add(entity_class_name)
            return f"{module_name}.{entity_class_name}"

    # Default to simple name
    return entity_class_name


class ModelConverter:
    """
    Utility class to convert between Pydantic models and SQLAlchemy models.
    """

    @staticmethod
    def create_sqlalchemy_model(
        pydantic_model: Type[BaseModel],
        tablename: Optional[str] = None,
        table_comment: Optional[str] = None,
        base_model=None,
    ) -> Type:
        """
        Create a SQLAlchemy model from a Pydantic model.

        Args:
            pydantic_model: The Pydantic model class to convert
            tablename: Optional explicit table name (default: derived from class name)
            table_comment: Optional comment for the table
            base_model: Optional base model to use (default: _CURRENT_BASE from module)

        Returns:
            A SQLAlchemy model class
        """
        # Get the base model to use (allows for test override)
        actual_base = base_model if base_model is not None else _CURRENT_BASE

        # Get model name (remove 'Model' suffix for SQLAlchemy class)
        pydantic_name = pydantic_model.__name__
        model_name = pydantic_name
        if model_name.endswith("Model"):
            model_name = model_name[:-5]  # Remove 'Model' suffix

        # Generate fully qualified name for registry
        module_name = pydantic_model.__module__
        fully_qualified_name = f"{module_name}.{model_name}"

        # Check if model is already created
        if fully_qualified_name in MODEL_REGISTRY:
            return MODEL_REGISTRY[fully_qualified_name]

        # Also check by simple name for backward compatibility
        if model_name in MODEL_REGISTRY:
            return MODEL_REGISTRY[model_name]

        if not tablename:
            # Convert CamelCase to snake_case and pluralize
            tablename = TABLENAME_REGEX.sub("_", model_name).lower()
            if not tablename.endswith("s"):
                tablename += "s"

        # Create a class dictionary for all columns and relationships
        class_dict = {
            "__tablename__": tablename,
            "__table_args__": {
                "comment": table_comment if table_comment else f"{model_name} table",
                "extend_existing": True,
            },
        }

        # Determine base classes from Pydantic model's inheritance
        base_classes = []

        # Check for mixins in the inheritance
        if hasattr(pydantic_model, "__bases__"):
            for base in pydantic_model.__bases__:
                base_name = base.__name__
                if base_name == "BaseMixinModel":
                    base_classes.append(BaseMixin)
                elif base_name == "UpdateMixinModel":
                    base_classes.append(UpdateMixin)
                elif base_name == "ImageMixinModel":
                    base_classes.append(ImageMixin)
                elif base_name == "ParentMixinModel":
                    # Use our fixed ParentRelationshipMixin instead of ParentMixin
                    base_classes.append(ParentRelationshipMixin)
                elif (
                    base_name == "Optional"
                    and hasattr(base, "__module__")
                    and "ImageMixinModel" in base.__module__
                ):
                    # Handle ImageMixinModel.Optional case
                    base_classes.append(ImageMixin)

        # Get a list of fields that are already defined by the base classes
        # so we don't override them and cause conflicts
        existing_columns = set()
        for base_class in base_classes:
            if hasattr(base_class, "__table__") and not isinstance(
                base_class, type(actual_base)
            ):
                # Get columns from an already mapped class
                existing_columns.update(
                    col.name for col in base_class.__table__.columns
                )
            elif hasattr(base_class, "__dict__"):
                # Get columns from a mixin class
                for key, value in base_class.__dict__.items():
                    if isinstance(value, Column) or (
                        isinstance(value, declared_attr) and key != "__tablename__"
                    ):
                        existing_columns.add(key)
                    # Check for declared_attr methods that return columns
                    elif callable(value) and hasattr(value, "__get__"):
                        existing_columns.add(key)

        # Process regular fields, excluding those already defined in base classes
        type_hints = get_type_hints(pydantic_model)

        # Filter out _id fields that will be handled with foreign keys, and already existing fields
        for name, field_type in type_hints.items():
            if name.startswith("_") or name.endswith("_id") or name in existing_columns:
                continue

            # Find field info - need to handle both Pydantic v1 and v2
            field_info = None

            # Method 1: Check __fields__ dictionary (Pydantic v1)
            if (
                hasattr(pydantic_model, "__fields__")
                and name in pydantic_model.__fields__
            ):
                field_info = pydantic_model.__fields__[name]

            # Method 2: Check model_fields dictionary (Pydantic v2)
            elif (
                hasattr(pydantic_model, "model_fields")
                and name in pydantic_model.model_fields
            ):
                field_info = pydantic_model.model_fields[name]

            # Method 3: Look for Field instances in class variables
            if field_info is None:
                for attr_name, attr_value in vars(pydantic_model).items():
                    if attr_name == name and isinstance(attr_value, Field):
                        field_info = attr_value
                        break

            # Method 4: Try to find annotations with default values
            if field_info is None:
                annotations = getattr(pydantic_model, "__annotations__", {})
                if name in annotations and hasattr(pydantic_model, name):
                    # Create a minimal field info with the default value
                    default_value = getattr(pydantic_model, name)
                    if default_value is not None:
                        field_info = {"default": default_value}

            # Create SQLAlchemy column
            column = ModelConverter._create_column_from_field(
                name, field_type, field_info
            )
            if column is not None:
                class_dict[name] = column

        # Process reference fields
        if hasattr(pydantic_model, "ReferenceID"):
            ref_class = pydantic_model.ReferenceID
            ref_fields = get_type_hints(ref_class)

            # Get optional fields
            optional_fields = set()
            if hasattr(ref_class, "Optional"):
                optional_fields = set(get_type_hints(ref_class.Optional).keys())

            # Process each reference field
            for name, field_type in ref_fields.items():
                if name.endswith("_id") and name not in existing_columns:
                    entity_name = name[:-3]  # Remove '_id' suffix
                    entity_class_name = entity_name.capitalize()
                    is_optional = name in optional_fields

                    # Try to find the referenced entity with module qualification
                    entity_module, entity_class = get_entity_module_class(
                        entity_class_name
                    )

                    # Skip if the entity and its foreign key are already defined
                    if entity_name in existing_columns or name in existing_columns:
                        continue

                    # Add foreign key column
                    if entity_class:
                        try:
                            ref_table = entity_class.__tablename__
                            class_dict[name] = Column(
                                String,
                                ForeignKey(f"{ref_table}.id"),
                                nullable=is_optional,
                                comment=f"{'Optional f' if is_optional else 'F'}oreign key to {entity_class_name}",
                            )

                            # Get the appropriate target name for the relationship
                            target_name = get_relationship_target(entity_class_name)

                            # Add relationship with lazy loading to prevent circular reference issues
                            class_dict[entity_name] = relationship(
                                target_name,
                                backref=f"{tablename}_{'optional' if is_optional else 'required'}",
                                lazy="selectin",
                            )
                        except Exception as e:
                            # If there's an issue with the relationship, still create the column
                            # but skip the relationship part to avoid mapper configuration errors
                            if name not in class_dict:
                                class_dict[name] = Column(
                                    String,
                                    nullable=is_optional,
                                    comment=f"{'Optional f' if is_optional else 'F'}oreign key to {entity_class_name} (error: {str(e)})",
                                )
                    else:
                        # Create placeholder column if entity class not found
                        class_dict[name] = Column(
                            String,
                            nullable=is_optional,
                            comment=f"{'Optional f' if is_optional else 'F'}oreign key to {entity_class_name} (not found)",
                        )

        # Create a new class that inherits from actual_base and mixins
        # But use a stable class name without UUID to avoid issues with metaclasses
        class_name = model_name
        if class_name in globals():
            # Only add UUID if name conflict exists
            class_name = f"{model_name}_{uuid.uuid4().hex[:8]}"

        model_class = type(
            class_name,
            (actual_base, *base_classes),
            class_dict,
        )

        # Register the model with our helper
        register_model(model_class, model_name)

        return model_class

    @staticmethod
    def _create_column_from_field(
        name: str, field_type: Any, field_info: Any = None
    ) -> Optional[Column]:
        """
        Create a SQLAlchemy Column from a Pydantic field.

        Args:
            name: Field name
            field_type: Field type (from type annotations)
            field_info: Optional Pydantic field info object

        Returns:
            SQLAlchemy Column or None if it should be skipped
        """
        # Skip reference ID fields that will be handled separately
        if name.endswith("_id"):
            return None

        # Handle Optional types
        is_optional = False
        if get_origin(field_type) is Union:
            args = get_args(field_type)
            if type(None) in args:
                is_optional = True
                # Extract the actual type from Optional
                non_none_args = [arg for arg in args if arg is not type(None)]
                if non_none_args:
                    field_type = non_none_args[0]

        # Handle List and Dict types
        if get_origin(field_type) in (list, List):
            # For List types, use JSON type
            sa_type = JSON
        elif get_origin(field_type) in (dict, Dict):
            # For Dict types, use JSON type
            sa_type = JSON
        else:
            # Get the SQLAlchemy type for regular types
            sa_type = TYPE_MAPPING.get(field_type, String)

        # Extract field parameters
        params = {}

        # Default nullable based on Optional status
        params["nullable"] = is_optional

        # Add primary key for id columns
        if name == "id":
            params["primary_key"] = True
            params["nullable"] = False

        if field_info:
            # Extract description/comment from various possible locations
            comment = None

            # Try different ways Pydantic might store the description
            if hasattr(field_info, "description") and field_info.description:
                comment = field_info.description
            elif (
                hasattr(field_info, "json_schema_extra")
                and field_info.json_schema_extra
            ):
                # Pydantic v2 might store it here
                if (
                    isinstance(field_info.json_schema_extra, dict)
                    and "description" in field_info.json_schema_extra
                ):
                    comment = field_info.json_schema_extra["description"]
            elif hasattr(field_info, "schema") and callable(field_info.schema):
                # Try to get from schema (Pydantic v1)
                try:
                    schema = field_info.schema()
                    if isinstance(schema, dict) and "description" in schema:
                        comment = schema["description"]
                except:
                    pass

            if comment:
                params["comment"] = comment

            # Get default value (compatible with both Pydantic v1 and v2)
            default_value = None

            # Look for default in various places
            if hasattr(field_info, "default") and field_info.default is not ...:
                default_value = field_info.default
            elif (
                hasattr(field_info, "default_factory")
                and field_info.default_factory is not None
                and field_info.default_factory is not ...
            ):
                try:
                    default_value = field_info.default_factory()
                except:
                    pass

            if default_value is not None and default_value is not ...:
                params["default"] = default_value

            # Extract constraints
            if hasattr(field_info, "unique") and field_info.unique:
                params["unique"] = True

            # Look for uniqueness in schema extras
            if hasattr(field_info, "json_schema_extra") and isinstance(
                field_info.json_schema_extra, dict
            ):
                if field_info.json_schema_extra.get("unique") is True:
                    params["unique"] = True

        # Create the column
        return Column(sa_type, **params)

    @staticmethod
    def create_reference_mixin(entity_class_name: str, entity_class: Type) -> Type:
        """
        Create a reference mixin class for relationships.

        Args:
            entity_class_name: The name of the entity class
            entity_class: The actual entity class

        Returns:
            A reference mixin class with Optional inner class
        """
        # Get the lowercase name and foreign key field name
        attr_name = entity_class_name.lower()
        fk_name = f"{attr_name}_id"

        # The entity's tablename for creating the foreign key
        tablename = entity_class.__tablename__

        # Get the fully qualified target for the relationship
        relationship_target = get_relationship_target(entity_class_name)

        # Create reference mixin class with proper attribute naming
        class RefMixin:
            """Mixin class that adds a reference to another entity"""

            pass

        # Create optional reference mixin
        class OptionalRefMixin:
            """Mixin class that adds an optional reference to another entity"""

            pass

        # Create foreign key column for specific entity
        @declared_attr
        def required_fk(cls):
            return Column(
                String,
                ForeignKey(f"{tablename}.id"),
                nullable=False,
                comment=f"Foreign key to {entity_class_name}",
            )

        # Relationship property for specific entity
        @declared_attr
        def required_rel(cls):
            return relationship(
                relationship_target,
                backref=(
                    f"ref_{cls.__tablename__}"
                    if hasattr(cls, "__tablename__")
                    else None
                ),
            )

        # Create foreign key column for optional entity
        @declared_attr
        def optional_fk(cls):
            return Column(
                String,
                ForeignKey(f"{tablename}.id"),
                nullable=True,
                comment=f"Optional foreign key to {entity_class_name}",
            )

        # Relationship property for optional entity
        @declared_attr
        def optional_rel(cls):
            return relationship(
                relationship_target,
                backref=(
                    f"opt_ref_{cls.__tablename__}"
                    if hasattr(cls, "__tablename__")
                    else None
                ),
            )

        # Dynamically set the attributes with the correct names
        setattr(RefMixin, fk_name, required_fk)
        setattr(RefMixin, attr_name, required_rel)
        setattr(OptionalRefMixin, fk_name, optional_fk)
        setattr(OptionalRefMixin, attr_name, optional_rel)

        # Attach the Optional inner class
        RefMixin.Optional = OptionalRefMixin

        return RefMixin

    @staticmethod
    def pydantic_to_dict(pydantic_obj: BaseModel) -> Dict[str, Any]:
        """
        Convert a Pydantic model instance to a dictionary suitable for SQLAlchemy.
        Removes any fields that don't belong in the SQLAlchemy model.

        Args:
            pydantic_obj: Pydantic model instance

        Returns:
            Dictionary with only the valid SQLAlchemy fields
        """
        # Handle both Pydantic v1 and v2
        try:
            if hasattr(pydantic_obj, "model_dump"):
                # Pydantic v2
                data = pydantic_obj.model_dump(exclude_unset=True)
            elif hasattr(pydantic_obj, "dict"):
                # Pydantic v1
                data = pydantic_obj.dict(exclude_unset=True)
            else:
                # Fallback
                data = {
                    k: v
                    for k, v in pydantic_obj.__dict__.items()
                    if not k.startswith("_")
                }
        except Exception as e:
            # Fallback if the methods fail
            data = {
                k: v for k, v in pydantic_obj.__dict__.items() if not k.startswith("_")
            }

        # Remove any fields that shouldn't be passed to SQLAlchemy
        # (like nested models or computed fields)
        keys_to_remove = []
        for key, value in data.items():
            if isinstance(value, BaseModel):
                keys_to_remove.append(key)
            elif isinstance(value, list) and value and isinstance(value[0], BaseModel):
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del data[key]

        return data

    @staticmethod
    def sqlalchemy_to_pydantic(
        sa_obj: Any, pydantic_class: Type[BaseModel]
    ) -> BaseModel:
        """
        Convert a SQLAlchemy model instance to a Pydantic model instance.

        Args:
            sa_obj: SQLAlchemy model instance
            pydantic_class: Target Pydantic model class

        Returns:
            Pydantic model instance
        """
        # Convert SQLAlchemy model to dict
        if hasattr(sa_obj, "__dict__"):
            # Extract data from SQLAlchemy model
            data = {}
            for key, value in sa_obj.__dict__.items():
                if not key.startswith("_"):
                    data[key] = value

            # Get model fields and provide default values
            try:
                # Initialize missing optional fields with None
                for field_name, field_type in get_type_hints(pydantic_class).items():
                    if (
                        field_name not in data
                        and get_origin(field_type) is Union
                        and type(None) in get_args(field_type)
                    ):
                        data[field_name] = None

                # Create Pydantic model instance based on version
                try:
                    if hasattr(pydantic_class, "model_validate"):
                        # Pydantic v2
                        return pydantic_class.model_validate(data)
                    elif hasattr(pydantic_class, "parse_obj"):
                        # Pydantic v1
                        return pydantic_class.parse_obj(data)
                    else:
                        # Direct instantiation
                        return pydantic_class(**data)
                except Exception as e:
                    # If the above fails, try direct instantiation
                    return pydantic_class(**data)
            except Exception as e:
                raise ValueError(
                    f"Failed to convert SQLAlchemy object to Pydantic: {str(e)}"
                )
        else:
            # Handle the case where sa_obj is already a dict
            try:
                if hasattr(pydantic_class, "model_validate"):
                    # Pydantic v2
                    return pydantic_class.model_validate(sa_obj)
                elif hasattr(pydantic_class, "parse_obj"):
                    # Pydantic v1
                    return pydantic_class.parse_obj(sa_obj)
                else:
                    # Direct instantiation
                    return pydantic_class(**sa_obj)
            except Exception as e:
                # If the above fails, try direct instantiation
                try:
                    return pydantic_class(**sa_obj)
                except Exception as nested_e:
                    raise ValueError(
                        f"Failed to convert dict to Pydantic: {str(e)}, nested error: {str(nested_e)}"
                    )


# Common Pydantic model mixins that match the SQLAlchemy mixins
class BaseMixinModel(BaseModel):
    id: Optional[str] = Field(None, description="Unique identifier")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    created_by_user_id: Optional[str] = Field(
        None, description="ID of the user who created this record"
    )


class UpdateMixinModel(BaseModel):
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    updated_by_user_id: Optional[str] = Field(
        None, description="ID of the user who last updated this record"
    )


class ImageMixinModel(BaseModel):
    image_url: Optional[str] = Field(
        None, description="URL to the image for this record"
    )

    class Optional:
        image_url: Optional[str] = Field(None, description="Optional image URL")


class ParentMixinModel(BaseModel):
    parent_id: Optional[str] = Field(None, description="ID of the parent record")


# Search model for string fields
class StringSearchModel(BaseModel):
    contains: Optional[str] = None
    equals: Optional[str] = None
    starts_with: Optional[str] = None
    ends_with: Optional[str] = None
    in_list: Optional[List[str]] = None


# Fix circular imports and handle parent relationship properly
class ParentRelationshipMixin:
    """Modified version of ParentMixin that sets up the self-reference correctly"""

    @declared_attr
    def parent_id(cls):
        return Column(
            String,
            ForeignKey(lambda: cls.__tablename__ + ".id"),
            nullable=True,
            comment="ID of the parent record",
        )

    @declared_attr
    def parent(cls):
        return relationship(
            lambda: cls,
            remote_side=lambda: cls.id,
            backref="children",
            foreign_keys=lambda: cls.parent_id,
            post_update=True,  # Add post_update to avoid circular dependency issues
        )
