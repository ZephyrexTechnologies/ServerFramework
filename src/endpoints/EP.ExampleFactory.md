# Example Factory Documentation

## Overview

The Example Factory provides utilities for automatically generating realistic example data for API documentation based on Pydantic models. It intelligently creates appropriate example values based on field types, names, and patterns, ensuring that API documentation includes meaningful and representative examples.

## Key Components

### ExampleGenerator Class

The core of the Example Factory is the `ExampleGenerator` class which analyzes Pydantic models and generates appropriate example data.

```python
class ExampleGenerator:
    """
    Utility class to generate example data for Pydantic models for OpenAPI documentation.

    This class analyzes Pydantic models and generates realistic example data based on
    field types, names, and patterns. It supports nested models, lists, and optional fields.
    """
```

## Features

1. **Intelligent Field Type Detection**: Automatically determines appropriate example values based on field types (strings, integers, booleans, dates, etc.)
2. **Field Name Pattern Recognition**: Recognizes common field name patterns and generates appropriate examples
3. **Caching Mechanism**: Caches generated examples to improve performance
4. **Support for Complex Types**: Handles nested models, lists, dictionaries, and optional fields
5. **Customizable Examples**: Allows overriding generated examples with custom values

## Field Name Pattern Recognition

The Example Factory intelligently generates values based on field name patterns:

| Field Pattern         | Example Generated                  |
| --------------------- | ---------------------------------- |
| ID fields             | UUID strings                       |
| Name fields           | "Example Name"                     |
| Description fields    | "Description for Example Resource" |
| Boolean `is_` fields  | `true`                             |
| Boolean `has_` fields | `true`                             |
| Email fields          | "user@example.com"                 |
| URL fields            | "https://example.com/resource"     |
| Path fields           | "/path/to/resource"                |
| Role fields           | "user", "admin", etc.              |
| Status fields         | "active"                           |
| Type fields           | "standard"                         |
| Code fields           | "ABC123"                           |
| Token fields          | "tk-{uuid}"                        |

## Usage Examples

### Generating Examples for a Model

```python
from pydantic import BaseModel
from endpoints.StaticExampleFactory import ExampleGenerator

class UserModel(BaseModel):
    id: str
    name: str
    email: str
    is_active: bool

# Generate example for a model
example = ExampleGenerator.generate_example_for_model(UserModel)
print(example)
# Output: {'id': '12345678-1234-5678-1234-567812345678', 'name': 'Example Name', 'email': 'user@example.com', 'is_active': True}
```

### Generating Examples for API Operations

```python
# Define your NetworkModel class with POST, PUT, SEARCH, ResponseSingle, ResponsePlural
class UserNetworkModel:
    # ... your model classes here ...

# Generate examples for all operation types
examples = ExampleGenerator.generate_operation_examples(UserNetworkModel, "user")

# Access specific example types
create_example = examples["create"]  # For POST operations
get_example = examples["get"]        # For GET operations by ID
list_example = examples["list"]      # For GET operations (listing)
update_example = examples["update"]  # For PUT operations
search_example = examples["search"]  # For search operations
```

### Customizing Generated Examples

```python
# Generate base example
example = ExampleGenerator.generate_example_for_model(UserModel)

# Customize specific fields
customized = ExampleGenerator.customize_example(
    example, 
    {
        "name": "John Doe",
        "email": "john.doe@example.com"
    }
)

# Customize nested fields using dot notation
nested_example = {"user": {"settings": {"theme": "light"}}}
customized_nested = ExampleGenerator.customize_example(
    nested_example,
    {
        "user.settings.theme": "dark"
    }
)
```

## Implementation Details

### Key Methods

1. **generate_example_for_model(model_cls)**: Analyzes a Pydantic model and generates a complete example

2. **get_example_value(field_type, field_name)**: Generates an appropriate example value for a specific field type and name

3. **generate_operation_examples(network_model_cls, resource_name)**: Generates examples for all standard operation types (create, get, list, update, search)

4. **customize_example(example, customizations)**: Applies custom overrides to a generated example

5. **clear_cache()**: Clears the internal cache of generated examples

### Example Caching

The Example Factory uses an internal cache to improve performance when generating examples for the same model multiple times. The cache is implemented as a class-level dictionary:

```python
_example_cache: Dict[str, Dict[str, Any]] = {}
```

Cache entries are keyed by the model's fully qualified name and store the complete generated example.

## Integration with AbstractEPRouter

The Example Factory is designed to work seamlessly with the AbstractEPRouter to provide automatic example generation for API documentation:

```python
router = AbstractEPRouter(
    prefix="/v1/resource",
    tags=["Resource Management"],
    manager_factory=get_resource_manager,
    network_model_cls=ResourceNetworkModel,
    example_overrides={
        "create": {"resource": {"name": "Custom Example"}},
    },
)
```

The router calls `ExampleGenerator.generate_operation_examples()` during initialization and uses the results to populate OpenAPI documentation.

## Best Practices

1. **Field Naming**: Use consistent and descriptive field names to leverage the pattern recognition features

2. **Custom Examples**: Provide custom examples for complex fields that cannot be automatically generated

3. **Documentation**: Add example values in field metadata for special cases:
   ```python
   class User(BaseModel):
       status: str = Field(..., json_schema_extra={"example": "premium"})
   ```

4. **Clear Cache**: Call `ExampleGenerator.clear_cache()` when memory usage is a concern or when you need to regenerate examples

5. **Test Coverage**: Ensure your test suite includes verification of generated examples to catch any regressions or inconsistencies 