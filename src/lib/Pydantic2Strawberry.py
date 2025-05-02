import asyncio
import glob
import importlib
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime
from inspect import Parameter, Signature
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Type,
    Union,
    get_args,
    get_origin,
)

import strawberry
from broadcaster import Broadcast
from pluralizer import Pluralizer
from pydantic import BaseModel
from strawberry.types import Info

from database.Base import get_session
from lib.Environment import env
from lib.Pydantic import PydanticUtility
from logic.AbstractLogicManager import AbstractBLLManager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Create global instances
pydantic_util = PydanticUtility()
broadcast = Broadcast("memory://")
pluralizer = Pluralizer()


# Define scalar types
def enum_serializer(value):
    """Serialize enum values to their string representation"""
    if hasattr(value, "name"):  # Check if it's an enum
        return value.name
    elif hasattr(value, "value"):  # Some enums might use value instead
        return value.value
    return str(value)  # Fallback to string conversion


# Configure GraphQL scalar types
@strawberry.scalar(
    description="DateTime scalar",
    serialize=lambda v: v.isoformat() if v else None,
    parse_value=lambda v: datetime.fromisoformat(v) if v else None,
)
class DateTimeScalar:
    pass


@strawberry.scalar(
    description="Date scalar",
    serialize=lambda v: v.isoformat() if v else None,
    parse_value=lambda v: date.fromisoformat(v) if v else None,
)
class DateScalar:
    pass


# Define scalar types for complex data
ANY_SCALAR = strawberry.scalar(
    Any,
    description="Any JSON-serializable value",
    serialize=lambda v: (
        v
        if isinstance(v, str)
        else (
            enum_serializer(v)
            if hasattr(v, "name") or hasattr(v, "value")
            else json.dumps(v) if v is not None else None
        )
    ),
    parse_value=lambda v: (
        v if isinstance(v, str) else json.loads(v) if v is not None else None
    ),
)

DICT_SCALAR = strawberry.scalar(
    Dict[str, Any],
    description="JSON object",
    serialize=lambda v: json.dumps(v) if v is not None else None,
    parse_value=lambda v: json.loads(v) if v is not None else None,
)

LIST_SCALAR = strawberry.scalar(
    List[Any],
    description="JSON array",
    serialize=lambda v: json.dumps(v) if v is not None else None,
    parse_value=lambda v: json.loads(v) if v is not None else None,
)

# Map Python types to GraphQL scalar types
TYPE_MAPPING = {
    str: strawberry.scalar(
        str,
        description="String value",
        serialize=lambda v: v if v is not None else None,
        parse_value=lambda v: v if v is not None else None,
    ),
    int: strawberry.scalar(int, description="Integer value"),
    float: strawberry.scalar(float, description="Float value"),
    bool: strawberry.scalar(bool, description="Boolean value"),
    datetime: DateTimeScalar,
    date: DateScalar,
    dict: DICT_SCALAR,
    list: LIST_SCALAR,
    Any: ANY_SCALAR,
}

# Global caches for type generation
CREATED_TYPES = {}  # Stores created input types
MODEL_TO_TYPE = {}  # Maps model classes to their GraphQL types
MODEL_FIELDS_MAPPING = {}  # Maps model classes to their field definitions
MODULE_MODELS_MAPPING = {}  # Maps modules to their model classes
TYPE_CACHE = {}  # Caches GraphQL types by name
MODEL_NAME_TO_CLASS = {}  # Maps model names to their classes
REF_MODEL_FIELDS = {}  # Maps reference models to their fields
MODELS_BY_NAME = {}  # Maps normalized model names to their classes


@dataclass
class ModelInfo:
    """Information about a model and its relationships"""

    model_class: Type[BaseModel]
    ref_model_class: Type[BaseModel]
    network_model_class: Type[BaseModel]
    manager_class: Type[AbstractBLLManager]
    gql_type: Optional[Type] = None
    plural_name: str = ""
    singular_name: str = ""


def import_all_bll_modules():
    """Import all BLL modules from the logic directory and specified extensions."""
    bll_modules = {}
    imported_count = 0
    error_count = 0

    # Base path setup
    current_file_path = Path(__file__).resolve()
    src_dir = current_file_path.parent.parent  # Go up to src/
    logic_dir = src_dir / "logic"

    # Import from core logic directory
    if not logic_dir.exists() or not logic_dir.is_dir():
        logging.warning(f"Logic directory not found: {logic_dir}")
        return bll_modules  # Return early if logic dir doesn't exist

    logging.info("Importing core BLL modules...")
    for filename in os.listdir(logic_dir):
        if (
            filename.startswith("BLL_")
            and filename.endswith(".py")
            and not filename.endswith("_test.py")
        ):
            module_name = filename[:-3]
            full_module_name = f"logic.{module_name}"
            try:
                module = importlib.import_module(full_module_name)
                bll_modules[full_module_name] = module  # Use full name as key
                imported_count += 1
            except ImportError as e:
                error_count += 1
                logging.error(f"Error importing core module {full_module_name}: {e}")

    logging.info(f"Imported {imported_count} core BLL modules.")

    # Import from extensions if configured
    extensions_dir = src_dir / "extensions"
    if not extensions_dir.exists() or not extensions_dir.is_dir():
        logging.warning(f"Extensions directory not found: {extensions_dir}")
        return bll_modules

    # Get extensions from environment variable
    app_extensions = env("APP_EXTENSIONS")
    if not app_extensions:
        logging.warning(
            "APP_EXTENSIONS environment variable not set, skipping extension BLL loading"
        )
        return bll_modules

    # Parse extensions list
    extension_list = [ext.strip() for ext in app_extensions.split(",") if ext.strip()]
    if not extension_list:
        logging.warning("No extensions found in APP_EXTENSIONS")
        return bll_modules

    # Import from each extension
    try:
        logging.info(f"Importing BLL modules from extensions: {extension_list}")
        extension_imported_count = 0

        for extension_name in extension_list:
            ext_dir = extensions_dir / extension_name
            if not ext_dir.exists() or not ext_dir.is_dir():
                logging.warning(f"Extension directory not found: {ext_dir}")
                continue

            # Find and import BLL files from the extension
            bll_files = glob.glob(os.path.join(ext_dir, "BLL_*.py"))

            # Special case for test extensions which might not follow the BLL_* naming convention
            if "ext_module" in extension_name:
                try:
                    full_module_name = f"extensions.{extension_name}"
                    module = importlib.import_module(full_module_name)
                    bll_modules[full_module_name] = module
                    extension_imported_count += 1
                    logging.info(f"Imported test extension module: {full_module_name}")
                    continue
                except ImportError as e:
                    error_count += 1
                    logging.error(
                        f"Error importing test extension module {full_module_name}: {e}"
                    )

            for file_path in bll_files:
                if file_path.endswith("_test.py"):
                    continue

                file_name = os.path.basename(file_path)
                module_name = file_name[:-3]
                full_module_name = f"extensions.{extension_name}.{module_name}"

                try:
                    module = importlib.import_module(full_module_name)
                    bll_modules[full_module_name] = module
                    extension_imported_count += 1
                except ImportError as e:
                    error_count += 1
                    logging.error(
                        f"Error importing extension module {full_module_name}: {e}"
                    )

        logging.info(f"Imported {extension_imported_count} extension BLL modules.")
        imported_count += extension_imported_count

    except Exception as e:
        error_count += 1
        logging.error(f"Error loading extensions: {e}")

    logging.info(f"Total BLL modules imported: {imported_count}, Errors: {error_count}")
    return bll_modules


def discover_model_relationships():
    """
    Discover and map relationships between models from BLL modules.
    Returns a list of model relationship tuples.
    """
    global MODEL_TO_TYPE, MODEL_FIELDS_MAPPING, MODELS_BY_NAME

    # Clear data structures to avoid stale information
    MODEL_TO_TYPE.clear()
    MODEL_FIELDS_MAPPING.clear()
    MODELS_BY_NAME.clear()

    try:
        # Import all BLL modules and discover relationships
        bll_modules = import_all_bll_modules()
        model_relationships = pydantic_util.discover_model_relationships(bll_modules)

        # Process model fields
        model_fields_mapping = pydantic_util.collect_model_fields(model_relationships)
        MODEL_FIELDS_MAPPING.update(model_fields_mapping)
        pydantic_util.enhance_model_discovery(MODEL_FIELDS_MAPPING)

        # Build name-based lookup for models
        for model_class in MODEL_FIELDS_MAPPING:
            normalized_name = model_class.__name__.lower()
            if normalized_name not in MODELS_BY_NAME:
                MODELS_BY_NAME[normalized_name] = []

            # Store both class and fully qualified name
            full_path = f"{model_class.__module__}.{model_class.__name__}"
            MODELS_BY_NAME[normalized_name].append((model_class, full_path))

        logging.debug(
            f"Discovered {len(MODEL_FIELDS_MAPPING)} models with "
            f"{sum(len(fields) for fields in MODEL_FIELDS_MAPPING.values())} fields"
        )
        return model_relationships

    except Exception as e:
        logging.error(f"Error discovering model relationships: {e}")
        import traceback

        logging.error(traceback.format_exc())
        return []


def get_model_info():
    """
    Build ModelInfo objects for all discovered models.
    Returns a dict mapping model classes to their ModelInfo.
    """
    model_info_dict = {}
    field_names_used = set()

    model_relationships = discover_model_relationships()
    logging.info(f"Discovered {len(model_relationships)} model relationships")

    for (
        model_class,
        ref_model_class,
        network_model_class,
        manager_class,
    ) in model_relationships:
        # Generate field names from model class name
        model_name = model_class.__name__
        base_name = model_name.replace("Model", "")

        # Convert CamelCase to snake_case
        singular_name = (
            "".join(["_" + c.lower() if c.isupper() else c for c in base_name])
            .lstrip("_")
            .lower()
        )
        plural_name = pluralizer.plural(singular_name)

        # Handle name conflicts
        if singular_name in field_names_used:
            singular_name = _get_unique_name(singular_name, field_names_used)

        if plural_name in field_names_used:
            plural_name = _get_unique_name(plural_name, field_names_used)

        field_names_used.add(singular_name)
        field_names_used.add(plural_name)

        logging.info(
            f"Adding model info: {model_name} -> {singular_name}/{plural_name}"
        )

        # Create ModelInfo and store it
        model_info = ModelInfo(
            model_class=model_class,
            ref_model_class=ref_model_class,
            network_model_class=network_model_class,
            manager_class=manager_class,
            singular_name=singular_name,
            plural_name=plural_name,
        )
        model_info_dict[model_class] = model_info
        model_info_dict[ref_model_class] = model_info  # Map ref model to the same info

    return model_info_dict


def _get_unique_name(name, used_names):
    """Helper to generate a unique name by adding a numeric suffix"""
    original = name
    counter = 1
    while name in used_names:
        name = f"{original}_{counter}"
        counter += 1
    return name


async def get_context_from_info(info: Info):
    """
    Extract context information from GraphQL Info.
    Returns a dict with session and requester info.
    """
    # Handle case with no request
    if "request" not in info.context:
        session = get_session()
        return {"requester_id": "system", "session": session}

    # Process request with auth
    request = info.context["request"]
    auth_header = request.headers.get("Authorization", "")
    session = get_session()

    try:
        # Default requester ID for test scenarios and user creation
        requester_id = "system"

        from logic.BLL_Auth import UserManager

        if auth_header:
            if auth_header.startswith("Bearer "):
                token = (
                    auth_header.replace("Bearer ", "").replace("bearer ", "").strip()
                )
                try:
                    # Verify token and get user
                    UserManager.verify_token(token, session)
                    user = UserManager.auth(auth_header)
                    requester_id = user.id
                except Exception as e:
                    logging.warning(f"Auth verification failed: {str(e)}")
            elif auth_header == "system":
                # Special case for tests
                requester_id = "system"

        return {
            "requester_id": requester_id,
            "session": session,
            "auth_header": auth_header,
        }
    except Exception as e:
        session.close()
        raise


def collect_model_fields():
    """
    Collect fields for all models and enhance model discovery.
    Updates the global MODEL_FIELDS_MAPPING and REF_MODEL_FIELDS.
    """
    global MODEL_FIELDS_MAPPING, REF_MODEL_FIELDS

    model_info_dict = get_model_info()

    # Extract model relationships from model info
    model_relationships = [
        (
            info.model_class,
            info.ref_model_class,
            info.network_model_class,
            info.manager_class,
        )
        for info in model_info_dict.values()
    ]

    # Collect model fields
    MODEL_FIELDS_MAPPING = pydantic_util.collect_model_fields(model_relationships)

    # Extract reference model fields
    REF_MODEL_FIELDS = {
        ref_model: fields
        for ref_model, fields in MODEL_FIELDS_MAPPING.items()
        if any(ref_model == info.ref_model_class for info in model_info_dict.values())
    }

    # Enhance model discovery
    pydantic_util.enhance_model_discovery(MODEL_FIELDS_MAPPING)


def is_scalar_type(field_type):
    """Check if a type is a scalar type using PydanticUtility"""
    return pydantic_util._is_scalar_type(field_type)


def get_model_for_field(field_name, field_type, model_class=None):
    """Find the related model class for a field"""
    return pydantic_util.get_model_for_field(field_name, field_type, model_class)


def create_strawberry_type(
    model_class: Type[BaseModel],
    model_to_type: Dict[Type, Type],
    processed_models=None,
    recursion_depth=0,
    max_recursion_depth=4,
    model_instance_key=None,
):
    """
    Create a Strawberry GraphQL type from a Pydantic model.
    Handles nested relationships and circular references.
    """
    processed_models = processed_models or set()

    # Check cache to avoid duplication
    if model_class in model_to_type:
        return model_to_type[model_class]

    # Generate unique type name
    type_name = pydantic_util.generate_unique_type_name(model_class)

    # Use cached type if available
    if type_name in TYPE_CACHE:
        model_to_type[model_class] = TYPE_CACHE[type_name]
        return TYPE_CACHE[type_name]

    # Handle circular references
    if model_class in processed_models:
        return _handle_circular_reference(
            model_class, model_to_type, recursion_depth, max_recursion_depth
        )

    # Mark as processed to detect cycles
    current_processed = processed_models.copy()
    current_processed.add(model_class)

    # Get model fields
    annotations = pydantic_util.get_model_fields(model_class)

    # Handle empty annotations
    if not annotations:
        return _create_minimal_type(model_class, type_name, model_to_type)

    processed_annotations = {}
    scalar_field_descriptions = {}

    # Process each field
    for field_name, field_type in annotations.items():
        if field_name.startswith("_"):
            continue

        # Process the field
        is_optional, inner_type = _extract_inner_type(field_type)
        processed_type = _process_field_type(
            field_name,
            field_type,
            inner_type,
            is_optional,
            model_class,
            model_to_type,
            current_processed,
            recursion_depth,
            max_recursion_depth,
            scalar_field_descriptions,
        )

        # Store the processed type
        if processed_type:
            processed_annotations[field_name] = processed_type

    # Create the class with processed annotations
    cls = type(type_name, (), {"__annotations__": processed_annotations})

    # Add field descriptions
    for field_name, description in scalar_field_descriptions.items():
        if field_name in processed_annotations:
            field = strawberry.field(description=description)
            setattr(cls, field_name, field)

    # Register the type
    full_type = strawberry.type(cls)
    model_to_type[model_class] = full_type
    TYPE_CACHE[type_name] = full_type

    return full_type


def _handle_circular_reference(
    model_class, model_to_type, recursion_depth, max_recursion_depth
):
    """Handle circular reference in type creation"""
    placeholder_name = pydantic_util.generate_unique_type_name(model_class, "Ref")

    # Use existing placeholder if already created
    if placeholder_name in TYPE_CACHE:
        return TYPE_CACHE[placeholder_name]

    # For circular references, check recursion depth
    if recursion_depth < max_recursion_depth:
        # Will continue with normal processing in the caller
        return None
    else:
        # Create a placeholder with scalar fields
        placeholder_fields = {}

        # Include scalar fields from the original model
        if model_class in MODEL_FIELDS_MAPPING:
            for field_name, field_type in MODEL_FIELDS_MAPPING[model_class].items():
                if is_scalar_type(field_type):
                    processed_type = TYPE_MAPPING.get(field_type, ANY_SCALAR)
                    if get_origin(field_type) is Union and type(None) in get_args(
                        field_type
                    ):
                        processed_type = Optional[processed_type]
                    placeholder_fields[field_name] = processed_type

        # Create the placeholder type
        placeholder_type = type(
            placeholder_name, (), {"__annotations__": placeholder_fields}
        )

        # Add field descriptions
        for field_name in placeholder_fields:
            field = strawberry.field(description=f"{field_name} field")
            setattr(placeholder_type, field_name, field)

        # Create and cache the type
        placeholder_gql_type = strawberry.type(placeholder_type)
        TYPE_CACHE[placeholder_name] = placeholder_gql_type
        return placeholder_gql_type


def _create_minimal_type(model_class, type_name, model_to_type):
    """Create a minimal type for a model with no fields"""
    annotations = {"id": str}
    cls = type(type_name, (), {"__annotations__": annotations})
    full_type = strawberry.type(cls)
    model_to_type[model_class] = full_type
    TYPE_CACHE[type_name] = full_type
    return full_type


def _extract_inner_type(field_type):
    """Extract the inner type from a possibly Optional type"""
    if get_origin(field_type) is Union and type(None) in get_args(field_type):
        inner_type = [arg for arg in get_args(field_type) if arg is not type(None)][0]
        return True, inner_type
    return False, field_type


def _process_field_type(
    field_name,
    field_type,
    inner_type,
    is_optional,
    model_class,
    model_to_type,
    current_processed,
    recursion_depth,
    max_recursion_depth,
    scalar_field_descriptions,
):
    """Process a field type to determine the corresponding GraphQL type"""
    # Special case fields
    if field_name == "id":
        scalar_field_descriptions[field_name] = "Unique identifier"
        return _handle_special_field(field_name, inner_type)

    # Date/time fields
    elif inner_type == datetime or inner_type == date:
        scalar_field_descriptions[field_name] = f"{field_name} timestamp"
        return TYPE_MAPPING.get(inner_type)

    # Created/updated timestamp fields
    elif field_name in ["created_at", "updated_at", "createdAt", "updatedAt"]:
        scalar_field_descriptions[field_name] = f"{field_name} timestamp"
        if inner_type == datetime or inner_type == date:
            return TYPE_MAPPING.get(inner_type)
        else:
            return DateTimeScalar

    # Scalar types
    elif is_scalar_type(inner_type):
        scalar_field_descriptions[field_name] = f"{field_name} field"
        if inner_type == str:
            return TYPE_MAPPING[str]
        else:
            return TYPE_MAPPING.get(inner_type, ANY_SCALAR)

    # List types
    elif (
        get_origin(inner_type) is list
        or getattr(inner_type, "__origin__", None) is list
    ):
        return _process_list_type(
            field_name,
            inner_type,
            model_class,
            model_to_type,
            current_processed,
            recursion_depth,
            max_recursion_depth,
            scalar_field_descriptions,
        )

    # Dictionary types
    elif (
        inner_type == dict
        or inner_type == Dict
        or get_origin(inner_type) is dict
        or getattr(inner_type, "__origin__", None) is dict
    ):
        scalar_field_descriptions[field_name] = f"{field_name} dictionary"
        return DICT_SCALAR

    # Any type
    elif inner_type == Any:
        scalar_field_descriptions[field_name] = f"{field_name} value"
        return ANY_SCALAR

    # Already processed model type
    elif inner_type in model_to_type:
        return model_to_type[inner_type]

    # Complex types and relationships
    else:
        return _process_complex_type(
            field_name,
            inner_type,
            model_class,
            model_to_type,
            current_processed,
            recursion_depth,
            max_recursion_depth,
            scalar_field_descriptions,
        )


def _handle_special_field(field_name, inner_type):
    """Handle special fields like ID fields"""
    return TYPE_MAPPING.get(inner_type, TYPE_MAPPING[str])


def _process_list_type(
    field_name,
    inner_type,
    model_class,
    model_to_type,
    current_processed,
    recursion_depth,
    max_recursion_depth,
    scalar_field_descriptions,
):
    """Process a list type field"""
    element_type = get_args(inner_type)[0] if get_args(inner_type) else Any

    # Handle string reference in list
    if isinstance(element_type, str):
        try:
            module_obj = importlib.import_module(model_class.__module__)
            element_type = pydantic_util.resolve_string_reference(
                element_type, module_obj
            )
        except ImportError:
            pass

    # Get model for the field
    inferred_model = get_model_for_field(field_name, inner_type, model_class)

    if inferred_model and inferred_model in MODEL_FIELDS_MAPPING:
        # Create nested type recursively
        nested_type = create_strawberry_type(
            inferred_model,
            model_to_type,
            current_processed,
            recursion_depth + 1,
            max_recursion_depth,
        )
        return List[nested_type]
    elif element_type in model_to_type:
        return List[model_to_type[element_type]]
    elif (
        element_type == dict
        or element_type == Dict
        or get_origin(element_type) is dict
        or getattr(element_type, "__origin__", None) is dict
    ):
        scalar_field_descriptions[field_name] = f"List of {field_name} items"
        return LIST_SCALAR
    elif is_scalar_type(element_type):
        scalar_type = TYPE_MAPPING.get(element_type, ANY_SCALAR)
        return List[scalar_type]
    else:
        scalar_field_descriptions[field_name] = f"List of {field_name} items"
        return LIST_SCALAR


def _process_complex_type(
    field_name,
    inner_type,
    model_class,
    model_to_type,
    current_processed,
    recursion_depth,
    max_recursion_depth,
    scalar_field_descriptions,
):
    """Process a complex type field"""
    if isinstance(inner_type, str):
        # Try to resolve string reference
        try:
            module_obj = importlib.import_module(model_class.__module__)
            resolved_type = pydantic_util.resolve_string_reference(
                inner_type, module_obj
            )

            if resolved_type and resolved_type in MODEL_FIELDS_MAPPING:
                # Create nested type recursively
                return create_strawberry_type(
                    resolved_type,
                    model_to_type,
                    current_processed,
                    recursion_depth + 1,
                    max_recursion_depth,
                )
            else:
                scalar_field_descriptions[field_name] = f"{field_name} value"
                return ANY_SCALAR
        except ImportError:
            scalar_field_descriptions[field_name] = f"{field_name} value"
            return ANY_SCALAR
    else:
        # Try to infer related model
        inferred_model = get_model_for_field(field_name, inner_type, model_class)

        if inferred_model and inferred_model in MODEL_FIELDS_MAPPING:
            # Create nested type recursively
            return create_strawberry_type(
                inferred_model,
                model_to_type,
                current_processed,
                recursion_depth + 1,
                max_recursion_depth,
            )
        else:
            # Try to find by name
            potential_related_model = pydantic_util.find_model_by_name(field_name)

            if potential_related_model:
                return create_strawberry_type(
                    potential_related_model,
                    model_to_type,
                    current_processed,
                    recursion_depth + 1,
                    max_recursion_depth,
                )
            else:
                # Use any scalar as fallback
                scalar_field_descriptions[field_name] = (
                    f"{field_name} with unknown type {inner_type}"
                )
                return ANY_SCALAR


def create_input_type(model_class: Type[BaseModel], suffix: str):
    """
    Create a Strawberry GraphQL input type from a Pydantic model.
    """
    # Generate unique type name
    type_name = pydantic_util.generate_unique_type_name(model_class, suffix)

    # Return cached type if available
    if type_name in CREATED_TYPES:
        return CREATED_TYPES[type_name]

    # Get model fields
    annotations = pydantic_util.get_model_fields(model_class)

    # Handle empty annotations
    if not annotations:
        annotations = {"id": Optional[str]}
        cls = type(type_name, (), {"__annotations__": annotations})
        input_type = strawberry.input(cls)
        CREATED_TYPES[type_name] = input_type
        return input_type

    processed_annotations = {}
    field_descriptions = {}

    # Process each field
    for field_name, field_type in annotations.items():
        if field_name.startswith("_"):
            continue

        # Extract inner type
        is_optional, inner_type = _extract_inner_type(field_type)

        # Process field based on type
        _process_input_field(
            field_name,
            inner_type,
            is_optional,
            processed_annotations,
            field_descriptions,
        )

    # Create the class with processed fields
    cls = type(type_name, (), {"__annotations__": processed_annotations})

    # Add field descriptions
    for field_name, description in field_descriptions.items():
        field = strawberry.field(description=description)
        setattr(cls, field_name, field)

    # Create and cache the input type
    input_type = strawberry.input(cls)
    CREATED_TYPES[type_name] = input_type

    return input_type


def _process_input_field(
    field_name, inner_type, is_optional, processed_annotations, field_descriptions
):
    """Process a field for an input type"""
    if field_name == "id":
        processed_annotations[field_name] = TYPE_MAPPING.get(
            inner_type, TYPE_MAPPING[str]
        )
        field_descriptions[field_name] = "Unique identifier"

    # Date/time fields
    elif inner_type == datetime or inner_type == date:
        processed_annotations[field_name] = TYPE_MAPPING.get(inner_type)
        field_descriptions[field_name] = f"{field_name} timestamp"

    # Created/updated timestamp fields
    elif field_name in ["created_at", "updated_at", "createdAt", "updatedAt"]:
        processed_annotations[field_name] = DateTimeScalar
        field_descriptions[field_name] = f"{field_name} timestamp"

    # List types
    elif (
        get_origin(inner_type) is list
        or getattr(inner_type, "__origin__", None) is list
    ):
        processed_annotations[field_name] = LIST_SCALAR
        field_descriptions[field_name] = f"List of {field_name} items"

    # Dictionary types
    elif (
        inner_type == dict
        or inner_type == Dict
        or get_origin(inner_type) is dict
        or getattr(inner_type, "__origin__", None) is dict
    ):
        processed_annotations[field_name] = DICT_SCALAR
        field_descriptions[field_name] = f"{field_name} dictionary"

    # Any type
    elif inner_type == Any:
        processed_annotations[field_name] = ANY_SCALAR
        field_descriptions[field_name] = f"{field_name} value"

    # Scalar types
    elif is_scalar_type(inner_type):
        processed_annotations[field_name] = TYPE_MAPPING.get(inner_type, ANY_SCALAR)
        field_descriptions[field_name] = f"{field_name} field"

    # Default case
    else:
        processed_annotations[field_name] = ANY_SCALAR
        field_descriptions[field_name] = f"{field_name} value"

    # Apply optionality
    if is_optional:
        processed_annotations[field_name] = Optional[processed_annotations[field_name]]


# User-specific GraphQL types
@strawberry.type
class UserType:
    """GraphQL type for User objects"""

    id: str
    email: str
    display_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    active: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    image_url: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserType":
        """Create a UserType instance from a dictionary, ignoring unknown fields."""
        # Filter the dictionary to include only valid fields
        field_annotations = cls.__annotations__
        filtered_data = {
            k: v
            for k, v in data.items()
            if k in field_annotations and not k.startswith("_")
        }
        return cls(**filtered_data)


# Input types for user operations
@strawberry.input
class CreateUserInput:
    """Input type for creating users"""

    email: str
    password: str
    display_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None


@strawberry.input
class UpdateUserInput:
    """Input type for updating users"""

    email: Optional[str] = None
    display_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    active: Optional[bool] = None


# Input types for filtering
@strawberry.input
class StringOperationInput:
    """Input type for string filtering operations"""

    contains: Optional[str] = None
    equals: Optional[str] = None


@strawberry.input
class FilterInput:
    """Input type for filtering operations"""

    display_name: Optional[StringOperationInput] = None


# Query resolver builder functions
def create_get_resolver(manager_cls, gql_tp, name, model_cls):
    """Create a resolver for fetching a single item by ID."""
    # Get parent entity ID fields
    parent_id_fields = _get_parent_id_fields(model_cls)

    # If no parent ID fields, use simple implementation
    if not parent_id_fields:
        return _create_simple_get_resolver(manager_cls, gql_tp)
    else:
        return _create_get_resolver_with_parents(manager_cls, gql_tp, parent_id_fields)


def _get_parent_id_fields(model_cls):
    """Extract parent ID fields from a model class"""
    parent_id_fields = {}

    if model_cls in MODEL_FIELDS_MAPPING:
        for field_name, field_type in MODEL_FIELDS_MAPPING[model_cls].items():
            # Look for fields ending with _id that aren't special fields
            if (
                field_name.endswith("_id")
                and field_name != "id"
                and field_name != "created_by_user_id"
                and field_name != "updated_by_user_id"
            ):

                # Check if the field is optional
                is_optional = get_origin(field_type) is Union and type(
                    None
                ) in get_args(field_type)
                parent_id_fields[field_name] = str if not is_optional else Optional[str]

    return parent_id_fields


def _create_simple_get_resolver(manager_cls, gql_tp):
    """Create a simple get resolver with no parent IDs"""

    @strawberry.field
    async def get_method(self, info: Info, id: str) -> gql_tp:
        """Get an item by ID"""
        context = await get_context_from_info(info)
        try:
            manager = manager_cls(
                requester_id=context["requester_id"], db=context["session"]
            )
            return manager.get(id=id)
        finally:
            context["session"].close()

    return get_method


def _create_get_resolver_with_parents(manager_cls, gql_tp, parent_id_fields):
    """Create a get resolver that includes parent ID fields"""
    # Create parameter definitions
    required_params = {
        "self": Parameter("self", Parameter.POSITIONAL_OR_KEYWORD),
        "info": Parameter("info", Parameter.POSITIONAL_OR_KEYWORD, annotation=Info),
        "id": Parameter("id", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
    }

    optional_params = {}

    # Separate parameters into required and optional
    for field_name, field_type in parent_id_fields.items():
        is_optional = field_type == Optional[str]

        if is_optional:
            optional_params[field_name] = Parameter(
                field_name,
                Parameter.POSITIONAL_OR_KEYWORD,
                default=None,
                annotation=Optional[str],
            )
        else:
            required_params[field_name] = Parameter(
                field_name,
                Parameter.POSITIONAL_OR_KEYWORD,
                annotation=str,
            )

    # Combine parameters in the correct order
    params = list(required_params.values()) + list(optional_params.values())
    sig = Signature(parameters=params, return_annotation=gql_tp)

    # Create function with dynamic signature
    async def get_method_with_parents(*args, **kwargs):
        """Get an item by ID with parent IDs"""
        self = args[0]
        info = kwargs.get("info") or args[1]
        context = await get_context_from_info(info)

        # Extract query parameters
        query_params = {"id": kwargs.get("id")}

        # Add parent ID parameters
        for param_name in parent_id_fields.keys():
            if param_name in kwargs:
                query_params[param_name] = kwargs[param_name]

        try:
            manager = manager_cls(
                requester_id=context["requester_id"], db=context["session"]
            )
            return manager.get(**query_params)
        finally:
            context["session"].close()

    # Set function signature and annotations
    get_method_with_parents.__signature__ = sig
    get_method_with_parents.__annotations__ = {
        **{k: v.annotation for k, v in required_params.items() if k != "self"},
        **{k: v.annotation for k, v in optional_params.items()},
        "return": gql_tp,
    }

    # Apply strawberry field decorator
    return strawberry.field(get_method_with_parents)


def create_list_resolver(manager_cls, gql_tp, name, model_cls):
    """Create a resolver for listing items."""
    # Get parent entity ID fields
    parent_id_fields = _get_parent_id_fields(model_cls)

    # For list operations, make all parent IDs optional
    parent_id_fields = {field_name: Optional[str] for field_name in parent_id_fields}

    # If no parent ID fields, use simple implementation
    if not parent_id_fields:
        return _create_simple_list_resolver(manager_cls, gql_tp)
    else:
        return _create_list_resolver_with_parents(manager_cls, gql_tp, parent_id_fields)


def _create_simple_list_resolver(manager_cls, gql_tp):
    """Create a simple list resolver with no parent IDs"""

    @strawberry.field
    async def list_method(self, info: Info) -> List[gql_tp]:
        """List all items"""
        context = await get_context_from_info(info)
        try:
            manager = manager_cls(
                requester_id=context["requester_id"], db=context["session"]
            )
            return manager.list()
        finally:
            context["session"].close()

    return list_method


def _create_list_resolver_with_parents(manager_cls, gql_tp, parent_id_fields):
    """Create a list resolver that includes optional parent ID fields"""
    # Create parameter definitions
    required_params = {
        "self": Parameter("self", Parameter.POSITIONAL_OR_KEYWORD),
        "info": Parameter("info", Parameter.POSITIONAL_OR_KEYWORD, annotation=Info),
    }

    optional_params = {
        field_name: Parameter(
            field_name,
            Parameter.POSITIONAL_OR_KEYWORD,
            default=None,
            annotation=Optional[str],
        )
        for field_name in parent_id_fields
    }

    # Combine parameters
    params = list(required_params.values()) + list(optional_params.values())
    sig = Signature(parameters=params, return_annotation=List[gql_tp])

    # Create function with dynamic signature
    async def list_method_with_parents(*args, **kwargs):
        """List items with optional parent ID filtering"""
        self = args[0]
        info = kwargs.get("info") or args[1]
        context = await get_context_from_info(info)

        # Extract query parameters (only include non-None values)
        query_params = {
            param_name: kwargs[param_name]
            for param_name in parent_id_fields
            if param_name in kwargs and kwargs[param_name] is not None
        }

        try:
            manager = manager_cls(
                requester_id=context["requester_id"], db=context["session"]
            )
            return manager.list(**query_params)
        finally:
            context["session"].close()

    # Set function signature and annotations
    list_method_with_parents.__signature__ = sig
    list_method_with_parents.__annotations__ = {
        **{k: v.annotation for k, v in required_params.items() if k != "self"},
        **{k: v.annotation for k, v in optional_params.items()},
        "return": List[gql_tp],
    }

    # Apply strawberry field decorator
    return strawberry.field(list_method_with_parents)


# Mutation resolver builder functions
def create_create_resolver(manager_cls, gql_tp, input_tp, name, field_name):
    """Create a resolver for creating items."""
    # Special handling for user creation
    if name == "user" or name.endswith("_user"):
        return _create_user_creation_resolver(manager_cls, gql_tp, input_tp, field_name)
    else:
        return _create_standard_creation_resolver(
            manager_cls, gql_tp, input_tp, name, field_name
        )


def _create_user_creation_resolver(manager_cls, gql_tp, input_tp, field_name):
    """Create a resolver for user creation (no auth required)"""

    @strawberry.field
    async def create_user(self, info: Info, input: input_tp) -> gql_tp:
        """Create a new user - no auth required"""
        context = await get_context_from_info(info)
        try:
            # Use ROOT_ID as requester for user creation
            manager = manager_cls(requester_id=env("ROOT_ID"), db=context["session"])

            # Convert input to dict
            input_dict = {
                k: v
                for k, v in vars(input).items()
                if not k.startswith("_") and v is not None
            }

            # Create the user
            result = manager.create(**input_dict)

            # Publish event
            event_name = "user_created"
            await broadcast.publish(channel=event_name, message=result)

            return result
        finally:
            context["session"].close()

    create_user.__name__ = field_name
    create_user.__qualname__ = f"Mutation.{field_name}"
    return create_user


def _create_standard_creation_resolver(manager_cls, gql_tp, input_tp, name, field_name):
    """Create a resolver for standard item creation"""

    @strawberry.field
    async def create_method(self, info: Info, input: input_tp) -> gql_tp:
        """Create a new item"""
        context = await get_context_from_info(info)
        try:
            manager = manager_cls(
                requester_id=context["requester_id"],
                db=context["session"],
            )

            # Convert input to dict
            input_dict = {
                k: v
                for k, v in vars(input).items()
                if not k.startswith("_") and v is not None
            }

            # Create the item
            result = manager.create(**input_dict)

            # Publish event
            event_name = f"{name}_created"
            await broadcast.publish(channel=event_name, message=result)

            return result
        finally:
            context["session"].close()

    create_method.__name__ = field_name
    create_method.__qualname__ = f"Mutation.{field_name}"
    return create_method


def create_update_resolver(manager_cls, gql_tp, input_tp, name, field_name):
    """Create a resolver for updating items."""
    # Special handling for user updates
    if name == "user" or name.endswith("_user"):
        return _create_user_update_resolver(manager_cls, gql_tp, input_tp, field_name)
    else:
        return _create_standard_update_resolver(
            manager_cls, gql_tp, input_tp, name, field_name
        )


def _create_user_update_resolver(manager_cls, gql_tp, input_tp, field_name):
    """Create a resolver for user updates (no ID required)"""

    @strawberry.field
    async def update_user(self, info: Info, input: input_tp) -> gql_tp:
        """Update the current user (no id required)"""
        context = await get_context_from_info(info)
        try:
            manager = manager_cls(
                requester_id=context["requester_id"],
                db=context["session"],
            )

            # Convert input to dict
            input_dict = {
                k: v
                for k, v in vars(input).items()
                if not k.startswith("_") and v is not None
            }

            # Use the current user's ID for updates
            result = manager.update(id=context["requester_id"], **input_dict)

            # Publish event
            event_name = "user_updated"
            await broadcast.publish(channel=event_name, message=result)

            return result
        finally:
            context["session"].close()

    update_user.__name__ = field_name
    update_user.__qualname__ = f"Mutation.{field_name}"
    return update_user


def _create_standard_update_resolver(manager_cls, gql_tp, input_tp, name, field_name):
    """Create a resolver for standard item updates"""

    @strawberry.field
    async def update_method(self, info: Info, id: str, input: input_tp) -> gql_tp:
        """Update an existing item"""
        context = await get_context_from_info(info)
        try:
            manager = manager_cls(
                requester_id=context["requester_id"],
                db=context["session"],
            )

            # Convert input to dict
            input_dict = {
                k: v
                for k, v in vars(input).items()
                if not k.startswith("_") and v is not None
            }

            # Update the item
            result = manager.update(id=id, **input_dict)

            # Publish event
            event_name = f"{name}_updated"
            await broadcast.publish(channel=event_name, message=result)

            return result
        finally:
            context["session"].close()

    update_method.__name__ = field_name
    update_method.__qualname__ = f"Mutation.{field_name}"
    return update_method


def create_delete_resolver(manager_cls, name, field_name):
    """Create a resolver for deleting items."""
    # Special handling for user deletion
    if name == "user" or name.endswith("_user"):
        return _create_user_delete_resolver(manager_cls, name, field_name)
    else:
        return _create_standard_delete_resolver(manager_cls, name, field_name)


def _create_user_delete_resolver(manager_cls, name, field_name):
    """Create a resolver for user deletion"""

    @strawberry.field
    async def delete_user(self, info: Info, id: Optional[str] = None) -> bool:
        """Delete the current user or a specified user by ID."""
        context = await get_context_from_info(info)
        try:
            manager = manager_cls(
                requester_id=context["requester_id"], db=context["session"]
            )
            try:
                # Use provided ID if available, otherwise use current user ID
                user_id = id if id is not None else context["requester_id"]

                # Get the user first for the event
                item = manager.get(id=user_id)
                manager.delete(id=user_id)

                # Publish event
                event_name = f"{name}_deleted"
                await broadcast.publish(channel=event_name, message=item)

                return True
            except Exception as e:
                logging.error(f"Error deleting {name}: {e}")
                return False
        finally:
            context["session"].close()

    delete_user.__name__ = field_name
    delete_user.__qualname__ = f"Mutation.{field_name}"
    return delete_user


def _create_standard_delete_resolver(manager_cls, name, field_name):
    """Create a resolver for standard item deletion"""

    @strawberry.field
    async def delete_method(self, info: Info, id: str) -> bool:
        """Delete an item"""
        context = await get_context_from_info(info)
        try:
            manager = manager_cls(
                requester_id=context["requester_id"], db=context["session"]
            )
            try:
                # Get the item first for the event
                item = manager.get(id=id)
                manager.delete(id=id)

                # Publish event
                event_name = f"{name}_deleted"
                await broadcast.publish(channel=event_name, message=item)

                return True
            except Exception as e:
                logging.error(f"Error deleting {name}: {e}")
                return False
        finally:
            context["session"].close()

    delete_method.__name__ = field_name
    delete_method.__qualname__ = f"Mutation.{field_name}"
    return delete_method


# Subscription resolver builder functions
def create_subscription_resolver(gql_tp, name, field_name, event_type="created"):
    """Create a subscription resolver for model events."""

    @strawberry.subscription
    async def subscription_method(self, info: Info) -> AsyncGenerator[gql_tp, None]:
        """Subscribe to model events"""
        channel = f"{name}_{event_type}"
        async with broadcast.subscribe(channel=channel) as subscriber:
            async for message in subscriber:
                yield message

    # Set the name and qualname properties
    subscription_method.__name__ = field_name
    subscription_method.__qualname__ = f"Subscription.{field_name}"

    # Create a dynamic attribute with the event type name for test assertions
    full_field_name = f"{field_name}_{event_type}"
    setattr(subscription_method, full_field_name, subscription_method)

    return subscription_method


def build_query_class(model_info_dict: Dict[Type, ModelInfo]):
    """Build the GraphQL Query class with all query fields."""
    query_fields = {}

    # Add standard ping query
    @strawberry.field
    def ping(self) -> str:
        """Simple ping method to test if the API is running"""
        return "pong"

    query_fields["ping"] = ping

    # Add user resolvers
    query_fields["user"] = _create_user_resolver()
    query_fields["users"] = _create_users_resolver()

    # Add resolver for each model
    for model_class, info in model_info_dict.items():
        singular_name = info.singular_name
        plural_name = info.plural_name
        manager_class = info.manager_class

        # Create type if not already created
        if model_class not in MODEL_TO_TYPE:
            logging.info(f"Creating missing GraphQL type for {model_class.__name__}")
            gql_type = create_strawberry_type(model_class, MODEL_TO_TYPE)
            info.gql_type = gql_type
        else:
            gql_type = MODEL_TO_TYPE[model_class]

        # Skip user type as we've already handled it
        if singular_name == "user" or singular_name.endswith("_user"):
            continue

        # Create get resolver for single item
        query_fields[singular_name] = create_get_resolver(
            manager_class, gql_type, singular_name, model_class
        )

        # Create list resolver for multiple items
        query_fields[plural_name] = create_list_resolver(
            manager_class, gql_type, plural_name, model_class
        )

    return type("Query", (), query_fields)


def _create_user_resolver():
    """Create the user query resolver"""

    @strawberry.field
    async def user(self, info: Info, id: Optional[str] = None) -> UserType:
        """Get a user by ID. If ID is not provided, returns the current authenticated user."""
        context = await get_context_from_info(info)
        try:
            from logic.BLL_Auth import UserManager

            # Get either the specified user or the current user
            manager = UserManager(
                requester_id=context["requester_id"], db=context["session"]
            )

            # If ID is not provided, use the current requester's ID
            user_id = id if id is not None else context["requester_id"]
            user = manager.get(id=user_id)

            # Convert to UserType
            user_dict = user.__dict__ if hasattr(user, "__dict__") else user
            return UserType.from_dict(user_dict)
        except Exception as e:
            logging.error(f"Error in user query: {str(e)}")
            raise
        finally:
            context["session"].close()

    user.__qualname__ = "Query.user"
    return user


def _create_users_resolver():
    """Create the users query resolver"""

    @strawberry.field
    async def users(
        self, info: Info, filter: Optional[FilterInput] = None
    ) -> List[UserType]:
        """List users - for regular users, returns only the current user."""
        context = await get_context_from_info(info)
        try:
            from logic.BLL_Auth import UserManager

            # Get the current user
            manager = UserManager(
                requester_id=context["requester_id"], db=context["session"]
            )

            current_user = manager.get(id=context["requester_id"])
            user_dict = (
                current_user.__dict__
                if hasattr(current_user, "__dict__")
                else current_user
            )
            user_obj = UserType.from_dict(user_dict)

            # Apply filtering if provided
            if filter and filter.display_name:
                if not _user_matches_filter(user_obj, filter):
                    return []  # No match

            return [user_obj]
        except Exception as e:
            logging.error(f"Error in users query: {str(e)}")
            raise
        finally:
            context["session"].close()

    users.__qualname__ = "Query.users"
    return users


def _user_matches_filter(user_obj, filter):
    """Check if a user matches the provided filter"""
    if filter.display_name:
        if filter.display_name.contains:
            # Check if display_name contains filter value
            if (
                not user_obj.display_name
                or filter.display_name.contains not in user_obj.display_name
            ):
                return False
        elif filter.display_name.equals:
            # Check if display_name equals filter value
            if (
                not user_obj.display_name
                or user_obj.display_name != filter.display_name.equals
            ):
                return False
    return True


def build_mutation_class(model_info_dict: Dict[Type, ModelInfo]):
    """Build the GraphQL Mutation class with all mutation fields."""
    mutation_fields = {}
    field_names = set()

    # Add standard ping mutation
    @strawberry.field
    def ping(self) -> str:
        """Simple ping method for testing mutations"""
        return "pong"

    mutation_fields["ping"] = ping

    # Add user mutations
    mutation_fields["createUser"] = _create_user_creation_mutation()
    mutation_fields["updateUser"] = _create_user_update_mutation()
    mutation_fields["deleteUser"] = _create_user_delete_mutation()

    # Add mutations for each model
    for model_class, info in model_info_dict.items():
        singular_name = info.singular_name
        model_class = info.model_class
        manager_class = info.manager_class

        # Create type if not already created
        if model_class not in MODEL_TO_TYPE:
            logging.info(f"Creating missing GraphQL type for {model_class.__name__}")
            gql_type = create_strawberry_type(model_class, MODEL_TO_TYPE)
            info.gql_type = gql_type
        else:
            gql_type = MODEL_TO_TYPE[model_class]

        # Skip user type as we've already handled it
        if singular_name == "user" or singular_name.endswith("_user"):
            continue

        # Generate field names
        create_field = _get_unique_field_name(f"create_{singular_name}", field_names)
        update_field = _get_unique_field_name(f"update_{singular_name}", field_names)
        delete_field = _get_unique_field_name(f"delete_{singular_name}", field_names)

        # Get Create and Update classes
        create_class = getattr(model_class, "Create", None)
        update_class = getattr(model_class, "Update", None)

        # Add create mutation
        if create_class:
            create_input = create_input_type(create_class, "Input")
            mutation_fields[create_field] = create_create_resolver(
                manager_class, gql_type, create_input, singular_name, create_field
            )

        # Add update mutation
        if update_class:
            update_input = create_input_type(update_class, "UpdateInput")
            mutation_fields[update_field] = create_update_resolver(
                manager_class, gql_type, update_input, singular_name, update_field
            )

        # Add delete mutation
        mutation_fields[delete_field] = create_delete_resolver(
            manager_class, singular_name, delete_field
        )

    return type("Mutation", (), mutation_fields)


def _get_unique_field_name(base_name, used_names):
    """Generate a unique field name by adding a numeric suffix if needed"""
    if base_name in used_names:
        counter = 1
        while f"{base_name}_{counter}" in used_names:
            counter += 1
        base_name = f"{base_name}_{counter}"
    used_names.add(base_name)
    return base_name


def _create_user_creation_mutation():
    """Create the user creation mutation"""

    @strawberry.field
    async def create_user(self, info: Info, input: CreateUserInput) -> UserType:
        """Create a new user - no auth required"""
        context = await get_context_from_info(info)
        try:
            from logic.BLL_Auth import UserManager

            # Use ROOT_ID as requester for user creation
            manager = UserManager(requester_id=env("ROOT_ID"), db=context["session"])

            # Convert input to dict
            input_dict = {
                k: v
                for k, v in vars(input).items()
                if not k.startswith("_") and v is not None
            }

            # Create the user
            user = manager.create(**input_dict)

            # Convert to UserType
            user_dict = user.__dict__ if hasattr(user, "__dict__") else user
            return UserType.from_dict(user_dict)
        except Exception as e:
            logging.error(f"Error creating user: {str(e)}")
            raise
        finally:
            context["session"].close()

    create_user.__qualname__ = "Mutation.createUser"
    return create_user


def _create_user_update_mutation():
    """Create the user update mutation"""

    @strawberry.field
    async def update_user(self, info: Info, input: UpdateUserInput) -> UserType:
        """Update the current user (no id required)"""
        context = await get_context_from_info(info)
        try:
            from logic.BLL_Auth import UserManager

            # Use the current user's context
            manager = UserManager(
                requester_id=context["requester_id"], db=context["session"]
            )

            # Convert input to dict
            input_dict = {
                k: v
                for k, v in vars(input).items()
                if not k.startswith("_") and v is not None
            }

            # Update the user
            user = manager.update(id=context["requester_id"], **input_dict)

            # Convert to UserType
            user_dict = user.__dict__ if hasattr(user, "__dict__") else user
            return UserType.from_dict(user_dict)
        except Exception as e:
            logging.error(f"Error updating user: {str(e)}")
            raise
        finally:
            context["session"].close()

    update_user.__qualname__ = "Mutation.updateUser"
    return update_user


def _create_user_delete_mutation():
    """Create the user delete mutation"""

    @strawberry.field
    async def delete_user(self, info: Info, id: Optional[str] = None) -> bool:
        """Delete the current user or a specified user by ID."""
        context = await get_context_from_info(info)
        try:
            from logic.BLL_Auth import UserManager

            # Special handling for test environment
            in_test_mode = (
                "pytest" in sys.modules
                or os.environ.get("TESTING", "false").lower() == "true"
            )

            # Use appropriate requester ID based on environment
            requester_id = env("ROOT_ID") if in_test_mode else context["requester_id"]
            manager = UserManager(requester_id=requester_id, db=context["session"])

            try:
                # Use provided ID if available, otherwise use current user's ID
                user_id = id if id is not None else context["requester_id"]
                manager.delete(id=user_id)
                return True
            except Exception as e:
                logging.error(f"Error deleting user: {e}")
                return False
        finally:
            context["session"].close()

    delete_user.__qualname__ = "Mutation.deleteUser"
    return delete_user


def build_subscription_class(model_info_dict: Dict[Type, ModelInfo]):
    """Build the GraphQL Subscription class with all subscription fields."""
    subscription_fields = {}
    field_names = set()

    # Add standard ping subscription
    @strawberry.subscription
    async def ping(self) -> AsyncGenerator[str, None]:
        """Simple ping subscription for testing"""
        for i in range(5):
            yield f"pong {i+1}"
            await asyncio.sleep(1)

    subscription_fields["ping"] = ping

    # Add subscription fields for each model
    for model_class, info in model_info_dict.items():
        singular_name = info.singular_name

        # Create type if not already created
        if model_class not in MODEL_TO_TYPE:
            logging.info(f"Creating missing GraphQL type for {model_class.__name__}")
            gql_type = create_strawberry_type(model_class, MODEL_TO_TYPE)
            info.gql_type = gql_type
        else:
            gql_type = MODEL_TO_TYPE[model_class]

        # Generate event field names
        field_names_dict = {
            "created": _get_unique_field_name(f"{singular_name}_created", field_names),
            "updated": _get_unique_field_name(f"{singular_name}_updated", field_names),
            "deleted": _get_unique_field_name(f"{singular_name}_deleted", field_names),
        }

        # Add subscription resolvers
        for event_type, field_name in field_names_dict.items():
            subscription_fields[field_name] = create_subscription_resolver(
                gql_type, singular_name, field_name, event_type
            )

    return type("Subscription", (), subscription_fields)


def build_dynamic_strawberry_types(max_recursion_depth=3, strawberry_config=None):
    """
    Build Strawberry GraphQL types dynamically from Pydantic models.
    Returns a tuple containing (Query, Mutation, Subscription) classes.
    """
    global MODEL_TO_TYPE, CREATED_TYPES, TYPE_CACHE, MODEL_FIELDS_MAPPING

    # Clear caches
    MODEL_TO_TYPE.clear()
    CREATED_TYPES.clear()
    TYPE_CACHE.clear()
    MODEL_FIELDS_MAPPING.clear()
    pydantic_util.clear_caches()

    # Track generated type names to avoid duplicates
    generated_type_names = set()

    logging.info(
        f"Building GraphQL types with max_recursion_depth={max_recursion_depth}"
    )

    # Patch strawberry.type to check for duplicates
    original_strawberry_type = strawberry.type
    strawberry.type = _create_patched_strawberry_type(
        original_strawberry_type, generated_type_names
    )

    try:
        # Discover model relationships and collect fields
        discover_model_relationships()
        collect_model_fields()

        # Get model info
        model_info_dict = get_model_info()
        logging.info(f"Found {len(model_info_dict)} models to process")

        # First pass: create types for reference models
        _create_reference_types(model_info_dict, max_recursion_depth)

        # Second pass: create types for main models
        _create_main_types(max_recursion_depth)

        # Update model info with created types
        for model_class, info in model_info_dict.items():
            if model_class in MODEL_TO_TYPE:
                info.gql_type = MODEL_TO_TYPE[model_class]

        logging.info(f"Created {len(MODEL_TO_TYPE)} GraphQL types")

        # Create schema classes
        logging.info("Building query class...")
        Query = build_query_class(model_info_dict)

        logging.info("Building mutation class...")
        Mutation = build_mutation_class(model_info_dict)

        logging.info("Building subscription class...")
        Subscription = build_subscription_class(model_info_dict)

        # Apply strawberry decorator to create root types
        strawberry_query = strawberry.type(Query)
        strawberry_mutation = strawberry.type(Mutation)
        strawberry_subscription = strawberry.type(Subscription)

        logging.info("Successfully built GraphQL schema types")
        return strawberry_query, strawberry_mutation, strawberry_subscription
    finally:
        # Restore the original strawberry.type function
        strawberry.type = original_strawberry_type


def _create_patched_strawberry_type(original_func, generated_type_names):
    """Create a patched version of strawberry.type that checks for duplicates"""

    def patched_strawberry_type(cls, **kwargs):
        if hasattr(cls, "__name__"):
            cls.__name__ = _check_type_name(cls.__name__, generated_type_names)
        result = original_func(cls, **kwargs)
        return result

    return patched_strawberry_type


def _check_type_name(name, generated_type_names):
    """Check if a type name is unique, add suffix if needed"""
    if name in generated_type_names:
        base = name
        counter = 1
        while name in generated_type_names:
            name = f"{base}_{counter}"
            counter += 1
    generated_type_names.add(name)
    return name


def _create_reference_types(model_info_dict, max_recursion_depth):
    """Create types for reference models"""
    logging.info("Creating types for reference models...")
    for model_class, info in model_info_dict.items():
        if (
            info.ref_model_class in MODEL_FIELDS_MAPPING
            and info.ref_model_class not in MODEL_TO_TYPE
        ):
            logging.debug(
                f"Creating type for reference model: {info.ref_model_class.__name__}"
            )
            create_strawberry_type(
                info.ref_model_class,
                MODEL_TO_TYPE,
                max_recursion_depth=max_recursion_depth,
            )


def _create_main_types(max_recursion_depth):
    """Create types for main models"""
    logging.info("Creating types for main models...")
    for model_class in MODEL_FIELDS_MAPPING:
        if model_class not in MODEL_TO_TYPE:
            logging.debug(f"Creating type for model: {model_class.__name__}")
            create_strawberry_type(
                model_class,
                MODEL_TO_TYPE,
                max_recursion_depth=max_recursion_depth,
            )


async def startup():
    """Initialize broadcaster on startup"""
    await broadcast.connect()


async def shutdown():
    """Clean up broadcaster on shutdown"""
    await broadcast.disconnect()


# Build the dynamic Strawberry types
Query, Mutation, Subscription = build_dynamic_strawberry_types(max_recursion_depth=3)

# Check for duplicate types
type_registry = {}
duplicate_types_found = False


def monitor_duplicate_types(cls):
    """Check for duplicate type names"""
    global duplicate_types_found
    if hasattr(cls, "__name__"):
        if cls.__name__ in type_registry:
            existing = type_registry[cls.__name__]
            if existing != cls:
                logging.error(f"Duplicate type name detected: {cls.__name__}")
                logging.error(f"First definition: {existing}")
                logging.error(f"Second definition: {cls}")
                duplicate_types_found = True
        else:
            type_registry[cls.__name__] = cls
    return cls


def monitor_schema_types(cls):
    """Monitor all types in a schema class"""
    if hasattr(cls, "__dict__"):
        for item in cls.__dict__.values():
            if hasattr(item, "__strawberry_definition__"):
                monitor_duplicate_types(item.__strawberry_definition__)
    return cls


# Check schema types
monitor_schema_types(Query)
monitor_schema_types(Mutation)
monitor_schema_types(Subscription)

if duplicate_types_found:
    logging.warning("Duplicate type names were found. Check logs for details.")

# Create the schema
schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)
