from datetime import date, datetime
from typing import Dict, List, Optional
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from endpoints.StaticExampleFactory import ExampleGenerator


class SimpleModel(BaseModel):
    id: str
    name: str
    description: str
    is_active: bool


class NestedModel(BaseModel):
    id: str
    name: str
    details: SimpleModel


class ComplexModel(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: date
    tags: List[str]
    settings: Dict[str, str]
    is_favorite: bool
    has_attachments: bool
    status: str
    type: str
    email: str
    role: str
    url: str
    path: str
    relative_path: str
    hosted_path: str
    token: str
    code: str


class NetworkModel:
    class POST(BaseModel):
        resource: SimpleModel

    class PUT(BaseModel):
        resource: SimpleModel

    class SEARCH(BaseModel):
        resource: SimpleModel

    class ResponseSingle(BaseModel):
        resource: SimpleModel

    class ResponsePlural(BaseModel):
        resources: List[SimpleModel]


@pytest.fixture
def clear_example_cache():
    """Clear the example cache before each test."""
    ExampleGenerator.clear_cache()
    yield
    ExampleGenerator.clear_cache()  # Cleanup after test


def test_generate_uuid():
    """Test that UUID generation creates valid UUIDs."""
    uuid1 = ExampleGenerator.generate_uuid()
    uuid2 = ExampleGenerator.generate_uuid()

    # Check format
    assert len(uuid1) == 36
    assert len(uuid2) == 36

    # Check uniqueness
    assert uuid1 != uuid2


def test_get_example_value_string(clear_example_cache):
    """Test string example generation for different field names."""
    # ID fields
    assert ExampleGenerator.get_example_value(str, "id").startswith("")

    # Basic fields
    assert isinstance(ExampleGenerator.get_example_value(str, "name"), str)
    assert isinstance(ExampleGenerator.get_example_value(str, "description"), str)
    assert isinstance(ExampleGenerator.get_example_value(str, "content"), str)

    # Check URL-type fields
    url_example = ExampleGenerator.get_example_value(str, "url")
    assert url_example.startswith("https://")

    # Check path fields
    path_example = ExampleGenerator.get_example_value(str, "path")
    assert path_example.startswith("/path/")

    relative_path = ExampleGenerator.get_example_value(str, "relative_path")
    assert "path/to/" in relative_path

    hosted_path = ExampleGenerator.get_example_value(str, "hosted_path")
    assert "https://" in hosted_path

    # Check email fields
    email = ExampleGenerator.get_example_value(str, "email")
    assert "@example.com" in email

    user_email = ExampleGenerator.get_example_value(str, "user_email")
    assert "user@example.com" in user_email

    # Check role fields
    role = ExampleGenerator.get_example_value(str, "role")
    assert role == "user"

    admin_role = ExampleGenerator.get_example_value(str, "admin_role")
    assert admin_role == "admin"

    # Check status fields
    status = ExampleGenerator.get_example_value(str, "status")
    assert status == "active"

    # Check type fields
    type_field = ExampleGenerator.get_example_value(str, "type")
    assert type_field == "standard"

    # Check code fields
    code = ExampleGenerator.get_example_value(str, "code")
    assert code == "ABC123"

    # Check token fields
    token = ExampleGenerator.get_example_value(str, "token")
    assert token.startswith("tk-")


def test_get_example_value_primitive_types(clear_example_cache):
    """Test example generation for primitive types."""
    assert ExampleGenerator.get_example_value(int, "count") == 42
    assert ExampleGenerator.get_example_value(float, "amount") == 42.5
    assert isinstance(ExampleGenerator.get_example_value(datetime, "created_at"), str)
    assert isinstance(ExampleGenerator.get_example_value(date, "created_date"), str)


def test_get_example_value_bool(clear_example_cache):
    """Test boolean example generation based on field name."""
    assert ExampleGenerator.get_example_value(bool, "is_active") is True
    assert ExampleGenerator.get_example_value(bool, "has_permission") is True
    assert ExampleGenerator.get_example_value(bool, "enabled") is True
    assert ExampleGenerator.get_example_value(bool, "favorite") is True
    assert ExampleGenerator.get_example_value(bool, "favourite") is True

    # Default for other boolean fields should be False
    assert ExampleGenerator.get_example_value(bool, "deleted") is False


def test_get_example_value_lists(clear_example_cache):
    """Test list example generation."""
    list_example = ExampleGenerator.get_example_value(List[str], "tags")
    assert isinstance(list_example, list)
    assert len(list_example) == 1
    assert isinstance(list_example[0], str)


def test_get_example_value_dict(clear_example_cache):
    """Test dict example generation."""
    dict_example = ExampleGenerator.get_example_value(Dict[str, str], "metadata")
    assert isinstance(dict_example, dict)
    assert dict_example == {"key": "value"}


def test_get_example_value_optional(clear_example_cache):
    """Test optional type handling."""
    optional_example = ExampleGenerator.get_example_value(
        Optional[str], "optional_name"
    )
    assert isinstance(optional_example, str)


def test_field_name_to_example(clear_example_cache):
    """Test field name to example conversion."""
    assert ExampleGenerator.field_name_to_example("name") == "Example Name"
    assert ExampleGenerator.field_name_to_example("project_name") == "Example Project"
    assert (
        ExampleGenerator.field_name_to_example("description") == "Example Description"
    )
    assert ExampleGenerator.field_name_to_example("project_id") == "Example Project"
    assert (
        ExampleGenerator.field_name_to_example("unknown_field")
        == "Example Unknown Field"
    )


def test_generate_example_for_model(clear_example_cache):
    """Test example generation for models."""
    # Test example generation for a simple model
    simple_example = ExampleGenerator.generate_example_for_model(SimpleModel)
    assert isinstance(simple_example, dict)
    assert "id" in simple_example
    assert "name" in simple_example
    assert "description" in simple_example
    assert "is_active" in simple_example

    # Test example generation for a complex model
    complex_example = ExampleGenerator.generate_example_for_model(ComplexModel)
    assert "id" in complex_example
    assert "name" in complex_example
    assert "description" in complex_example
    assert "created_at" in complex_example
    assert "updated_at" in complex_example
    assert "tags" in complex_example
    assert "settings" in complex_example
    assert "is_favorite" in complex_example
    assert "has_attachments" in complex_example
    assert complex_example["is_favorite"] is True  # Should be True for favorite fields
    assert complex_example["has_attachments"] is True  # Should be True for has_ fields


def test_example_caching(clear_example_cache):
    """Test that example generation is cached."""
    with patch.object(ExampleGenerator, "get_example_value") as mock_get_value:
        # First call should use the method
        ExampleGenerator.generate_example_for_model(SimpleModel)
        assert mock_get_value.called

        mock_get_value.reset_mock()

        # Second call should use the cache
        ExampleGenerator.generate_example_for_model(SimpleModel)
        assert not mock_get_value.called


def test_clear_cache(clear_example_cache):
    """Test cache clearing."""
    # Generate an example to populate the cache
    ExampleGenerator.generate_example_for_model(SimpleModel)

    # Cache should now have an entry
    cache_key = f"{SimpleModel.__module__}.{SimpleModel.__name__}"
    assert cache_key in ExampleGenerator._example_cache

    # Clear the cache
    ExampleGenerator.clear_cache()

    # Cache should be empty
    assert len(ExampleGenerator._example_cache) == 0


def test_generate_operation_examples(clear_example_cache):
    """Test operation example generation."""
    operation_examples = ExampleGenerator.generate_operation_examples(
        NetworkModel, "resource"
    )

    # Check that all operation types are generated
    assert "get" in operation_examples
    assert "list" in operation_examples
    assert "create" in operation_examples
    assert "update" in operation_examples
    assert "search" in operation_examples
    assert "batch_update" in operation_examples
    assert "batch_delete" in operation_examples

    # Check the content of examples
    assert "resource" in operation_examples["get"]
    assert "resources" in operation_examples["list"]
    assert "resource" in operation_examples["create"]
    assert "resource" in operation_examples["update"]
    assert "resource" in operation_examples["search"]
    assert "resource" in operation_examples["batch_update"]
    assert "target_ids" in operation_examples["batch_update"]
    assert "target_ids" in operation_examples["batch_delete"]


def test_customize_example(clear_example_cache):
    """Test example customization."""
    # Generate a base example
    example = ExampleGenerator.generate_example_for_model(SimpleModel)

    # Test basic customization
    customized = ExampleGenerator.customize_example(example, {"name": "Custom Name"})
    assert customized["name"] == "Custom Name"

    # Test nested customization
    complex_example = {"user": {"name": "Original", "settings": {"theme": "light"}}}
    nested_customized = ExampleGenerator.customize_example(
        complex_example, {"user.name": "New Name", "user.settings.theme": "dark"}
    )
    assert nested_customized["user"]["name"] == "New Name"
    assert nested_customized["user"]["settings"]["theme"] == "dark"
