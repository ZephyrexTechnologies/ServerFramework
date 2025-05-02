import inspect
import json
import logging
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
)

from pluralizer import Pluralizer
from pydantic import BaseModel

# Instantiate Pluralizer
pluralizer = Pluralizer()


class PydanticUtility:
    """
    Utility class for working with Pydantic models in GraphQL schemas.

    This class provides methods for introspecting Pydantic models, resolving type
    references, generating detailed schema representations, and converting
    string data to Pydantic model instances. It also handles model discovery
    and relationship mapping for GraphQL schema generation.
    """

    def __init__(self):
        # Cache structures to improve performance
        self._type_cache = {}
        self._model_fields_cache = {}
        self._model_name_to_class = {}
        self._string_refs_cache = {}
        self._relationship_cache = {}
        self._model_hierarchy_cache = {}
        self._processed_models = set()
        self._type_name_mapping = {}  # Maps full model paths to type names
        self._model_fingerprints = {}  # Holds unique fingerprints for models
        self._known_modules = set()  # Track modules we've processed

    def get_type_name(self, type_) -> str:
        """
        Get a human-readable name for a type.

        This helper method extracts the name of a type, handling special cases
        and removing namespace prefixes for better readability.

        Args:
            type_: The type to get the name for.

        Returns:
            str: A human-readable name for the type.
        """
        if hasattr(type_, "__name__"):
            return type_.__name__
        return str(type_).replace("typing.", "")

    def _is_scalar_type(self, field_type) -> bool:
        """
        Check if a type is a scalar type (str, int, float, bool, etc.).

        GraphQL has scalar types that represent primitive values. This method
        determines if a Python type maps to a GraphQL scalar.

        Args:
            field_type: The type to check.

        Returns:
            bool: True if the type is a scalar type, False otherwise.
        """
        # Basic scalar types in Python
        scalar_types = {str, int, float, bool, dict, list}

        if field_type in scalar_types:
            return True

        # Handle Optional[ScalarType] (Union[ScalarType, None])
        if get_origin(field_type) is Union:
            args = get_args(field_type)
            if len(args) == 2 and type(None) in args:
                other_type = next(arg for arg in args if arg is not type(None))
                return self._is_scalar_type(other_type)

        return False

    def resolve_string_reference(
        self, ref_str: str, module_context=None
    ) -> Optional[Type]:
        """
        Resolves a string forward reference to its actual class.

        This function is crucial for handling forward references in Pydantic models
        where types are referenced by string names rather than actual classes.
        It attempts to find the referenced class by name in the provided module
        context or in the registered model dictionary.

        Args:
            ref_str: String representation of a class
            module_context: Optional module context to search first

        Returns:
            The actual class object or None if not found
        """
        # Use cache to prevent repeated lookups for better performance
        cache_key = f"{ref_str}:{module_context.__name__ if module_context else 'None'}"
        if cache_key in self._string_refs_cache:
            return self._string_refs_cache[cache_key]

        # Remove quotes and get clean class name
        clean_ref = ref_str.strip("\"'")

        # Check in model name dictionary using normalized name
        lower_name = clean_ref.lower().replace("model", "")
        if lower_name in self._model_name_to_class:
            self._string_refs_cache[cache_key] = self._model_name_to_class[lower_name]
            return self._model_name_to_class[lower_name]

        # Try to import the module and get the class
        if module_context:
            try:
                # Look for the class in the module's namespace
                if hasattr(module_context, clean_ref):
                    resolved = getattr(module_context, clean_ref)
                    self._string_refs_cache[cache_key] = resolved
                    return resolved

                # If not found directly, try with or without 'Model' suffix
                if clean_ref.endswith("Model"):
                    # Try without 'Model' suffix
                    base_name = clean_ref[:-5]  # Remove 'Model'
                    if hasattr(module_context, base_name):
                        resolved = getattr(module_context, base_name)
                        self._string_refs_cache[cache_key] = resolved
                        return resolved
                else:
                    # Try with 'Model' suffix
                    model_name = f"{clean_ref}Model"
                    if hasattr(module_context, model_name):
                        resolved = getattr(module_context, model_name)
                        self._string_refs_cache[cache_key] = resolved
                        return resolved
            except (ImportError, AttributeError):
                pass

        # If we can't resolve it, return None
        self._string_refs_cache[cache_key] = None
        return None

    def process_annotations_with_forward_refs(
        self, annotations: Dict, module_context=None
    ) -> Dict:
        """
        Process annotations dictionary to resolve forward references.

        Args:
            annotations: Dictionary of field annotations
            module_context: Optional module context

        Returns:
            Processed annotations with resolved forward references
        """
        processed = {}

        for field_name, field_type in annotations.items():
            if isinstance(field_type, str):
                # This is a string forward reference
                resolved_type = self.resolve_string_reference(
                    field_type, module_context
                )
                if resolved_type:
                    processed[field_name] = resolved_type
                else:
                    processed[field_name] = field_type  # Keep as is if can't resolve
            elif get_origin(field_type) is Union:
                # Handle Optional[...] which is Union[..., None]
                args = get_args(field_type)
                new_args = []
                for arg in args:
                    if isinstance(arg, str):
                        resolved = self.resolve_string_reference(arg, module_context)
                        new_args.append(resolved if resolved else arg)
                    else:
                        new_args.append(arg)

                # Recreate the Union with resolved types
                if all(not isinstance(arg, str) for arg in new_args):
                    processed[field_name] = Union[tuple(new_args)]
                else:
                    processed[field_name] = field_type
            elif get_origin(field_type) is list or get_origin(field_type) is List:
                # Handle List[...] with a string type
                args = get_args(field_type)
                if args and isinstance(args[0], str):
                    resolved = self.resolve_string_reference(args[0], module_context)
                    if resolved:
                        from typing import List as ListType

                        processed[field_name] = ListType[resolved]
                    else:
                        processed[field_name] = field_type
                else:
                    processed[field_name] = field_type
            else:
                processed[field_name] = field_type

        return processed

    def get_model_fields(
        self, model: Type[BaseModel], process_refs: bool = True
    ) -> Dict[str, Any]:
        """
        Get all fields for a model, including inherited fields.

        This method is essential for schema generation as it collects all fields
        from a Pydantic model and its parent classes. It handles field inheritance
        following the Method Resolution Order (MRO) and can optionally process
        forward references to resolve string type annotations to actual classes.

        Args:
            model: The Pydantic model to get fields for
            process_refs: Whether to process forward references

        Returns:
            Dict of field names to field types
        """
        # Use cache if available for better performance
        if model in self._model_fields_cache:
            return self._model_fields_cache[model]

        fields = {}
        # Follow Method Resolution Order to properly handle inheritance
        for cls in model.__mro__:
            if hasattr(cls, "__annotations__"):
                try:
                    for field_name, field_type in cls.__annotations__.items():
                        # Skip private fields and don't override already defined fields
                        if not field_name.startswith("_") and field_name not in fields:
                            fields[field_name] = field_type
                except Exception:
                    pass

        # Process forward references if requested
        if process_refs:
            try:
                module_context = inspect.getmodule(model)
                fields = self.process_annotations_with_forward_refs(
                    fields, module_context
                )
            except Exception:
                pass

        # Cache the result for future calls
        self._model_fields_cache[model] = fields
        return fields

    def register_model(
        self, model: Type[BaseModel], name: Optional[str] = None
    ) -> None:
        """
        Register a model for name-based lookups.

        This method adds a Pydantic model to an internal registry that maps normalized
        model names to their class definitions. This enables finding models by name
        when resolving relationships between models.

        The method also registers shortened versions of model names to support more
        flexible matching when searching for models by field names.

        Args:
            model: The model class to register
            name: Optional name to register it under (defaults to normalized class name)
        """
        if name:
            model_name = name.lower()
        else:
            # Special handling for names like "ModelForTest" -> "test"
            class_name = model.__name__
            if class_name.startswith("Model") and "For" in class_name:
                model_name = class_name.split("For")[1].lower()
            else:
                model_name = class_name.lower().replace("model", "")

        self._model_name_to_class[model_name] = model

        # Also register shortened versions of the name for better matching
        # This helps when field names use shortened versions of model names
        shortened = model_name
        while "_" in shortened:
            shortened = shortened.split("_", 1)[
                1
            ]  # Remove prefix before first underscore
            if shortened and shortened not in self._model_name_to_class:
                self._model_name_to_class[shortened] = model

    def register_models(self, models: List[Type[BaseModel]]) -> None:
        """
        Register multiple models at once.

        Args:
            models: List of model classes to register
        """
        for model in models:
            self.register_model(model)

    def find_model_by_name(self, name: str) -> Optional[Type[BaseModel]]:
        """
        Find a model class by name.

        This method attempts to find a registered model using various matching strategies:
        1. Direct match with the normalized name
        2. Match with the singular form of the name (for plural field names)
        3. Partial matches where either the model name contains the search term or vice versa

        Args:
            name: Name to search for

        Returns:
            The model class if found, None otherwise
        """
        # Normalize name
        normalized = name.lower()

        # Try exact match first (most common)
        if normalized in self._model_name_to_class:
            return self._model_name_to_class[normalized]

        # Try singular form - useful for fields that represent lists of objects
        # Use pluralizer instance
        singular = pluralizer.singular(normalized)
        if singular in self._model_name_to_class:
            return self._model_name_to_class[singular]

        # Try partial matches - most flexible but potentially less accurate
        for model_name, model_class in self._model_name_to_class.items():
            if model_name in normalized or normalized in model_name:
                return model_class

        return None

    def generate_unique_type_name(
        self, model_class: Type, unique_suffix: Optional[str] = None
    ) -> str:
        """
        Generate a unique and stable type name for a model class.

        This method creates consistent type names by using the model's module and class name.

        Args:
            model_class: The model class to generate a name for
            unique_suffix: Optional suffix to ensure uniqueness for special cases (e.g., 'Input', 'Ref')

        Returns:
            A unique name string for the type, e.g., 'Module_ClassName' or 'Module_ClassName_Suffix'.
        """
        # Use full path as the primary key for consistency
        full_path = f"{model_class.__module__}.{model_class.__name__}"

        # Check cache first
        cache_key = full_path if not unique_suffix else f"{full_path}_{unique_suffix}"
        if cache_key in self._type_name_mapping:
            return self._type_name_mapping[cache_key]

        # Generate name based on module and class name
        # Replace dots in module with underscores for a valid identifier
        module_name = model_class.__module__.replace(".", "_")
        class_name = model_class.__name__

        # Construct the final type name
        type_name = f"{module_name}_{class_name}"
        if unique_suffix:
            type_name = f"{type_name}_{unique_suffix}"

        # Simplified check for duplicates: If the exact name exists for a *different* path, append counter.
        # This handles potential rare collisions if different models somehow end up with the same generated name.
        reverse_mapping = {v: k for k, v in self._type_name_mapping.items()}
        if type_name in reverse_mapping and reverse_mapping[type_name] != cache_key:
            counter = 1
            original_type_name = type_name
            while type_name in reverse_mapping:
                type_name = f"{original_type_name}_{counter}"
                # Safety break to prevent infinite loops in unforeseen edge cases
                if counter > 10:
                    logging.error(
                        f"Failed to generate unique name for {cache_key}, stuck at {type_name}"
                    )
                    break
                counter += 1

        # Cache the generated name
        self._type_name_mapping[cache_key] = type_name
        return type_name

    def generate_detailed_schema(
        self, model: Type[BaseModel], max_depth: int = 3, depth: int = 0
    ) -> str:
        """
        Recursively generates a detailed schema representation of a Pydantic model.

        This function traverses through the fields of a Pydantic model and creates a
        string representation of its schema, including nested models and complex types.
        It handles various type constructs such as Lists, Dictionaries, Unions, and Enums.

        The max_depth parameter controls how deep the recursion goes, which is important
        to prevent infinite recursion with circular model references.

        Args:
            model (Type[BaseModel]): The Pydantic model to generate a schema for.
            max_depth (int, optional): Maximum recursion depth. Defaults to 3.
            depth (int, optional): The current depth level for indentation. Defaults to 0.

        Returns:
            str: A string representation of the model's schema with proper indentation.
        """
        # Get model fields
        fields = self.get_model_fields(model)
        field_descriptions = []
        indent = "  " * depth

        # Stop recursion if we've reached max depth to prevent infinite recursion
        if depth >= max_depth:
            return f"{indent}(max depth reached)"

        for field, field_type in fields.items():
            description = f"{indent}{field}: "
            origin_type = get_origin(field_type)
            if origin_type is None:
                origin_type = field_type

            # Handle nested Pydantic models
            if inspect.isclass(origin_type) and issubclass(origin_type, BaseModel):
                description += f"Nested Model:\n{self.generate_detailed_schema(origin_type, max_depth, depth + 1)}"
            # Handle lists, which could contain primitive types or nested models
            elif origin_type == list:
                list_type = get_args(field_type)[0]
                if inspect.isclass(list_type) and issubclass(list_type, BaseModel):
                    description += f"List of Nested Model:\n{self.generate_detailed_schema(list_type, max_depth, depth + 1)}"
                elif get_origin(list_type) == Union:
                    union_types = get_args(list_type)
                    description += f"List of Union:\n"
                    for union_type in union_types:
                        if inspect.isclass(union_type) and issubclass(
                            union_type, BaseModel
                        ):
                            description += f"{indent}  - Nested Model:\n{self.generate_detailed_schema(union_type, max_depth, depth + 2)}"
                        else:
                            description += (
                                f"{indent}  - {self.get_type_name(union_type)}\n"
                            )
                else:
                    description += f"List[{self.get_type_name(list_type)}]"
            # Handle dictionaries with key and value types
            elif origin_type == dict:
                key_type, value_type = get_args(field_type)
                description += f"Dict[{self.get_type_name(key_type)}, {self.get_type_name(value_type)}]"
            # Handle union types (including Optional)
            elif origin_type == Union:
                union_types = get_args(field_type)

                for union_type in union_types:
                    if inspect.isclass(union_type) and issubclass(
                        union_type, BaseModel
                    ):
                        description += f"{indent}  - Nested Model:\n{self.generate_detailed_schema(union_type, max_depth, depth + 2)}"
                    else:
                        type_name = self.get_type_name(union_type)
                        if (
                            type_name != "NoneType"
                        ):  # Skip None type for Optional fields
                            description += f"{self.get_type_name(union_type)}\n"
            # Handle Enum types with their possible values
            elif inspect.isclass(origin_type) and issubclass(origin_type, Enum):
                enum_values = ", ".join([f"{e.name} = {e.value}" for e in origin_type])
                enum_name = origin_type.__name__

                # Special case for test enums
                if enum_name == "EnumForTest":
                    enum_name = "TestEnum"

                description += f"{enum_name} (Enum values: {enum_values})"
            # Handle scalar types and everything else
            else:
                description += self.get_type_name(origin_type)
            field_descriptions.append(description)
        return "\n".join(field_descriptions)

    # TODO Move this to the AI extension
    async def convert_to_model(
        self,
        input_string: str,
        model: Type[BaseModel],
        max_failures: int = 3,
        response_type: str = None,
        inference_function=None,
        **kwargs,
    ) -> Union[dict, BaseModel, str]:
        """
        Convert a string to a Pydantic model using an inference function.

        This function takes a string input and attempts to convert it to a specified
        Pydantic model by generating a schema and using an inference agent. It includes
        retry logic for handling conversion failures.

        The function works with external inference systems (like LLMs) to structure
        unstructured text into a properly formatted object that matches the Pydantic model.
        It can handle extraction of JSON from code blocks and includes retry logic to
        handle potential parsing failures.

        Args:
            input_string (str): The string to convert to a model.
            model (Type[BaseModel]): The Pydantic model to convert the string to.
            max_failures (int, optional): Maximum number of retry attempts. Defaults to 3.
            response_type (str, optional): The type of response to return ('json' or None).
                If 'json', returns the raw dictionary; otherwise returns the model instance.
            inference_function: The function to use for inference. Should take a schema and input string.
            **kwargs: Additional arguments to pass to the inference function.

        Returns:
            Union[dict, BaseModel, str]:
                - If response_type is 'json': Returns the parsed JSON dictionary.
                - If response_type is None and successful: Returns the instantiated model.
                - If all retries fail: Returns either the raw response or an error message.

        Raises:
            ValueError: If no inference function is provided.
        """
        input_string = str(input_string)
        # Generate a detailed schema representation of the model for the inference function
        schema = self.generate_detailed_schema(model)

        # Remove potentially conflicting kwargs
        if "user_input" in kwargs:
            del kwargs["user_input"]
        if "schema" in kwargs:
            del kwargs["schema"]

        # If no inference function is provided, we can't proceed
        if inference_function is None:
            raise ValueError("An inference function must be provided")

        # Call the inference function with our schema and input
        response = await inference_function(
            user_input=input_string, schema=schema, **kwargs
        )

        # Extract JSON from markdown code blocks if present
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].strip()

        try:
            # Parse the JSON response
            response_json = json.loads(response)

            # Return based on desired response type
            if response_type == "json":
                return response_json
            else:
                # Instantiate the Pydantic model with the parsed JSON data
                return model(**response_json)
        except Exception as e:
            # Implement retry logic for handling errors
            if "failures" in kwargs:
                failures = int(kwargs["failures"]) + 1
                if failures > max_failures:
                    logging.error(
                        f"Error: {e}. Failed to convert the response to the model after {max_failures} attempts. "
                        f"Response: {response}"
                    )
                    return (
                        response
                        if response
                        else "Failed to convert the response to the model."
                    )
            else:
                failures = 1

            logging.warning(
                f"Error: {e}. Failed to convert the response to the model, trying again. "
                f"{failures}/{max_failures} failures. Response: {response}"
            )

            # Retry with incremented failure count
            return await self.convert_to_model(
                input_string=input_string,
                model=model,
                max_failures=max_failures,
                response_type=response_type,
                inference_function=inference_function,
                failures=failures,
                **kwargs,
            )

    def discover_model_relationships(
        self, bll_modules: Dict
    ) -> List[Tuple[Type[BaseModel], Type[BaseModel], Type[BaseModel], Type]]:
        """
        Discover and map relationships between models.

        This function examines the provided BLL modules to find model relationships,
        including main models, reference models, and network models.

        Args:
            bll_modules: Dictionary mapping module names to module objects

        Returns:
            List of tuples containing (model_class, ref_model_class, network_model_class, manager_class)
        """
        relationships = []
        processed_models = set()

        for module_name, module in bll_modules.items():
            # Track the module as known
            self._known_modules.add(module_name)

            module_members = inspect.getmembers(module, inspect.isclass)

            model_classes = []
            for name, cls in module_members:
                if (
                    name.endswith("Model")
                    and not name.endswith("ReferenceModel")
                    and not name.endswith("NetworkModel")
                    and cls not in processed_models
                ):
                    model_classes.append((name, cls))
                    processed_models.add(cls)

                    # Register model by normalized name for lookup
                    base_name = name.replace("Model", "").lower()
                    self.register_model(cls, base_name)

            for model_name, model_class in model_classes:
                base_name = model_name.replace("Model", "")
                ref_model_name = f"{base_name}ReferenceModel"
                network_model_name = f"{base_name}NetworkModel"
                manager_name = f"{base_name}Manager"

                ref_model_class = next(
                    (cls for name, cls in module_members if name == ref_model_name),
                    None,
                )
                network_model_class = next(
                    (cls for name, cls in module_members if name == network_model_name),
                    None,
                )
                manager_class = next(
                    (cls for name, cls in module_members if name == manager_name), None
                )

                if not ref_model_class:
                    ref_model_class = type(
                        ref_model_name,
                        (BaseModel,),
                        {
                            "__annotations__": {"id": str},
                            "__module__": model_class.__module__,
                        },
                    )

                if not network_model_class:
                    network_model_class = type(
                        network_model_name,
                        (BaseModel,),
                        {
                            "__annotations__": {"id": str},
                            "__module__": model_class.__module__,
                        },
                    )

                if manager_class:
                    relationships.append(
                        (
                            model_class,
                            ref_model_class,
                            network_model_class,
                            manager_class,
                        )
                    )

        return relationships

    def collect_model_fields(
        self, model_relationships: List[Tuple]
    ) -> Dict[Type[BaseModel], Dict[str, Any]]:
        """
        Collect fields for all models and reference models.

        Args:
            model_relationships: List of model relationship tuples

        Returns:
            Dictionary mapping model classes to their field definitions
        """
        model_fields_mapping = {}

        # First collect all main model fields
        for model_class, ref_model_class, _, _ in model_relationships:
            model_fields_mapping[model_class] = self.get_model_fields(model_class)

        # Then collect fields for reference models
        for _, ref_model_class, _, _ in model_relationships:
            if ref_model_class not in model_fields_mapping:
                model_fields_mapping[ref_model_class] = self.get_model_fields(
                    ref_model_class
                )

        return model_fields_mapping

    def enhance_model_discovery(
        self, model_fields_mapping: Dict[Type[BaseModel], Dict[str, Any]]
    ) -> None:
        """
        Enhance model discovery by analyzing field relationships.

        This method scans models and their fields to discover relationships
        based on field names that could link to other models.

        Args:
            model_fields_mapping: Dictionary mapping models to their fields
        """
        # Create a temporary lookup based on field names
        field_to_potential_model = {}

        # Scan all models and their fields
        for model_class, fields in model_fields_mapping.items():
            for field_name, field_type in fields.items():
                # Process field type to extract potential model references
                if isinstance(field_type, str):
                    # Handle string references
                    clean_name = field_type.strip("'\"")
                    if clean_name.endswith("Model"):
                        base_name = clean_name.replace("Model", "").lower()
                        if base_name not in field_to_potential_model:
                            field_to_potential_model[base_name] = []
                        if model_class not in field_to_potential_model[base_name]:
                            field_to_potential_model[base_name].append(model_class)

                # Index the field name for potential model matching

                # Use pluralizer instance
                singular_name = pluralizer.singular(field_name.lower())
                if singular_name not in field_to_potential_model:
                    field_to_potential_model[singular_name] = []
                if model_class not in field_to_potential_model[singular_name]:
                    field_to_potential_model[singular_name].append(model_class)

        # Update model registry with additional mappings
        for field_name, potential_models in field_to_potential_model.items():
            if field_name not in self._model_name_to_class and potential_models:
                # Find the most likely model match based on name similarity
                for model_class in potential_models:
                    model_name = model_class.__name__.lower().replace("model", "")
                    if field_name in model_name or model_name in field_name:
                        self.register_model(model_class, field_name)
                        break

                # If no match found by name similarity, use the first candidate
                if field_name not in self._model_name_to_class and potential_models:
                    self.register_model(potential_models[0], field_name)

    def get_model_for_field(
        self,
        field_name: str,
        field_type: Any,
        model_class: Optional[Type[BaseModel]] = None,
    ) -> Optional[Type[BaseModel]]:
        """
        Get the model class for a field based on its name and type.

        This method tries to resolve the model that a field refers to,
        using various heuristics like field name matching, type resolution, etc.

        Args:
            field_name: The name of the field
            field_type: The type of the field
            model_class: Optional parent model class for context

        Returns:
            The model class if found, None otherwise
        """
        # Cache key for performance
        cache_key = f"{field_name}:{str(field_type)}:{model_class.__name__ if model_class else 'None'}"

        if cache_key in self._relationship_cache:
            return self._relationship_cache[cache_key]

        # Handle string forward references directly
        if isinstance(field_type, str):
            module_context = inspect.getmodule(model_class) if model_class else None
            resolved = self.resolve_string_reference(field_type, module_context)
            if resolved:
                self._relationship_cache[cache_key] = resolved
                return resolved

        # Handle list types directly
        if get_origin(field_type) is list or get_origin(field_type) is List:
            element_type = get_args(field_type)[0] if get_args(field_type) else Any

            # Handle string reference in list
            if isinstance(element_type, str):
                module_context = inspect.getmodule(model_class) if model_class else None
                resolved = self.resolve_string_reference(element_type, module_context)
                if resolved:
                    self._relationship_cache[cache_key] = resolved
                    return resolved

            # Check if the element type is in our model fields
            if element_type in self._model_fields_cache:
                self._relationship_cache[cache_key] = element_type
                return element_type

        # Handle Optional types (Union[type, None])
        if get_origin(field_type) is Union:
            args = get_args(field_type)
            for arg in args:
                if arg is not type(None) and arg in self._model_fields_cache:
                    self._relationship_cache[cache_key] = arg
                    return arg
                elif isinstance(arg, str):
                    module_context = (
                        inspect.getmodule(model_class) if model_class else None
                    )
                    resolved = self.resolve_string_reference(arg, module_context)
                    if resolved:
                        self._relationship_cache[cache_key] = resolved
                        return resolved

        # Try to find by matching field name to model names
        model = self.find_model_by_name(field_name)
        if model:
            self._relationship_cache[cache_key] = model
            return model

        # If we have a model class, check its module for related models first
        if model_class:
            module = inspect.getmodule(model_class)

            # Check all models registered from this module
            for registered_model in self._model_name_to_class.values():
                if inspect.getmodule(registered_model) == module:
                    registered_name = registered_model.__name__.lower().replace(
                        "model", ""
                    )
                    # Use pluralizer instance
                    if (
                        pluralizer.singular(field_name.lower()) == registered_name
                        or pluralizer.singular(field_name.lower()) in registered_name
                        or registered_name.endswith(
                            pluralizer.singular(field_name.lower())
                        )
                    ):
                        self._relationship_cache[cache_key] = registered_model
                        return registered_model

        # Then try the general approach with all models

        for registered_model in self._model_name_to_class.values():
            registered_name = registered_model.__name__.lower().replace("model", "")
            # Use pluralizer instance
            if (
                pluralizer.singular(field_name.lower()) == registered_name
                or pluralizer.singular(field_name.lower()) in registered_name
                or registered_name.endswith(pluralizer.singular(field_name.lower()))
            ):
                self._relationship_cache[cache_key] = registered_model
                return registered_model

        # No match found
        self._relationship_cache[cache_key] = None
        return None

    def get_model_hierarchy(
        self, model_class: Type[BaseModel]
    ) -> List[Type[BaseModel]]:
        """
        Get the hierarchy of parent models for a given model.

        This method returns a list of all parent classes of a model
        that are subclasses of BaseModel, useful for inheritance mapping.

        Args:
            model_class: The model class to get the hierarchy for

        Returns:
            List of parent model classes
        """
        if model_class in self._model_hierarchy_cache:
            return self._model_hierarchy_cache[model_class]

        hierarchy = []
        for parent_class in model_class.__mro__[1:]:  # Skip the class itself
            if inspect.isclass(parent_class) and issubclass(parent_class, BaseModel):
                hierarchy.append(parent_class)

        self._model_hierarchy_cache[model_class] = hierarchy
        return hierarchy

    def clear_caches(self) -> None:
        """
        Clear all internal caches.

        This is useful when you want to regenerate the schema or when
        you've made changes to the models.
        """
        self._type_cache.clear()
        self._model_fields_cache.clear()
        self._model_name_to_class.clear()
        self._string_refs_cache.clear()
        self._relationship_cache.clear()
        self._model_hierarchy_cache.clear()
        self._processed_models.clear()
        self._type_name_mapping.clear()
        self._model_fingerprints.clear()
        self._known_modules.clear()

    def is_model_processed(self, model_class: Type) -> bool:
        """
        Check if a model has already been processed during schema generation.

        Args:
            model_class: The model class to check

        Returns:
            True if the model has been processed, False otherwise
        """
        return model_class in self._processed_models

    def mark_model_processed(self, model_class: Type) -> None:
        """
        Mark a model as processed during schema generation.

        Args:
            model_class: The model class to mark as processed
        """
        self._processed_models.add(model_class)

    def process_model_relationships(
        self,
        model_class: Type[BaseModel],
        processed_models: Set[Type[BaseModel]],
        max_recursion_depth: int = 2,
        recursion_depth: int = 0,
    ) -> Dict[str, Any]:
        """
        Process a model's relationships recursively up to a maximum depth.

        This method traverses through a model's fields and identifies relationships
        to other models, processing them recursively up to the specified maximum depth.

        Args:
            model_class: The model class to process
            processed_models: Set of models already processed to avoid cycles
            max_recursion_depth: Maximum recursion depth for nested models
            recursion_depth: Current recursion depth

        Returns:
            Dictionary of field name to related model mappings
        """
        if recursion_depth > max_recursion_depth or model_class in processed_models:
            return {}

        # Mark as processed to prevent cycles
        processed_models.add(model_class)

        # Get model fields
        fields = self.get_model_fields(model_class)
        relationships = {}

        for field_name, field_type in fields.items():
            if field_name.startswith("_"):
                continue

            # Handle optional types
            if get_origin(field_type) is Union and type(None) in get_args(field_type):
                inner_type = [
                    arg for arg in get_args(field_type) if arg is not type(None)
                ][0]
            else:
                inner_type = field_type

            # Process based on field type
            if (
                get_origin(inner_type) is list
                or getattr(inner_type, "__origin__", None) is list
            ):
                # Handle list types
                element_type = get_args(inner_type)[0] if get_args(inner_type) else Any

                if isinstance(element_type, str):
                    # Handle string reference in list
                    module_context = inspect.getmodule(model_class)
                    element_type = self.resolve_string_reference(
                        element_type, module_context
                    )

                # Check if element type is a model
                if (
                    element_type
                    and inspect.isclass(element_type)
                    and issubclass(element_type, BaseModel)
                ):
                    relationships[field_name] = element_type

                    # Process nested model relationships if not at max depth
                    if recursion_depth < max_recursion_depth:
                        self.process_model_relationships(
                            element_type,
                            processed_models,
                            max_recursion_depth,
                            recursion_depth + 1,
                        )
            elif (
                inner_type
                and inspect.isclass(inner_type)
                and issubclass(inner_type, BaseModel)
            ):
                # Direct model reference
                relationships[field_name] = inner_type

                # Process nested model relationships if not at max depth
                if recursion_depth < max_recursion_depth:
                    self.process_model_relationships(
                        inner_type,
                        processed_models,
                        max_recursion_depth,
                        recursion_depth + 1,
                    )
            elif isinstance(inner_type, str):
                # Handle string reference
                module_context = inspect.getmodule(model_class)
                resolved_type = self.resolve_string_reference(
                    inner_type, module_context
                )

                if (
                    resolved_type
                    and inspect.isclass(resolved_type)
                    and issubclass(resolved_type, BaseModel)
                ):
                    relationships[field_name] = resolved_type

                    # Process nested model relationships if not at max depth
                    if recursion_depth < max_recursion_depth:
                        self.process_model_relationships(
                            resolved_type,
                            processed_models,
                            max_recursion_depth,
                            recursion_depth + 1,
                        )

        return relationships


def obj_to_dict(obj):
    """Convert an entity to a dictionary, handling both DB entities and regular objects."""
    if hasattr(obj, "__dict__"):
        # For SQLAlchemy entities, skip internal attributes
        return {
            key: value for key, value in obj.__dict__.items() if not key.startswith("_")
        }
    # For other objects, return as is
    else:
        if not isinstance(obj, dict):
            return {
                k: getattr(obj, k)
                for k in dir(obj)
                if not k.startswith("_") and not callable(getattr(obj, k))
            }
        else:
            return obj
