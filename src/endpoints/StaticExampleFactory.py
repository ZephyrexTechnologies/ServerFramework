import datetime
import logging
import uuid
from typing import Any, Dict, Type, TypeVar, Union, get_args, get_origin

from pydantic import BaseModel

# Set up logging
logger = logging.getLogger(__name__)

# Generic type variables
T = TypeVar("T", bound=BaseModel)


class ExampleGenerator:
    """
    Utility class to generate example data for Pydantic models for OpenAPI documentation.

    This class analyzes Pydantic models and generates realistic example data based on
    field types, names, and patterns. It supports nested models, lists, and optional fields.
    """

    # Cache for generated examples to avoid redundant work
    _example_cache: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def generate_uuid() -> str:
        """Generate a random UUID string."""
        return str(uuid.uuid4())

    @staticmethod
    def get_example_value(field_type: Type, field_name: str) -> Any:
        """
        Generate an appropriate example value based on field type and name.

        Args:
            field_type: The type of the field
            field_name: The name of the field

        Returns:
            An appropriate example value
        """
        # Check for Optional types
        origin = get_origin(field_type)
        if origin is Union:
            args = get_args(field_type)
            if type(None) in args:  # This is an Optional type
                for arg in args:
                    if arg is not type(None):
                        field_type = arg
                        break

        # Check for List types
        if origin is list:
            inner_type = get_args(field_type)[0]
            # Return a list with a single example item of the inner type
            return [ExampleGenerator.get_example_value(inner_type, field_name)]

        # Check for Dict types
        if origin is dict or field_type is dict or field_type is Dict:
            # For dictionaries, provide a simple key-value example
            return {"key": "value"}

        # Generate example based on field type
        example_generators = {
            str: lambda: ExampleGenerator._generate_string_example(field_name),
            int: lambda: 42,
            float: lambda: 42.5,
            bool: lambda: ExampleGenerator._generate_bool_example(field_name),
            datetime.datetime: lambda: datetime.datetime.now().isoformat(),
            datetime.date: lambda: datetime.datetime.now().date().isoformat(),
        }

        # Use appropriate generator or return None for unsupported types
        return example_generators.get(field_type, lambda: None)()

    @staticmethod
    def _generate_string_example(field_name: str) -> str:
        """Generate string examples based on field name patterns."""
        field_lower = field_name.lower()

        # ID fields
        if field_lower == "id" or ("id" in field_lower and field_lower != "id"):
            return ExampleGenerator.generate_uuid()

        # Name fields
        elif "name" in field_lower:
            return ExampleGenerator.field_name_to_example(field_name)

        # Description fields
        elif "description" in field_lower:
            return (
                f"Description for {ExampleGenerator.field_name_to_example(field_name)}"
            )

        # Content fields
        elif "content" in field_lower:
            return f"Content for {ExampleGenerator.field_name_to_example(field_name)}"

        # Path fields
        elif "path" in field_lower:
            # Extract entity from field name
            entity_part = field_lower.replace("path", "").replace("_", "")
            if "relative" in field_lower:
                return f"path/to/{entity_part or 'resource'}.ext"
            elif "hosted" in field_lower:
                return f"https://example.com/path/to/{entity_part or 'resource'}.ext"
            else:
                return f"/path/to/{entity_part or 'resource'}"

        # URL fields
        elif "url" in field_lower:
            # Extract entity from field name
            entity_part = field_lower.replace("url", "").replace("_", "")
            return f"https://example.com/{entity_part or 'resource'}"

        # Role fields
        elif "role" in field_lower:
            if "admin" in field_lower:
                return "admin"
            elif "owner" in field_lower:
                return "owner"
            else:
                return "user"

        # Email fields
        elif "email" in field_lower:
            # Extract potential username from field
            username_part = field_lower.replace("email", "").replace("_", "")
            if username_part:
                return f"{username_part}@example.com"
            else:
                return "user@example.com"

        # Status fields
        elif "status" in field_lower:
            return "active"

        # Type fields
        elif "type" in field_lower:
            return "standard"

        # Code fields
        elif "code" in field_lower:
            return "ABC123"

        # Token fields
        elif "token" in field_lower:
            return f"tk-{ExampleGenerator.generate_uuid()[:8]}"

        # Generic string example
        else:
            return f"Example {field_name}"

    @staticmethod
    def _generate_bool_example(field_name: str) -> bool:
        """Generate boolean examples based on field name patterns."""
        # Favorite/favourite fields default to True
        if "favourite" in field_name.lower() or "favorite" in field_name.lower():
            return True

        # Is/has/enabled fields default to True
        elif field_name.lower().startswith(("is_", "has_", "enabled")):
            return True

        # Other boolean fields default to False
        return False

    @staticmethod
    def field_name_to_example(field_name: str) -> str:
        """
        Convert a field name to a readable example value.

        Args:
            field_name: The name of the field

        Returns:
            A readable example string
        """
        # Remove underscores and convert to title case
        parts = field_name.replace("_", " ").title().split()

        # Special handling for specific field names
        if field_name == "name":
            return "Example Name"

        # Extract potential entity type from the field name
        # E.g., "project_name" -> "Project", "user_id" -> "User"
        entity_type = None
        for part in parts:
            # Skip common attribute words
            if part.lower() in ["name", "id", "description", "type", "status", "date"]:
                continue
            entity_type = part
            break

        # Generate an appropriate example based on field semantics
        if entity_type:
            # Create a generic but descriptive example
            return f"Example {entity_type}"
        elif "name" in field_name.lower():
            return "Example Name"
        elif "title" in field_name.lower():
            return "Example Title"
        elif "description" in field_name.lower():
            return "Example Description"

        # Default to joining the parts
        formatted = " ".join(parts)
        return f"Example {formatted}"

    @staticmethod
    def generate_example_for_model(model_cls: Type[BaseModel]) -> Dict[str, Any]:
        """
        Generate a complete example object for a Pydantic model.

        Args:
            model_cls: The Pydantic model class

        Returns:
            Dictionary with example values for all fields
        """
        # Check cache first
        cache_key = f"{model_cls.__module__}.{model_cls.__name__}"
        if cache_key in ExampleGenerator._example_cache:
            logger.debug(f"Using cached example for {cache_key}")
            return ExampleGenerator._example_cache[cache_key].copy()

        logger.debug(f"Generating example for model: {model_cls.__name__}")
        example = {}

        # Process fields from model
        for field_name, field in model_cls.model_fields.items():
            field_info = field
            field_type = field_info.annotation

            # Check if field has a default value
            if not field_info.is_required():
                if field_info.default is not None:
                    example[field_name] = field_info.default
                    continue
                # Check if field has a default factory
                elif field_info.default_factory is not None:
                    example[field_name] = field_info.default_factory()
                    continue

            # Check for example in field metadata
            if (
                hasattr(field_info, "json_schema_extra")
                and field_info.json_schema_extra
            ):
                schema_extra = field_info.json_schema_extra
                if isinstance(schema_extra, dict) and "example" in schema_extra:
                    example[field_name] = schema_extra["example"]
                    continue

            # Generate example value based on field type and name
            example[field_name] = ExampleGenerator.get_example_value(
                field_type, field_name
            )

        # Cache the result for future use
        ExampleGenerator._example_cache[cache_key] = example.copy()

        return example

    @staticmethod
    def generate_operation_examples(
        network_model_cls: Any, resource_name: str
    ) -> Dict[str, Dict]:
        """
        Generate examples for all operation types (create, update, get, search).

        Args:
            network_model_cls: The NetworkModel class
            resource_name: The name of the resource

        Returns:
            Dictionary with examples for each operation type
        """
        logger.info(f"Generating operation examples for {resource_name}")
        examples = {}
        resource_name_plural = resource_name + "s"  # Simple pluralization

        # Get model classes using introspection
        response_single_cls = getattr(network_model_cls, "ResponseSingle", None)
        response_plural_cls = getattr(network_model_cls, "ResponsePlural", None)
        post_cls = getattr(network_model_cls, "POST", None)
        put_cls = getattr(network_model_cls, "PUT", None)
        search_cls = getattr(network_model_cls, "SEARCH", None)

        # Generate resource example
        resource_cls = None
        if response_single_cls:
            for field_name, field in response_single_cls.model_fields.items():
                if field_name == resource_name:
                    resource_cls = field.annotation
                    break

        if resource_cls:
            # Generate single resource example
            resource_example = ExampleGenerator.generate_example_for_model(resource_cls)

            # Get example
            examples["get"] = {resource_name: resource_example}

            # List example
            examples["list"] = {resource_name_plural: [resource_example]}

        # Generate create example
        if post_cls:
            create_field = None
            for field_name, field in post_cls.model_fields.items():
                if field_name == resource_name:
                    create_field = field
                    break

            if create_field:
                create_cls = create_field.annotation
                create_example = ExampleGenerator.generate_example_for_model(create_cls)
                examples["create"] = {resource_name: create_example}

        # Generate update example
        if put_cls:
            update_field = None
            for field_name, field in put_cls.model_fields.items():
                if field_name == resource_name:
                    update_field = field
                    break

            if update_field:
                update_cls = update_field.annotation
                update_example = ExampleGenerator.generate_example_for_model(update_cls)
                examples["update"] = {resource_name: update_example}

                # Also generate batch update example
                examples["batch_update"] = {
                    resource_name: update_example,  # Use the specific resource name
                    "target_ids": [
                        ExampleGenerator.generate_uuid(),
                        ExampleGenerator.generate_uuid(),
                    ],
                }

        # Generate search example
        if search_cls:
            search_field = None
            for field_name, field in search_cls.model_fields.items():
                if field_name == resource_name:
                    search_field = field
                    break

            if search_field:
                search_cls = search_field.annotation
                search_example = ExampleGenerator.generate_example_for_model(search_cls)

                # Make search examples more realistic for search operations
                # Only include a subset of fields that would commonly be used for filtering
                search_example_refined = {}

                for key, value in search_example.items():
                    # Keep ID fields, name fields, status fields, type fields, date fields
                    if (
                        "id" in key.lower()
                        or "name" in key.lower()
                        or "status" in key.lower()
                        or "type" in key.lower()
                        or "date" in key.lower()
                        or "created" in key.lower()
                        or "updated" in key.lower()
                    ):
                        search_example_refined[key] = value

                # If we filtered out everything, use original example
                if not search_example_refined:
                    search_example_refined = search_example

                examples["search"] = {resource_name: search_example_refined}

        # Generate batch delete example
        examples["batch_delete"] = {
            "target_ids": [
                ExampleGenerator.generate_uuid(),
                ExampleGenerator.generate_uuid(),
            ]
        }

        return examples

    @staticmethod
    def clear_cache():
        """Clear the example cache."""
        ExampleGenerator._example_cache.clear()

    @staticmethod
    def customize_example(
        example: Dict[str, Any], customizations: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply customizations to an example.

        Args:
            example: The original example dictionary
            customizations: Dict of paths to values to customize
                           (e.g., {"name": "Custom Name", "settings.theme": "dark"})

        Returns:
            Customized example dictionary
        """
        result = example.copy()

        for path, value in customizations.items():
            if "." in path:
                # Handle nested paths
                parts = path.split(".")
                current = result
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = value
            else:
                # Handle top-level paths
                result[path] = value

        return result
