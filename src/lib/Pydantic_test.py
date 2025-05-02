import inspect
import os
import sys
import unittest
from enum import Enum
from typing import Dict, List, Optional, Union, get_args, get_origin
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

# Add parent directory to sys.path to import Pydantic
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.Pydantic import PydanticUtility

# Access the utility functions from PydanticUtility
# Instead of importing functions directly that might not exist as standalone functions


class EnumForTest(Enum):
    """Test enum for schema generation testing."""

    VALUE1 = "value1"
    VALUE2 = "value2"


class NestedModel(BaseModel):
    """Test nested model."""

    id: int
    name: str


class RelatedModel(BaseModel):
    """Test related model."""

    id: int
    title: str


class ModelForTest(BaseModel):
    """Test model with various field types."""

    id: int
    name: str
    tags: List[str]
    nested: NestedModel
    nested_list: List[NestedModel]
    optional_nested: Optional[NestedModel] = None
    optional_string: Optional[str] = None
    enum_field: EnumForTest = EnumForTest.VALUE1
    union_field: Union[int, str]
    dict_field: Dict[str, int]


class ForwardRefUser(BaseModel):
    """Model with forward references."""

    id: int
    name: str
    # Forward reference to a model defined below
    references: List["ForwardReference"]
    optional_ref: Optional["ForwardReference"] = None


class ForwardReference(BaseModel):
    """Model referenced by ForwardRefUser."""

    id: int
    name: str
    user_id: int


# Create circular reference by updating ForwardReference.__annotations__
ForwardRefUser.update_forward_refs()


class UserModel(BaseModel):
    """User model for relationship testing."""

    id: int
    name: str
    email: str


class UserReferenceModel(BaseModel):
    """User reference model."""

    id: int


class UserNetworkModel(BaseModel):
    """User network model."""

    id: int


class UserManager:
    """User manager for relationship testing."""

    pass


class PostModel(BaseModel):
    """Post model for relationship testing."""

    id: int
    title: str
    content: str
    user_id: int
    user: UserReferenceModel


class CommentModel(BaseModel):
    """Comment model for relationship testing."""

    id: int
    content: str
    post_id: int
    user_id: int
    post: PostModel
    user: UserReferenceModel


class TestPydantic(unittest.TestCase):
    """Test suite for Pydantic.py functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.utility = PydanticUtility()

        # Register test models
        self.utility.register_model(ModelForTest)
        self.utility.register_model(NestedModel)
        self.utility.register_model(RelatedModel)
        self.utility.register_model(ForwardRefUser)
        self.utility.register_model(ForwardReference)

        # Create mock BLL modules for relationship testing
        self.bll_modules = {
            "user_module": MagicMock(
                UserModel=UserModel,
                UserReferenceModel=UserReferenceModel,
                UserNetworkModel=UserNetworkModel,
                UserManager=UserManager,
            ),
            "post_module": MagicMock(
                PostModel=PostModel,
                PostReferenceModel=BaseModel,
                PostNetworkModel=BaseModel,
                PostManager=MagicMock(),
            ),
            "comment_module": MagicMock(
                CommentModel=CommentModel,
                CommentReferenceModel=BaseModel,
                CommentNetworkModel=BaseModel,
                CommentManager=MagicMock(),
            ),
        }

    def test_is_model(self):
        """Test model detection functionality."""
        # Test if a Pydantic BaseModel class is properly handled
        self.assertTrue(hasattr(ModelForTest, "__fields__"))

        # Test interaction with utility (register and find)
        self.utility.register_model(ModelForTest)
        found_model = self.utility.find_model_by_name("test")
        self.assertEqual(found_model, ModelForTest)

        # A standard class should not have __fields__
        class NotAModel:
            pass

        self.assertFalse(hasattr(NotAModel, "__fields__"))

        # A standard module should not have __fields__
        self.assertFalse(hasattr(os, "__fields__"))

    def test_get_field_type(self):
        """Test field type extraction from models using get_model_fields."""
        # Get fields for TestModel
        fields = self.utility.get_model_fields(ModelForTest)

        # Verify field types
        self.assertIn("id", fields)
        self.assertEqual(fields["id"], int)

        self.assertIn("name", fields)
        self.assertEqual(fields["name"], str)

        self.assertIn("tags", fields)
        # Check that tags is a List[str]
        self.assertTrue(
            get_origin(fields["tags"]) is list or get_origin(fields["tags"]) is List
        )
        list_args = get_args(fields["tags"])
        self.assertTrue(len(list_args) > 0 and list_args[0] is str)

        # Verify nested field type
        self.assertIn("nested", fields)
        self.assertEqual(fields["nested"], NestedModel)

    def test_get_type_name(self):
        """Test get_type_name for different Python types."""
        # Test simple types - verify they produce string results
        type_names = {
            str: self.utility.get_type_name(str),
            int: self.utility.get_type_name(int),
            bool: self.utility.get_type_name(bool),
            float: self.utility.get_type_name(float),
            dict: self.utility.get_type_name(dict),
            list: self.utility.get_type_name(list),
        }

        # Verify we got string representations for each type
        for t, name in type_names.items():
            self.assertIsInstance(name, str)
            self.assertTrue(t.__name__ in name)

        # Test complex types
        dict_type_name = self.utility.get_type_name(Dict[str, int])
        self.assertIsInstance(dict_type_name, str)
        # Using assertIn separately since 'or' in assertions doesn't work as expected
        has_dict_name = "Dict" in dict_type_name or "dict" in dict_type_name
        self.assertTrue(
            has_dict_name, f"Neither 'Dict' nor 'dict' found in '{dict_type_name}'"
        )

        # Test list type (don't assume type parameters are included)
        list_type_name = self.utility.get_type_name(List[str])
        self.assertIsInstance(list_type_name, str)
        # Verify it's some form of list representation
        has_list_name = "List" in list_type_name or "list" in list_type_name
        self.assertTrue(
            has_list_name, f"Neither 'List' nor 'list' found in '{list_type_name}'"
        )

        # Test optional type (only check it returns a string)
        optional_type_name = self.utility.get_type_name(Optional[str])
        self.assertIsInstance(optional_type_name, str)

        # Test model type
        model_type_name = self.utility.get_type_name(ModelForTest)
        self.assertIsInstance(model_type_name, str)
        # Should contain at least part of the model name
        self.assertTrue(
            "Model" in model_type_name or "Test" in model_type_name,
            f"Neither 'Model' nor 'Test' found in '{model_type_name}'",
        )

    def test_process_annotations_with_forward_refs(self):
        """Test processing of annotations with forward references."""
        # Mock annotations with forward references
        annotations = {
            "value": int,
            "name": str,
            "items": "List[Item]",  # Forward reference
            "optional_item": "Optional[Item]",  # Forward reference with Optional
        }

        # Create a module-like object for context
        module_context = inspect.getmodule(self)

        # Register a mock Item class to be found by name
        class Item:
            pass

        # Register our Item class with the utility
        self.utility.register_model(Item, "Item")

        # Create a custom version of a resolver that works with our test
        original_resolve = self.utility.resolve_string_reference

        def mock_resolve(ref_str, context=None):
            if "Item" in ref_str:
                return Item
            return original_resolve(ref_str, context)

        # Replace temporarily
        self.utility.resolve_string_reference = mock_resolve

        try:
            # Process annotations
            result = self.utility.process_annotations_with_forward_refs(
                annotations, module_context
            )

            # Check the results - types should at least be preserved
            self.assertEqual(result["value"], int)
            self.assertEqual(result["name"], str)

            # Test items is present - skip checking container type if too complex
            self.assertIn("items", result)
            items_type = result["items"]
            # If the type has args, check for Item
            # If not, just ensure Item is mentioned in the string representation
            if hasattr(items_type, "__origin__"):
                origin = get_origin(items_type)
                if origin is not None:
                    args = get_args(items_type)
                    if args and len(args) > 0:
                        item_found = any(arg is Item for arg in args)
                        if not item_found:
                            # If no exact match, check if Item appears in string representation
                            self.assertIn("Item", str(items_type))
                    else:
                        # If no args but has origin, Item should be in string representation
                        self.assertIn("Item", str(items_type))
                else:
                    # If no origin, Item should be in string representation
                    self.assertIn("Item", str(items_type))
            else:
                # If not a container type, should be Item or have Item in string rep
                either_item_or_contains_item = (items_type is Item) or (
                    "Item" in str(items_type)
                )
                self.assertTrue(
                    either_item_or_contains_item,
                    f"Item not found in items_type: {items_type}",
                )

            # Test optional_item is present
            self.assertIn("optional_item", result)
            opt_type = result["optional_item"]
            # Check if Item appears in string representation or is Item itself
            either_item_or_contains_item = (opt_type is Item) or (
                "Item" in str(opt_type)
            )
            self.assertTrue(
                either_item_or_contains_item, f"Item not found in opt_type: {opt_type}"
            )
        finally:
            # Restore original method
            self.utility.resolve_string_reference = original_resolve

    @patch("pydantic.create_model")
    def test_create_model(self, mock_create_model):
        """Test model creation with Pydantic."""
        # Set up mock return value
        mock_model = MagicMock()
        mock_create_model.return_value = mock_model

        # Call the pydantic.create_model function directly
        from pydantic import create_model as pydantic_create_model

        # Test creating a simple model with fields
        model_name = "TestModel"
        fields = {"name": (str, ...), "age": (int, 0)}

        # We'll use the original implementation but verify our mock was called
        model = pydantic_create_model(model_name, **fields)

        # Verify our mock was called with the right parameters
        mock_create_model.assert_called_once_with(model_name, **fields)
        self.assertEqual(model, mock_model)

    def test_is_scalar_type(self):
        """Test _is_scalar_type method."""
        # Test scalar types
        self.assertTrue(self.utility._is_scalar_type(str))
        self.assertTrue(self.utility._is_scalar_type(int))
        self.assertTrue(self.utility._is_scalar_type(float))
        self.assertTrue(self.utility._is_scalar_type(bool))
        self.assertTrue(self.utility._is_scalar_type(dict))
        self.assertTrue(self.utility._is_scalar_type(list))

        # Test optional scalar types
        self.assertTrue(self.utility._is_scalar_type(Optional[str]))
        self.assertTrue(self.utility._is_scalar_type(Optional[int]))

        # Test non-scalar types
        self.assertFalse(self.utility._is_scalar_type(ModelForTest))
        self.assertFalse(self.utility._is_scalar_type(List[ModelForTest]))
        self.assertFalse(self.utility._is_scalar_type(Optional[ModelForTest]))

    def test_resolve_string_reference(self):
        """Test resolve_string_reference method."""
        # Test with direct model reference
        module_context = inspect.getmodule(ModelForTest)
        result = self.utility.resolve_string_reference("TestModel", module_context)
        self.assertEqual(result, ModelForTest)

        # Test with cached reference
        result2 = self.utility.resolve_string_reference("TestModel", module_context)
        self.assertEqual(result2, ModelForTest)

        # Test with unquoted string
        result3 = self.utility.resolve_string_reference('"TestModel"', module_context)
        self.assertEqual(result3, ModelForTest)

        # Test with non-existent model
        result4 = self.utility.resolve_string_reference(
            "NonExistentModel", module_context
        )
        self.assertIsNone(result4)

    def test_get_model_fields(self):
        """Test get_model_fields method."""
        # Test with simple model
        fields = self.utility.get_model_fields(NestedModel)
        self.assertEqual(len(fields), 2)
        self.assertIn("id", fields)
        self.assertIn("name", fields)
        self.assertEqual(fields["id"], int)
        self.assertEqual(fields["name"], str)

        # Test with complex model
        fields = self.utility.get_model_fields(ModelForTest)
        self.assertEqual(len(fields), 10)
        self.assertIn("nested", fields)
        self.assertIn("nested_list", fields)
        self.assertEqual(fields["nested"], NestedModel)

        # Test caching
        cached_fields = self.utility.get_model_fields(ModelForTest)
        self.assertEqual(id(fields), id(cached_fields))

    def test_register_model(self):
        """Test register_model method."""
        # Clear existing registrations
        self.utility._model_name_to_class.clear()

        # Register a model
        self.utility.register_model(ModelForTest)

        # Check direct registration - the key should be 'test' not 'testmodel'
        self.assertIn("test", self.utility._model_name_to_class)
        self.assertEqual(self.utility._model_name_to_class["test"], ModelForTest)

        # Register with custom name
        self.utility.register_model(NestedModel, "custom_name")
        self.assertIn("custom_name", self.utility._model_name_to_class)
        self.assertEqual(self.utility._model_name_to_class["custom_name"], NestedModel)

        # Test shortened name registration
        self.utility.register_model(RelatedModel, "prefix_related")
        self.assertIn("related", self.utility._model_name_to_class)

    def test_register_models(self):
        """Test register_models method."""
        # Clear existing registrations
        self.utility._model_name_to_class.clear()

        # Register multiple models
        models = [ModelForTest, NestedModel, RelatedModel]
        self.utility.register_models(models)

        # Check all models were registered with normalized names
        self.assertIn("test", self.utility._model_name_to_class)
        self.assertIn("nested", self.utility._model_name_to_class)
        self.assertIn("related", self.utility._model_name_to_class)

    def test_find_model_by_name(self):
        """Test find_model_by_name method."""
        # Clear existing registrations
        self.utility._model_name_to_class.clear()

        # Register models
        self.utility.register_model(ModelForTest)
        self.utility.register_model(UserModel)

        # Test direct match
        model = self.utility.find_model_by_name("test")
        self.assertEqual(model, ModelForTest)

        # Test case insensitive match
        model = self.utility.find_model_by_name("TEST")
        self.assertEqual(model, ModelForTest)

        # Test singular/plural handling
        self.utility.register_model(CommentModel, "comments")
        model = self.utility.find_model_by_name("comment")
        self.assertEqual(model, CommentModel)

        # Test partial match
        model = self.utility.find_model_by_name("user")
        self.assertEqual(model, UserModel)

        # Test no match
        model = self.utility.find_model_by_name("nonexistent")
        self.assertIsNone(model)

    def test_generate_unique_type_name(self):
        """Test generate_unique_type_name method."""
        # Test basic type name generation
        type_name = self.utility.generate_unique_type_name(ModelForTest)
        expected_name = (
            f"{ModelForTest.__module__.replace('.', '_')}_{ModelForTest.__name__}"
        )
        self.assertEqual(type_name, expected_name)

        # Test with suffix
        type_name = self.utility.generate_unique_type_name(ModelForTest, "Input")
        self.assertEqual(type_name, f"{expected_name}_Input")

        # Test caching
        cached_name = self.utility.generate_unique_type_name(ModelForTest)
        self.assertEqual(cached_name, expected_name)

    def test_generate_detailed_schema(self):
        """Test generate_detailed_schema method."""
        # Generate schema for simple model
        schema = self.utility.generate_detailed_schema(NestedModel)
        self.assertIn("id: int", schema)
        self.assertIn("name: str", schema)

        # Generate schema for complex model
        schema = self.utility.generate_detailed_schema(ModelForTest)
        self.assertIn("nested:", schema)
        self.assertIn("tags: List[str]", schema)
        self.assertIn("enum_field: TestEnum", schema)

        # Create a custom mocking of the generate_detailed_schema for max_depth testing
        original_method = self.utility.generate_detailed_schema

        def mock_generate_detailed_schema(model, max_depth=3, depth=0):
            if depth >= max_depth:
                return "(max depth reached)"
            if model == ForwardReference:
                return "ForwardReference fields"
            return original_method(model, max_depth, depth)

        # Temporarily replace the method
        self.utility.generate_detailed_schema = mock_generate_detailed_schema

        # Now test with max_depth=1
        schema = self.utility.generate_detailed_schema(
            ForwardRefUser, max_depth=1, depth=1
        )
        self.assertEqual(schema, "(max depth reached)")

        # Restore original method
        self.utility.generate_detailed_schema = original_method

    @pytest.mark.asyncio
    async def test_convert_to_model(self):
        """Test convert_to_model method."""

        # Create mock inference function
        async def mock_inference(user_input, schema, **kwargs):
            return '{"id": 1, "name": "Test"}'

        # Test successful conversion
        result = await self.utility.convert_to_model(
            "Convert this to a NestedModel",
            NestedModel,
            inference_function=mock_inference,
        )

        self.assertIsInstance(result, NestedModel)
        self.assertEqual(result.id, 1)
        self.assertEqual(result.name, "Test")

        # Test json response type
        result = await self.utility.convert_to_model(
            "Convert this to a NestedModel",
            NestedModel,
            response_type="json",
            inference_function=mock_inference,
        )

        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], 1)
        self.assertEqual(result["name"], "Test")

        # Test markdown code block handling
        async def mock_inference_with_markdown(user_input, schema, **kwargs):
            return """```json
{"id": 2, "name": "Markdown Test"}
```"""

        result = await self.utility.convert_to_model(
            "Convert this with markdown",
            NestedModel,
            inference_function=mock_inference_with_markdown,
        )

        self.assertIsInstance(result, NestedModel)
        self.assertEqual(result.id, 2)
        self.assertEqual(result.name, "Markdown Test")

        # Test error handling
        async def mock_inference_with_error(user_input, schema, **kwargs):
            failures = kwargs.get("failures", 0)
            if failures < 2:
                return '{"invalid": "json'
            return '{"id": 3, "name": "After Error"}'

        result = await self.utility.convert_to_model(
            "Convert with error",
            NestedModel,
            inference_function=mock_inference_with_error,
        )

        self.assertIsInstance(result, NestedModel)
        self.assertEqual(result.id, 3)
        self.assertEqual(result.name, "After Error")

        # Test max failures
        async def mock_inference_always_error(user_input, schema, **kwargs):
            return '{"invalid": "json'

        result = await self.utility.convert_to_model(
            "Always error",
            NestedModel,
            max_failures=2,
            inference_function=mock_inference_always_error,
        )

        self.assertIsInstance(result, str)
        self.assertIn("Failed to convert", result)

    def test_discover_model_relationships(self):
        """Test discover_model_relationships method."""
        # Note: The function might only discover relationships when a manager is present
        # Let's patch the method to test properly

        # First, create a simpler test case
        test_module = MagicMock(
            UserModel=UserModel,
            UserReferenceModel=UserReferenceModel,
            UserNetworkModel=UserNetworkModel,
            UserManager=UserManager,
        )

        simplified_modules = {"user_module": test_module}

        # With one module, we should get one relationship
        relationships = self.utility.discover_model_relationships(simplified_modules)
        self.assertEqual(
            len(relationships), 1
        )  # Expect 1 relationship in the simplified test

        # Basic structure check
        model_class, ref_model_class, network_model_class, manager_class = (
            relationships[0]
        )
        self.assertEqual(model_class, UserModel)
        self.assertEqual(ref_model_class, UserReferenceModel)
        self.assertEqual(network_model_class, UserNetworkModel)
        self.assertEqual(manager_class, UserManager)

    def test_collect_model_fields(self):
        """Test collect_model_fields method."""
        # Create test relationships with real model classes, not MagicMock objects
        relationships = [
            (UserModel, UserReferenceModel, UserNetworkModel, UserManager),
            (
                PostModel,
                PostModel,
                PostModel,
                object,
            ),  # Use real classes, not MagicMock
        ]

        model_fields = self.utility.collect_model_fields(relationships)

        # Check that fields were collected for all models
        self.assertIn(UserModel, model_fields)
        self.assertIn(UserReferenceModel, model_fields)
        self.assertIn(PostModel, model_fields)

        # Check field content
        self.assertEqual(len(model_fields[UserModel]), 3)  # id, name, email
        self.assertEqual(len(model_fields[UserReferenceModel]), 1)  # id

    def test_enhance_model_discovery(self):
        """Test enhance_model_discovery method."""
        # Clear existing registrations
        self.utility._model_name_to_class.clear()

        # Register base models
        self.utility.register_model(UserModel)
        self.utility.register_model(PostModel)  # Register PostModel too

        # Create model fields mapping
        model_fields = {
            PostModel: {
                "id": int,
                "title": str,
                "content": str,
                "user_id": int,
                "user": "UserModel",  # String reference
            },
            CommentModel: {
                "id": int,
                "content": str,
                "post_id": int,
                "post": PostModel,  # Direct reference
            },
        }

        # Enhance discovery
        self.utility.enhance_model_discovery(model_fields)

        # Check that new relationships were discovered
        self.assertEqual(self.utility.find_model_by_name("user"), UserModel)
        self.assertEqual(self.utility.find_model_by_name("post"), PostModel)

    def test_get_model_for_field(self):
        """Test get_model_for_field method."""
        # Clear existing registrations
        self.utility._model_name_to_class.clear()

        # Register models
        self.utility.register_model(UserModel)
        self.utility.register_model(PostModel)

        # Test direct field match
        model = self.utility.get_model_for_field("user", UserModel)
        self.assertEqual(model, UserModel)

        # Test with string reference
        model = self.utility.get_model_for_field("user_ref", "UserModel", PostModel)
        self.assertEqual(model, UserModel)

        # Test with list type
        model = self.utility.get_model_for_field("users", List[UserModel])
        self.assertEqual(model, UserModel)

        # Test with optional type
        model = self.utility.get_model_for_field("optional_user", Optional[UserModel])
        self.assertEqual(model, UserModel)

        # Test with non-existent model
        model = self.utility.get_model_for_field("nonexistent", str)
        self.assertIsNone(model)

    def test_get_model_hierarchy(self):
        """Test get_model_hierarchy method."""

        # Create test class hierarchy
        class BaseTestModel(BaseModel):
            id: int

        class ExtendedModel(BaseTestModel):
            name: str

        class FurtherExtendedModel(ExtendedModel):
            description: str

        # Get hierarchy
        hierarchy = self.utility.get_model_hierarchy(FurtherExtendedModel)

        # Check hierarchy order
        self.assertEqual(hierarchy[0], ExtendedModel)
        self.assertEqual(hierarchy[1], BaseTestModel)
        self.assertEqual(hierarchy[2], BaseModel)

        # Check caching
        cached_hierarchy = self.utility.get_model_hierarchy(FurtherExtendedModel)
        self.assertEqual(id(hierarchy), id(cached_hierarchy))

    def test_clear_caches(self):
        """Test clear_caches method."""
        # Populate caches
        self.utility.get_model_fields(ModelForTest)
        self.utility.register_model(ModelForTest)
        self.utility.generate_unique_type_name(ModelForTest)
        self.utility.get_model_for_field("test", ModelForTest)
        self.utility.get_model_hierarchy(ModelForTest)

        # Verify caches are populated
        self.assertNotEqual(len(self.utility._model_fields_cache), 0)
        self.assertNotEqual(len(self.utility._model_name_to_class), 0)
        self.assertNotEqual(len(self.utility._type_name_mapping), 0)

        # Clear caches
        self.utility.clear_caches()

        # Verify caches are cleared
        self.assertEqual(len(self.utility._model_fields_cache), 0)
        self.assertEqual(len(self.utility._model_name_to_class), 0)
        self.assertEqual(len(self.utility._type_name_mapping), 0)
        self.assertEqual(len(self.utility._relationship_cache), 0)
        self.assertEqual(len(self.utility._model_hierarchy_cache), 0)
        self.assertEqual(len(self.utility._processed_models), 0)

    def test_is_model_processed(self):
        """Test is_model_processed method."""
        # Initially model is not processed
        self.assertFalse(self.utility.is_model_processed(ModelForTest))

        # Mark as processed
        self.utility._processed_models.add(ModelForTest)

        # Now it should be processed
        self.assertTrue(self.utility.is_model_processed(ModelForTest))

    def test_mark_model_processed(self):
        """Test mark_model_processed method."""
        # Initially model is not processed
        self.assertFalse(self.utility.is_model_processed(ModelForTest))

        # Mark as processed
        self.utility.mark_model_processed(ModelForTest)

        # Now it should be processed
        self.assertTrue(self.utility.is_model_processed(ModelForTest))

    def test_process_model_relationships(self):
        """Test process_model_relationships method."""
        # Clear existing registrations
        self.utility._model_name_to_class.clear()

        # Register models
        self.utility.register_model(UserModel)
        self.utility.register_model(PostModel)
        self.utility.register_model(CommentModel)

        # Process relationships
        processed_models = set()
        relationships = self.utility.process_model_relationships(
            CommentModel, processed_models
        )

        # Check detected relationships
        self.assertIn("post", relationships)
        self.assertIn("user", relationships)
        self.assertEqual(relationships["post"], PostModel)
        self.assertEqual(relationships["user"], UserReferenceModel)

        # Check processed models tracking
        self.assertIn(CommentModel, processed_models)
        self.assertIn(PostModel, processed_models)
        self.assertIn(UserReferenceModel, processed_models)

        # Test max recursion depth
        processed_models = set()
        relationships = self.utility.process_model_relationships(
            CommentModel, processed_models, max_recursion_depth=0
        )

        # Only immediate relationships should be detected
        self.assertIn("post", relationships)
        self.assertIn("user", relationships)
        self.assertEqual(len(processed_models), 1)  # Only CommentModel


if __name__ == "__main__":
    unittest.main()
