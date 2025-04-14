def generate_detailed_schema(self, model: Type[BaseModel], depth: int = 0) -> str:
    """
    Recursively generates a detailed schema representation of a Pydantic model.

    This function traverses through the fields of a Pydantic model and creates a
    string representation of its schema, including nested models and complex types.
    It handles various type constructs such as Lists, Dictionaries, Unions, and Enums.

    Args:
        model (Type[BaseModel]): The Pydantic model to generate a schema for.
        depth (int, optional): The current depth level for indentation. Defaults to 0.

    Returns:
        str: A string representation of the model's schema with proper indentation.
    """
    fields = get_type_hints(model)
    field_descriptions = []
    indent = "  " * depth
    for field, field_type in fields.items():
        description = f"{indent}{field}: "
        origin_type = get_origin(field_type)
        if origin_type is None:
            origin_type = field_type
        if inspect.isclass(origin_type) and issubclass(origin_type, BaseModel):
            description += f"Nested Model:\n{self._generate_detailed_schema(origin_type, depth + 1)}"
        elif origin_type == list:
            list_type = get_args(field_type)[0]
            if inspect.isclass(list_type) and issubclass(list_type, BaseModel):
                description += f"List of Nested Model:\n{self._generate_detailed_schema(list_type, depth + 1)}"
            elif get_origin(list_type) == Union:
                union_types = get_args(list_type)
                description += f"List of Union:\n"
                for union_type in union_types:
                    if inspect.isclass(union_type) and issubclass(
                        union_type, BaseModel
                    ):
                        description += f"{indent}  - Nested Model:\n{self._generate_detailed_schema(union_type, depth + 2)}"
                    else:
                        description += (
                            f"{indent}  - {self._get_type_name(union_type)}\n"
                        )
            else:
                description += f"List[{self._get_type_name(list_type)}]"
        elif origin_type == dict:
            key_type, value_type = get_args(field_type)
            description += f"Dict[{self._get_type_name(key_type)}, {self._get_type_name(value_type)}]"
        elif origin_type == Union:
            union_types = get_args(field_type)

            for union_type in union_types:
                if inspect.isclass(union_type) and issubclass(union_type, BaseModel):
                    description += f"{indent}  - Nested Model:\n{self._generate_detailed_schema(union_type, depth + 2)}"
                else:
                    type_name = self._get_type_name(union_type)
                    if type_name != "NoneType":
                        description += f"{self._get_type_name(union_type)}\n"
        elif inspect.isclass(origin_type) and issubclass(origin_type, Enum):
            enum_values = ", ".join([f"{e.name} = {e.value}" for e in origin_type])
            description += f"{origin_type.__name__} (Enum values: {enum_values})"
        else:
            description += self._get_type_name(origin_type)
        field_descriptions.append(description)
    return "\n".join(field_descriptions)


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
