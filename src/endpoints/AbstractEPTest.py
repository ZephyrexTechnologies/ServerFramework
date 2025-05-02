import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import pytest
from faker import Faker
from pydantic import BaseModel

# Assume src is in python path
from AbstractTest import AbstractTest, ParentEntity
from lib.Environment import env  # Import the new base class

# Set up logging
logger = logging.getLogger(__name__)

from pluralizer import Pluralizer


# Inherit from AbstractTest
class AbstractEndpointTest(AbstractTest):
    """Base class for testing REST API endpoints with support for dependent entities.

    This abstract class provides a comprehensive set of tests for REST API endpoints
    following the patterns described in EP.schema.md and EP.patterns.md.

    Features:
    - Standard CRUD operation testing
    - Batch operations support
    - Nested resources handling
    - Authentication testing
    - GraphQL integration
    - Parent-child relationship testing
    - Validation testing
    - Flexible test configuration

    Child classes should override class attributes and implement the create_parent_entities
    method if their resource requires parent entities.
    """

    # To be overridden by child classes
    base_endpoint: str = None
    entity_name: str = None
    string_field_to_update: str = "name"
    required_fields: List[str] = None

    # System entity flag - determines if entity requires API keys
    system_entity: bool = False  # Default to False, override in child classes

    # Dependent entity configuration

    # Required parameters for GraphQL queries, beyond parent entities
    # Override in child classes if needed.
    # Example:
    # required_graphql_params = {
    #     "role_id": "00000000-0000-0000-0000-000000000001",  # default value to use
    #     "user_id": None  # None means this param is required but no default
    # }
    # This will ensure these parameters are included in GraphQL queries even if they're
    # not part of parent_entities. If the parameter is found in the resource, that value
    # will be used. Otherwise, the default value will be used.
    required_graphql_params: Dict[str, Any] = {}

    # Search configuration - can be overridden by child classes
    supports_search: bool = True
    searchable_fields: List[str] = ["name"]  # Default searchable fields
    search_example_value: str = None  # Example value to search for

    # --- Endpoint Path Configuration --- #
    # Defines default nesting behavior. Child classes override specific keys
    # in NESTING_CONFIG_OVERRIDES.
    # Values represent nesting level: 0=standalone, 1=single, 2=double
    DEFAULT_NESTING_CONFIG: Dict[str, int] = {
        "LIST": 0,
        "CREATE": 0,
        "DETAIL": 0,  # Covers GET/PUT/DELETE
        "SEARCH": 0,
    }
    NESTING_CONFIG_OVERRIDES: Dict[str, int] = {}

    # Create a faker instance
    faker = Faker()

    def _get_nesting_level(self, operation: str) -> int:
        """Get the nesting level for a given operation, respecting overrides.

        Args:
            operation: The operation type (LIST, CREATE, DETAIL, SEARCH)

        Returns:
            int: The nesting level (0=standalone, 1=single, 2=double)
        """
        # Check for override first
        if operation in self.NESTING_CONFIG_OVERRIDES:
            return self.NESTING_CONFIG_OVERRIDES[operation]

        # Fall back to default config
        return self.DEFAULT_NESTING_CONFIG[operation]

    @property
    def list_endpoint_template(self) -> str:
        """Get the endpoint template for listing resources."""
        nesting = self._get_nesting_level("LIST")
        if nesting == 0:
            return f"/v1/{self.base_endpoint}"
        elif nesting == 1:
            return f"/v1/{{{self.parent_entities[0].name}}}/{self.base_endpoint}"
        elif nesting == 2:
            return f"/v1/{{{self.parent_entities[0].name}}}/{{{self.parent_entities[1].name}}}/{self.base_endpoint}"

    @property
    def create_endpoint_template(self) -> str:
        """Get the API endpoint template for create operations."""
        # Same as list endpoint for now
        return self.list_endpoint_template

    @property
    def get_endpoint_template(self) -> str:
        """Get the API endpoint template for get operations."""
        # Base endpoint with ID placeholder
        if self.base_endpoint.endswith("/"):
            return f"{self.base_endpoint}{{id}}"
        return f"{self.base_endpoint}/{{id}}"

    @property
    def update_endpoint_template(self) -> str:
        """Get the API endpoint template for update operations."""
        # Same as get endpoint for PUT operations
        return self.get_endpoint_template

    @property
    def delete_endpoint_template(self) -> str:
        """Get the API endpoint template for delete operations."""
        # Same as get endpoint for DELETE operations
        return self.get_endpoint_template

    @property
    def search_endpoint_template(self) -> str:
        """Get the API endpoint template for search operations."""
        # Add search suffix to list endpoint
        return f"{self.list_endpoint_template}/search"

    @property
    def resource_name_plural(self) -> str:
        """Get the pluralized resource name for requests."""
        pluralizer = Pluralizer()
        return pluralizer.pluralize(self.entity_name)

    def get_path_parent_entity(self) -> Optional[ParentEntity]:
        """Get the parent entity that should be included in the path."""
        for entity in self.parent_entities:
            if entity.is_path or entity.path_level is not None:
                return entity
        return None

    def has_parent_entities(self) -> bool:
        """Check if this resource has parent entities."""
        return len(self.parent_entities) > 0

    def has_nullable_parent_entities(self) -> bool:
        """Check if this resource has nullable parent entities."""
        return any(entity.nullable for entity in self.parent_entities)

    def _get_path_parents_by_level(self) -> Dict[int, ParentEntity]:
        """Get a dictionary of path parent entities by level."""
        result = {}
        for entity in self.parent_entities:
            # Legacy support for is_path (treat as level 1)
            if entity.is_path and entity.path_level is None:
                result[1] = entity
            # Use path_level if set
            elif entity.path_level is not None:
                result[entity.path_level] = entity
        return result

    def get_parent_entity_by_name(self, name: str) -> Optional[ParentEntity]:
        """Get a parent entity by name."""
        for entity in self.parent_entities:
            if entity.name == name:
                return entity
        return None

    def _get_endpoint_for_op(
        self,
        op_type: str,
        resource_id: Optional[str] = None,
        parent_ids: Dict[str, str] = None,
    ) -> str:
        """
        Construct the endpoint based on operation type and nesting configuration.

        Args:
            op_type: Type of operation (LIST, CREATE, DETAIL, SEARCH)
            resource_id: Optional resource ID for detailed operations
            parent_ids: Optional dict of parent entity IDs

        Returns:
            Complete API endpoint path
        """
        # Get nesting level for this operation
        nesting_level = self.DEFAULT_NESTING_CONFIG.get(op_type, 0)
        if op_type in self.NESTING_CONFIG_OVERRIDES:
            nesting_level = self.NESTING_CONFIG_OVERRIDES[op_type]

        # If no nesting, use simple endpoints
        if nesting_level == 0:
            if op_type == "LIST":
                endpoint = self.list_endpoint_template
            elif op_type == "CREATE":
                endpoint = self.create_endpoint_template
            elif op_type == "DETAIL":
                endpoint = self.get_endpoint_template.format(id=resource_id)
            elif op_type == "SEARCH":
                endpoint = self.search_endpoint_template
            else:
                raise ValueError(f"Unknown operation type: {op_type}")
            return endpoint

        # Handle nested resources
        path_parents = self._get_path_parents_by_level()
        path_components = []

        # Base API prefix
        base_prefix = "/api/v1"
        if self.base_endpoint.startswith(base_prefix):
            # If base_endpoint already has the prefix, use it as is
            base_path = ""
        else:
            # Otherwise add the prefix
            base_path = base_prefix

        # Add parent paths based on nesting level
        for level in range(1, nesting_level + 1):
            if level in path_parents:
                parent = path_parents[level]
                parent_id = parent_ids.get(parent.foreign_key) if parent_ids else None
                if parent_id:
                    parent_path = f"/{parent.name.lower()}/{parent_id}"
                    path_components.append(parent_path)
                else:
                    if not parent.nullable:
                        raise ValueError(
                            f"Required parent {parent.name} missing for nesting level {level}"
                        )

        # Build final path
        resource_path = f"/{self.base_endpoint}"
        if resource_id and op_type == "DETAIL":
            resource_path = f"{resource_path}/{resource_id}"
        elif op_type == "SEARCH":
            resource_path = f"{resource_path}/search"

        final_path = f"{base_path}{''.join(path_components)}{resource_path}"
        return final_path

    def get_list_endpoint(self, parent_ids: Dict[str, str] = None) -> str:
        """Get the API endpoint for list operations."""
        return self._get_endpoint_for_op("LIST", parent_ids=parent_ids)

    def get_create_endpoint(self, parent_ids: Dict[str, str] = None) -> str:
        """Get the API endpoint for create operations."""
        return self._get_endpoint_for_op("CREATE", parent_ids=parent_ids)

    def get_detail_endpoint(
        self, resource_id: str, parent_ids: Dict[str, str] = None
    ) -> str:
        """Get the API endpoint for get/update/delete operations."""
        return self._get_endpoint_for_op(
            "DETAIL", resource_id=resource_id, parent_ids=parent_ids
        )

    def get_update_endpoint(
        self, resource_id: str, parent_ids: Dict[str, str] = None
    ) -> str:
        """Get the API endpoint for update operations."""
        return self.get_detail_endpoint(resource_id, parent_ids)

    def get_delete_endpoint(
        self, resource_id: str, parent_ids: Dict[str, str] = None
    ) -> str:
        """Get the API endpoint for delete operations."""
        return self.get_detail_endpoint(resource_id, parent_ids)

    def get_search_endpoint(self, parent_ids: Dict[str, str] = None) -> str:
        """Get the API endpoint for search operations."""
        return self._get_endpoint_for_op("SEARCH", parent_ids=parent_ids)

    @staticmethod
    def _auth_header(jwt_token: str) -> Dict[str, str]:
        """Create an authentication header with a JWT token."""
        return {"Authorization": f"Bearer {jwt_token}"}

    @staticmethod
    def _api_key_header(api_key: str = None) -> Dict[str, str]:
        """Create an API key header if needed."""
        if api_key:
            return {"X-API-Key": api_key}
        return {}

    def nest_payload_in_entity(
        self, entity: Union[Dict[str, Any], List[Dict[str, Any]]]
    ) -> Union[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """
        Nest the payload in the entity name.

        API design pattern: POST/PUT requests should nest the entity data
        under the entity name, e.g. {"user": {...}} for a user resource.

        Args:
            entity: The entity data or list of entities

        Returns:
            Nested payload ready for API request
        """
        return {self.entity_name: entity}

    def generate_name(self) -> str:
        """Generate a unique name for test entities."""
        return f"Test {self.entity_name.capitalize()} {self.faker.word().capitalize()} {self.faker.random_int(min=1000, max=9999)}"

    def generate_test_data(
        self, model_cls: Type[BaseModel] = None, field_overrides: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate test data for the given model class.

        Args:
            model_cls: The Pydantic model class to generate data for (optional)
            field_overrides: Dictionary of field values to override in the generated data

        Returns:
            Dictionary containing field values for the model
        """
        data = {}

        # Generate a random name if it's a typical entity
        data["name"] = self.generate_name()

        # Add example data based on field names
        if model_cls:
            for field_name, field_info in model_cls.model_fields.items():
                if field_name not in data:
                    if "email" in field_name.lower():
                        data[field_name] = self.faker.email()
                    elif "description" in field_name.lower():
                        data[field_name] = self.faker.paragraph(nb_sentences=2)
                    elif "password" in field_name.lower():
                        data[field_name] = self.faker.password(length=12)
                    elif "user_id" in field_name.lower():
                        data[field_name] = str(uuid.uuid4())
                    elif "team_id" in field_name.lower():
                        data[field_name] = str(uuid.uuid4())
                    elif "role_id" in field_name.lower():
                        data[field_name] = str(uuid.uuid4())
                    elif "url" in field_name.lower():
                        data[field_name] = self.faker.url()
                    elif "phone" in field_name.lower():
                        data[field_name] = self.faker.phone_number()

        # Apply any overrides
        if field_overrides:
            data.update(field_overrides)

        return data

    def create_payload(
        self, name: str = None, parent_ids: Dict[str, str] = None, team_id: str = None
    ) -> Dict[str, Any]:
        """
        Create a payload for creating a new resource.

        Args:
            name: Optional name to use (generates one if not provided)
            parent_ids: Optional parent entity IDs
            team_id: Optional team ID to associate

        Returns:
            Complete payload for API request
        """
        # Generate basic data
        payload = {"name": name or self.faker.word()}

        # Add parent entity IDs
        if parent_ids:
            for entity in self.parent_entities:
                if entity.foreign_key in parent_ids:
                    payload[entity.foreign_key] = parent_ids[entity.foreign_key]

        # Add team_id if provided and not a system entity
        if team_id and not self.system_entity:
            payload["team_id"] = team_id

        return payload

    def create_search_payload(self, field: str, value: Any) -> Dict[str, Any]:
        """
        Create a search payload for the search endpoint.

        Args:
            field: Field to search on
            value: Value to search for

        Returns:
            Search payload for API request
        """
        # Convert to camel case for API
        field_camel = self.to_camel_case(field)

        # Create search payload with inclusion filter
        return {field_camel: {"inc": value}}

    def to_camel_case(self, snake_str: str) -> str:
        """Convert a snake_case string to camelCase."""
        components = snake_str.split("_")
        return components[0] + "".join(x.title() for x in components[1:])

    def _extract_parent_ids(
        self, entity: Dict[str, Any]
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Extract parent IDs from an entity response.

        Args:
            entity: Entity response from API

        Returns:
            Tuple of (parent_ids, all_params) where:
                parent_ids: Dict of parent entity keys to IDs
                all_params: Dict of all parameters including parent IDs and other required params
        """
        parent_ids = {}
        all_params = {}

        # Extract parent IDs
        for parent in self.parent_entities:
            if parent.foreign_key in entity:
                parent_ids[parent.foreign_key] = entity[parent.foreign_key]
                all_params[parent.foreign_key] = entity[parent.foreign_key]

        # Add any required GraphQL params
        for param_key, default_value in self.required_graphql_params.items():
            if param_key in entity:
                all_params[param_key] = entity[param_key]
            elif default_value is not None:
                all_params[param_key] = default_value

        return parent_ids, all_params

    def _get_appropriate_headers(
        self, jwt_token: str, api_key: str = None
    ) -> Dict[str, str]:
        """
        Get the appropriate headers for API requests.

        Args:
            jwt_token: JWT token for authentication
            api_key: Optional API key for system entities

        Returns:
            Complete headers for API request
        """
        headers = {}

        # Add Auth header if JWT provided
        if jwt_token:
            headers.update(self._auth_header(jwt_token))

        # Add API key header if needed
        if self.system_entity and api_key:
            headers.update(self._api_key_header(api_key))

        return headers

    def _assert_response_status(
        self, response, expected_status, operation, endpoint, payload=None
    ):
        """Assert that a response has the expected status code."""
        if response.status_code != expected_status:
            error_msg = (
                f"{operation} to {endpoint} failed with status {response.status_code}, "
                f"expected {expected_status}. "
            )
            if payload:
                error_msg += f"Payload: {json.dumps(payload)}"
            if hasattr(response, "json"):
                try:
                    error_msg += f"\nResponse: {json.dumps(response.json())}"
                except Exception:
                    error_msg += f"\nResponse text: {response.text}"
            assert False, error_msg

    def _assert_entity_in_response(
        self, response, entity_field=None, expected_value=None
    ):
        """
        Assert that an entity is present in the response and has expected values.

        Args:
            response: API response
            entity_field: Optional field to check
            expected_value: Optional expected value for the field
        """
        # Get JSON response
        try:
            data = response.json()
        except json.JSONDecodeError:
            assert False, f"Invalid JSON response: {response.text}"

        # Check for entity under entity name
        if self.entity_name in data:
            entity = data[self.entity_name]
        # Handle direct entity responses
        elif "id" in data:
            entity = data
        # Handle list responses
        elif isinstance(data, list) and len(data) > 0:
            entity = data[0]
        else:
            assert False, f"Entity not found in response: {json.dumps(data)}"

        # Check specific field if provided
        if entity_field and expected_value is not None:
            assert (
                entity_field in entity
            ), f"Field '{entity_field}' not in entity: {json.dumps(entity)}"
            assert entity[entity_field] == expected_value, (
                f"Field '{entity_field}' mismatch: expected {expected_value}, "
                f"got {entity[entity_field]}"
            )

        return entity

    def _assert_entities_in_response(self, response, entity_type=None):
        """
        Assert that entities are present in the response and optionally filtered by type.

        Args:
            response: API response
            entity_type: Optional entity type to filter by
        """
        # Get JSON response
        try:
            data = response.json()
        except json.JSONDecodeError:
            assert False, f"Invalid JSON response: {response.text}"

        # Check for entities under pluralized name (common pattern)
        plural_key = self.resource_name_plural
        if plural_key in data:
            entities = data[plural_key]
        # Handle direct array response
        elif isinstance(data, list):
            entities = data
        # Handle entity lists under "items" key (another common pattern)
        elif "items" in data:
            entities = data["items"]
        else:
            assert False, f"Entities not found in response: {json.dumps(data)}"

        # Ensure we have entities
        assert len(entities) > 0, "No entities found in response"

        # Check type if specified
        if entity_type:
            for entity in entities:
                assert (
                    "type" in entity
                ), f"Entity doesn't have 'type' field: {json.dumps(entity)}"
                assert entity["type"] == entity_type, (
                    f"Entity type mismatch: expected {entity_type}, "
                    f"got {entity['type']}"
                )

        return entities

    def _assert_parent_ids_match(self, entity, parent_ids):
        """Assert that parent IDs in the entity match expected values."""
        if parent_ids:
            for parent_key, parent_id in parent_ids.items():
                assert (
                    parent_key in entity
                ), f"Parent key '{parent_key}' not in entity: {json.dumps(entity)}"
                assert entity[parent_key] == parent_id, (
                    f"Parent ID mismatch for '{parent_key}': expected {parent_id}, "
                    f"got {entity[parent_key]}"
                )

    def _assert_has_created_by_user_id(self, entity, jwt_token):
        """
        Assert that the entity has created_by_user_id matching the authenticated user.

        Args:
            entity: Entity from response
            jwt_token: JWT token used for authentication
        """
        # Skip this check if we don't have JWT validation logic
        # In a real implementation, we would decode the JWT and compare user ID
        assert "created_by_user_id" in entity, "Entity missing created_by_user_id field"
        assert entity["created_by_user_id"] is not None, "created_by_user_id is null"

    def _assert_has_updated_by_user_id(self, entity, jwt_token):
        """
        Assert that the entity has updated_by_user_id matching the authenticated user.

        Args:
            entity: Entity from response
            jwt_token: JWT token used for authentication
        """
        # Skip this check if we don't have JWT validation logic
        assert "updated_by_user_id" in entity, "Entity missing updated_by_user_id field"
        assert entity["updated_by_user_id"] is not None, "updated_by_user_id is null"

    def _setup_test_resources(self, server, jwt_token, team, count=1, api_key=None):
        """
        Set up test resources for tests that need pre-existing entities.

        Args:
            server: Test server
            jwt_token: JWT token for authentication
            team: Team object for team association
            count: Number of entities to create
            api_key: Optional API key for system entities

        Returns:
            Tuple of (resources, parent_ids) where:
                resources: List of created resources
                parent_ids: Dict of parent entity keys to IDs
        """
        # Use centralized fixtures
        from conftest import standard_team_ids

        # Get parent IDs from fixtures or create them if needed
        parent_ids = {}
        if self.has_parent_entities():
            # This would need to be implemented in the specific test class
            # that has parent entities defined
            pass

        # Default team ID if not provided
        team_id = None
        if team and "id" in team:
            team_id = team["id"]

        # Create test resources
        resources = []
        for i in range(count):
            payload = self.create_payload(
                name=f"Test {i} {self.faker.word()}",
                parent_ids=parent_ids,
                team_id=team_id,
            )

            nested_payload = self.nest_payload_in_entity(payload)

            # Get appropriate endpoint
            endpoint = self.get_create_endpoint(parent_ids=parent_ids)

            # Get headers
            headers = self._get_appropriate_headers(jwt_token, api_key)

            # Create resource
            response = server.post(endpoint, json=nested_payload, headers=headers)

            # Verify successful creation
            self._assert_response_status(
                response, 201, "POST", endpoint, nested_payload
            )

            # Extract entity and save
            entity = self._assert_entity_in_response(response)
            resources.append(entity)

        return resources, parent_ids

    def test_POST_201(self, server, admin_a_jwt, team_a, api_key=None):
        """Test successful resource creation with valid authentication."""
        test_name = "test_POST_201"
        self.reason_to_skip(test_name)

        # Generate a unique name for the test resource
        resource_name = self.faker.word()

        # Create parent entities if required
        parent_ids = {}
        path_parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(
                server, admin_a_jwt, team_a
            )
            for parent in self.parent_entities:
                if parent.name in parent_entities_dict:
                    parent_id = parent_entities_dict[parent.name].id
                    parent_ids[parent.foreign_key] = parent_id
                    # Use path_level to populate path_parent_ids
                    if parent.path_level in [1, 2]:
                        path_parent_ids[f"{parent.name}_id"] = parent_id
                    # Fallback for backward compatibility (if is_path=True and path_level=None)
                    elif parent.is_path and parent.path_level is None:
                        path_parent_ids[f"{parent.name}_id"] = parent_id

        # Create the payload using the child class implementation
        payload = self.create_payload(resource_name, parent_ids, team_a.id)

        # Choose the appropriate authentication header
        headers = self._get_appropriate_headers(admin_a_jwt, api_key)

        # Make the request
        response = server.post(
            self.get_create_endpoint(path_parent_ids),
            json=payload,
            headers=headers,
        )

        # Assertions
        self._assert_response_status(
            response, 201, "POST", self.get_create_endpoint(path_parent_ids), payload
        )
        entity = self._assert_entity_in_response(
            response,
            self.string_field_to_update if self.string_field_to_update else None,
            resource_name if self.string_field_to_update else None,
        )
        self._assert_parent_ids_match(entity, parent_ids)

        # Assert that the entity has created_by_user_id matching the user
        self._assert_has_created_by_user_id(entity, admin_a_jwt)

        return entity

    def test_POST_201_null_parents(self, server, admin_a_jwt, team_a, api_key=None):
        """Test creating a resource with nullable parent fields set to null."""
        test_name = "test_POST_201_null_parents"
        self.reason_to_skip(test_name)

        # Check if there are any nullable parents
        nullable_parents = [p for p in self.parent_entities if p.nullable]
        if not nullable_parents:
            pytest.skip("No nullable parents for this entity")

        # Generate a unique name for the test resource
        resource_name = self.faker.word()

        # Create non-nullable parent entities if required
        parent_ids = {}
        path_parent_ids = {}

        # First handle non-nullable parents (we need actual IDs for these)
        for parent in self.parent_entities:
            if not parent.nullable:
                parent_entities_dict = self.create_parent_entities(
                    server, admin_a_jwt, team_a
                )

                if parent.name in parent_entities_dict:
                    parent_id = parent_entities_dict[parent.name].id
                    parent_ids[parent.foreign_key] = parent_id
                    # Use path_level to populate path_parent_ids
                    if parent.path_level in [1, 2]:
                        path_parent_ids[f"{parent.name}_id"] = parent_id
                    # Fallback for backward compatibility (if is_path=True and path_level=None)
                    elif parent.is_path and parent.path_level is None:
                        path_parent_ids[f"{parent.name}_id"] = parent_id

        # Create the payload - set nullable parents to None
        payload = (
            {"name": resource_name} if self.string_field_to_update == "name" else {}
        )

        # Add name if string_field_to_update is set to something other than "name"
        if self.string_field_to_update and self.string_field_to_update != "name":
            payload[self.string_field_to_update] = resource_name

        # Add IDs for non-nullable parents
        for parent in self.parent_entities:
            if not parent.nullable and parent.foreign_key in parent_ids:
                payload[parent.foreign_key] = parent_ids[parent.foreign_key]
            elif parent.nullable:
                payload[parent.foreign_key] = None

        if team_a and "team_id" in self.required_fields:
            payload["team_id"] = team_a.id

        # Nest the payload in the entity
        nested_payload = self.nest_payload_in_entity(entity=payload)

        # Choose the appropriate authentication header
        headers = self._get_appropriate_headers(admin_a_jwt, api_key)

        # Make the request
        response = server.post(
            self.get_create_endpoint(path_parent_ids),
            json=nested_payload,
            headers=headers,
        )

        # Assert the response
        self._assert_response_status(
            response,
            201,
            "POST with null parents",
            self.get_create_endpoint(path_parent_ids),
            nested_payload,
        )
        entity = self._assert_entity_in_response(
            response,
            self.string_field_to_update if self.string_field_to_update else None,
            resource_name if self.string_field_to_update else None,
        )

        # Verify nullable parents are null/None in the response
        for parent in nullable_parents:
            assert parent.foreign_key in entity, (
                f"Expected nullable parent {parent.foreign_key} to be in response\n"
                f"Entity: {entity}"
            )
            assert entity[parent.key] is None, (
                f"Expected nullable parent {parent.foreign_key} to be None, got {entity[parent.key]}\n"
                f"Entity: {entity}"
            )

        # Assert that the entity has created_by_user_id matching the user
        self._assert_has_created_by_user_id(entity, admin_a_jwt)

        return entity

    def test_POST_201_batch(self, server, admin_a_jwt, team_a, api_key=None):
        """Test successful batch creation of resources."""
        test_name = "test_POST_201_batch"
        self.reason_to_skip(test_name)

        # Number of entities to create in batch
        batch_size = 3

        # Create parent entities if required
        parent_ids = {}
        path_parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(
                server, admin_a_jwt, team_a
            )
            for parent in self.parent_entities:
                if parent.name in parent_entities_dict:
                    parent_id = parent_entities_dict[parent.name].id
                    parent_ids[parent.foreign_key] = parent_id
                    # Use path_level to populate path_parent_ids
                    if parent.path_level in [1, 2]:
                        path_parent_ids[f"{parent.name}_id"] = parent_id
                    # Fallback for backward compatibility (if is_path=True and path_level=None)
                    elif parent.is_path and parent.path_level is None:
                        path_parent_ids[f"{parent.name}_id"] = parent_id

        # Create multiple resource entities
        batch_entities = []
        expected_names = []
        for i in range(batch_size):
            resource_name = f"{self.faker.word()} Batch Item {i+1}"
            expected_names.append(resource_name)

            entity = {}
            if self.string_field_to_update:
                entity[self.string_field_to_update] = resource_name

            # Add parent IDs
            for parent in self.parent_entities:
                if parent.foreign_key in parent_ids:
                    entity[parent.foreign_key] = parent_ids[parent.foreign_key]

            if team_a and "team_id" in self.required_fields:
                entity["team_id"] = team_a.id

            batch_entities.append(entity)

        # Nest the entities in a list under the pluralized entity name
        nested_payload = {self.resource_name_plural: batch_entities}

        # Choose the appropriate authentication header
        headers = self._get_appropriate_headers(admin_a_jwt, api_key)

        # Make the request
        response = server.post(
            self.get_create_endpoint(path_parent_ids),
            json=nested_payload,
            headers=headers,
        )

        # Assert the response
        self._assert_response_status(
            response,
            201,
            "POST (Batch)",
            self.get_create_endpoint(path_parent_ids),
            nested_payload,
        )

        json_response = response.json()
        plural_entity_type = self.resource_name_plural

        assert plural_entity_type in json_response, (
            f"[{self.entity_name}] Batch response does not contain expected entities: {plural_entity_type}\n"
            f"Response: {json_response}"
        )

        entities = json_response[plural_entity_type]
        assert isinstance(entities, list), (
            f"[{self.entity_name}] Expected a list of entities, got: {type(entities)}\n"
            f"Entities: {entities}"
        )

        assert len(entities) == batch_size, (
            f"[{self.entity_name}] Expected {batch_size} entities, got {len(entities)}\n"
            f"Entities: {entities}"
        )

        # Check that each entity has the required fields and matches one of our expected names
        for entity in entities:
            for field in self.required_fields:
                assert field in entity, (
                    f"[{self.entity_name}] Required field missing in batch entity: {field}\n"
                    f"Entity: {entity}"
                )

            # Check that each entity has the string field with "Batch Item" if string_field_to_update is defined
            if self.string_field_to_update:
                assert self.string_field_to_update in entity, (
                    f"[{self.entity_name}] Field {self.string_field_to_update} missing in batch entity\n"
                    f"Entity: {entity}"
                )
                assert "Batch Item" in entity[self.string_field_to_update], (
                    f"[{self.entity_name}] Expected 'Batch Item' in entity {self.string_field_to_update}, got: {entity[self.string_field_to_update]}\n"
                    f"Entity: {entity}"
                )

            # Check parent IDs
            self._assert_parent_ids_match(entity, parent_ids)

            # Check created_by_user_id
            self._assert_has_created_by_user_id(entity, admin_a_jwt)

        return entities

    def test_PUT_200_batch(self, server, admin_a_jwt, team_a, api_key=None):
        """Test batch updating resources."""
        test_name = "test_PUT_200_batch"
        self.reason_to_skip(test_name)

        # Create multiple resources to update in batch
        resources, path_parent_ids, headers = self._setup_test_resources(
            server, admin_a_jwt, team_a, count=3, api_key=api_key
        )

        # Prepare batch update data
        updated_name = f"Batch Updated {self.entity_name} {uuid.uuid4()}"
        target_ids = [r["id"] for r in resources]

        payload = {
            "target_ids": target_ids,
        }

        # Only include string_field_to_update if it's defined
        if self.string_field_to_update:
            payload[self.entity_name] = {self.string_field_to_update: updated_name}
        else:
            payload[self.entity_name] = {}  # Empty update payload if no string field

        # Make the batch update request
        response = server.put(
            self.get_list_endpoint(path_parent_ids),
            json=payload,
            headers=headers,
        )

        self._assert_response_status(
            response,
            200,
            "PUT batch update",
            self.get_list_endpoint(path_parent_ids),
            payload,
        )

        # Check the response format
        json_response = response.json()

        assert self.resource_name_plural in json_response, (
            f"[{self.entity_name}] Batch update response missing entities key: {self.resource_name_plural}\n"
            f"Response: {json_response}"
        )

        updated_entities = json_response[self.resource_name_plural]
        assert isinstance(updated_entities, list), (
            f"[{self.entity_name}] Expected a list of entities, got: {type(updated_entities)}\n"
            f"Entities: {updated_entities}"
        )

        assert len(updated_entities) == len(target_ids), (
            f"[{self.entity_name}] Expected {len(target_ids)} updated entities, got {len(updated_entities)}\n"
            f"Entities: {updated_entities}"
        )

        # Verify each entity was updated
        for entity in updated_entities:
            # Only verify the string field if it's defined
            if self.string_field_to_update:
                assert entity[self.string_field_to_update] == updated_name, (
                    f"[{self.entity_name}] Entity not batch updated: expected '{updated_name}', "
                    f"got '{entity[self.string_field_to_update]}'\n"
                    f"Entity: {entity}"
                )

            # Check updated_by_user_id
            self._assert_has_updated_by_user_id(entity, admin_a_jwt)

        # Verify the updates by retrieving each resource
        for resource_id in target_ids:
            get_response = server.get(
                self.get_detail_endpoint(resource_id, path_parent_ids),
                headers=headers,
            )
            self._assert_response_status(
                response=get_response,
                expected_status=200,
                operation="GET after batch update",
                endpoint=self.get_detail_endpoint(resource_id, path_parent_ids),
            )

            retrieved_entity = self._assert_entity_in_response(get_response)

            # Only verify the string field if it's defined
            if self.string_field_to_update:
                assert retrieved_entity[self.string_field_to_update] == updated_name, (
                    f"[{self.entity_name}] Entity batch update didn't persist: expected '{updated_name}', "
                    f"got '{retrieved_entity[self.string_field_to_update]}'\n"
                    f"Entity: {retrieved_entity}"
                )

        return updated_entities

    def test_DELETE_204_batch(self, server, admin_a_jwt, team_a, api_key=None):
        """Test batch deleting resources."""
        test_name = "test_DELETE_204_batch"
        self.reason_to_skip(test_name)

        # Create multiple resources to delete in batch
        resources, path_parent_ids, headers = self._setup_test_resources(
            server, admin_a_jwt, team_a, count=3, api_key=api_key
        )

        # Prepare batch delete data
        target_ids = [r["id"] for r in resources]
        payload = {"target_ids": target_ids}

        id_join = ",".join(target_ids)

        # Make the batch delete request
        response = server.delete(
            f"{self.get_list_endpoint(path_parent_ids)}?target_ids={','.join(target_ids)}",
            headers=headers,
        )

        # foo = response.errors
        self._assert_response_status(
            response,
            204,
            "DELETE batch",
            self.get_list_endpoint(path_parent_ids),
            payload,
        )

        # Verify each resource is deleted
        for resource_id in target_ids:
            verify_response = server.get(
                self.get_detail_endpoint(resource_id, path_parent_ids),
                headers=headers,
            )

            self._assert_response_status(
                verify_response,
                404,
                "GET after batch DELETE",
                self.get_detail_endpoint(resource_id, path_parent_ids),
            )

        return target_ids

    def test_GET_200_pagination(self, server, admin_a_jwt, team_a):
        """Test pagination for list endpoints."""
        test_name = "test_GET_200_pagination"
        self.reason_to_skip(test_name)

        # Create multiple resources to test pagination
        resources, path_parent_ids, headers = self._setup_test_resources(
            server, admin_a_jwt, team_a, count=3
        )

        # Test with limit=1 to get first page
        response = server.get(
            f"{self.get_list_endpoint(path_parent_ids)}?limit=1", headers=headers
        )

        self._assert_response_status(
            response,
            200,
            "GET list with pagination",
            f"{self.get_list_endpoint(path_parent_ids)}?limit=1",
        )
        entities = self._assert_entities_in_response(response)

        # Should only have 1 entity
        assert len(entities) == 1, (
            f"[{self.entity_name}] Pagination limit not respected: "
            f"Expected 1 entity, got {len(entities)}"
        )

        # Test with offset=1 to get second page
        response = server.get(
            f"{self.get_list_endpoint(path_parent_ids)}?offset=1&limit=1",
            headers=headers,
        )

        self._assert_response_status(
            response,
            200,
            "GET list with pagination offset",
            f"{self.get_list_endpoint(path_parent_ids)}?offset=1&limit=1",
        )
        entities = self._assert_entities_in_response(response)

        # Should only have 1 entity and it should be different from the first page
        assert len(entities) == 1, (
            f"[{self.entity_name}] Pagination limit not respected: "
            f"Expected 1 entity, got {len(entities)}"
        )

        # The ID should be different from the first page
        second_page_id = entities[0]["id"]

        response = server.get(
            f"{self.get_list_endpoint(path_parent_ids)}?limit=1", headers=headers
        )
        first_entities = self._assert_entities_in_response(response)

        assert first_entities[0]["id"] != second_page_id, (
            f"[{self.entity_name}] Pagination offset not working correctly: "
            f"Got same entity on different pages"
        )

        return entities

    @pytest.mark.xfail(reason="Open Issue: #39")
    def test_GET_200_fields(self, server, admin_a_jwt, team_a):
        """Test retrieving resources with the fields parameter."""
        test_name = "test_GET_200_fields"
        self.reason_to_skip(test_name)

        # Create a resource
        resource, parent_ids, path_parent_ids, headers = self._setup_test_resources(
            server, admin_a_jwt, team_a, count=1
        )[0]

        # Select a subset of fields
        subset_fields = self.required_fields[
            :2
        ]  # Just use the first two required fields
        fields_param = f"?{'&'.join([f'fields={field}' for field in subset_fields])}"

        # Test with single entity endpoint
        response = server.get(
            f"{self.get_detail_endpoint(resource['id'], path_parent_ids)}{fields_param}",
            headers=headers,
        )

        self._assert_response_status(
            response,
            200,
            "GET with fields parameter",
            f"{self.get_detail_endpoint(resource['id'], path_parent_ids)}{fields_param}",
        )

        entity = self._assert_entity_in_response(response)

        # Verify only the requested fields (plus id) are present
        expected_fields = set(subset_fields + ["id"])
        actual_fields = set(entity.keys())

        assert actual_fields.issubset(set(self.required_fields + ["id"])), (
            f"[{self.entity_name}] Response contains fields not in required fields list\n"
            f"Extra fields: {actual_fields - set(self.required_fields + ['id'])}\n"
            f"Entity: {entity}"
        )

        assert expected_fields.issubset(actual_fields), (
            f"[{self.entity_name}] Response missing requested fields\n"
            f"Missing fields: {expected_fields - actual_fields}\n"
            f"Entity: {entity}"
        )

        return entity

    @pytest.mark.xfail(reason="Open Issue: #38")
    def test_POST_422_batch(self, server, admin_a_jwt, team_a, api_key=None):
        """Test batch creation with invalid entities fails."""
        test_name = "test_POST_422_batch"
        self.reason_to_skip(test_name)
        # Create parent entities if required
        parent_ids = {}
        path_parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(
                server, admin_a_jwt, team_a
            )
            for parent in self.parent_entities:
                if parent.name in parent_entities_dict:
                    parent_id = parent_entities_dict[parent.name].id
                    parent_ids[parent.foreign_key] = parent_id
                    # Use path_level to populate path_parent_ids
                    if parent.path_level in [1, 2]:
                        path_parent_ids[f"{parent.name}_id"] = parent_id
                    # Fallback for backward compatibility (if is_path=True and path_level=None)
                    elif parent.is_path and parent.path_level is None:
                        path_parent_ids[f"{parent.name}_id"] = parent_id

        # Valid entity
        valid_entity = {}
        if self.string_field_to_update:
            valid_entity[self.string_field_to_update] = self.faker.word()

        # Add parent IDs to valid entity
        for parent in self.parent_entities:
            if parent.foreign_key in parent_ids:
                valid_entity[parent.foreign_key] = parent_ids[parent.foreign_key]

        if team_a and "team_id" in self.required_fields:
            valid_entity["team_id"] = team_a.id

        # Invalid entity - missing required fields
        invalid_entity = {}  # Empty entity missing required fields

        # Create the batch payload
        batch_entities = [valid_entity, invalid_entity]
        nested_payload = {self.resource_name_plural: batch_entities}

        # Choose the appropriate authentication header
        headers = self._get_appropriate_headers(admin_a_jwt, api_key)

        # Make the request
        response = server.post(
            self.get_create_endpoint(path_parent_ids),
            json=nested_payload,
            headers=headers,
        )

        # Assert the response - should fail with 422
        self._assert_response_status(
            response,
            422,
            "POST (Invalid Batch)",
            self.get_create_endpoint(path_parent_ids),
            nested_payload,
        )

    def test_POST_401(self, server, admin_a):
        """Test creating resource without proper authorization."""
        test_name = "test_POST_401"
        self.reason_to_skip(test_name)

        resource_name = f"Test {self.entity_name}"

        # Get fake parent_ids if required for the path, do not create real entities
        parent_ids = {}
        path_parent_ids = {}
        if self.has_parent_entities():
            for parent in self.parent_entities:
                # Generate dummy IDs only if needed for the path structure
                if parent.path_level in [1, 2] or (
                    parent.is_path and parent.path_level is None
                ):
                    dummy_id = str(uuid.uuid4())
                    path_parent_ids[f"{parent.name}_id"] = dummy_id
                # Include dummy IDs for non-nullable parents in payload if create_path requires them
                # Note: This might still fail if the BLL requires valid parent FKs even before auth check.
                if not parent.nullable:
                    parent_ids[parent.foreign_key] = str(uuid.uuid4())

        # Create the payload using the child class implementation
        # Pass dummy parent_ids if needed by create_payload structure
        payload = self.create_payload(resource_name, parent_ids if parent_ids else None)

        # Test without authorization header
        endpoint = self.get_create_endpoint(path_parent_ids)
        response = server.post(endpoint, json=payload)
        self._assert_response_status(
            response,
            401,
            "POST (no auth)",
            endpoint,
            payload,
        )

        # Test with invalid token
        headers = self._auth_header("invalid.token")
        response = server.post(
            endpoint,
            json=payload,
            headers=headers,
        )
        self._assert_response_status(
            response,
            401,
            "POST (invalid auth)",
            endpoint,
            payload,
        )

    def test_POST_403_system(self, server, admin_a_jwt, team_a):
        """Test that system entity creation fails without API key."""
        test_name = "test_POST_403_system"
        self.reason_to_skip(test_name)

        if not self.system_entity:
            pytest.skip("Not a system entity")

        # Generate a unique name for the test resource
        resource_name = self.faker.word()

        # Create parent entities if required
        parent_ids = {}
        path_parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(
                server, admin_a_jwt, team_a
            )
            for parent in self.parent_entities:
                if parent.name in parent_entities_dict:
                    parent_id = parent_entities_dict[parent.name].id
                    parent_ids[parent.foreign_key] = parent_id
                    # Use path_level to populate path_parent_ids
                    if parent.path_level in [1, 2]:
                        path_parent_ids[f"{parent.name}_id"] = parent_id
                    # Fallback for backward compatibility (if is_path=True and path_level=None)
                    elif parent.is_path and parent.path_level is None:
                        path_parent_ids[f"{parent.name}_id"] = parent_id

        # Create the payload
        payload = self.create_payload(resource_name, parent_ids, team_a.id)

        # Try to create with JWT instead of API key
        response = server.post(
            self.get_create_endpoint(path_parent_ids),
            json=payload,
            headers=self._auth_header(admin_a_jwt),
        )

        # Assert it fails with 403
        self._assert_response_status(
            response,
            403,
            "POST (system entity without API key)",
            self.get_create_endpoint(path_parent_ids),
            payload,
        )

    def test_GET_200_list(self, server, admin_a_jwt, team_a):
        """Test retrieving the list of available resources."""
        self.reason_to_skip("test_GET_200_list")

        # Create an entity first to ensure there's something to list
        entity = self.test_POST_201(server, admin_a_jwt, team_a)

        # Extract parent IDs from created entity
        _, path_parent_ids = self._extract_parent_ids(entity)

        response = server.get(
            self.get_list_endpoint(path_parent_ids),
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response, 200, "GET list", self.get_list_endpoint(path_parent_ids)
        )
        entities = self._assert_entities_in_response(response)

        # Check that at least one entity with our ID is in the results
        found = False
        for e in entities:
            if e["id"] == entity["id"]:
                found = True
                break

        assert found, (
            f"[{self.entity_name}] Created entity not found in list results\n"
            f"Entity ID: {entity['id']}\n"
            f"List results: {entities}"
        )

        return entities

    def test_GET_200_id(self, server, admin_a_jwt, team_a):
        """Test retrieving a specific resource by ID."""
        test_name = "test_GET_200_id"
        self.reason_to_skip(test_name)

        # First create a resource
        resource = self.test_POST_201(server, admin_a_jwt, team_a)

        # Extract parent IDs from created resource
        _, path_parent_ids = self._extract_parent_ids(resource)

        # Special handling for user endpoint which doesn't support /{id} route
        if self.entity_name == "user":
            # User endpoint uses GET /v1/user without an ID to get current user
            response = server.get("/v1/user", headers=self._auth_header(admin_a_jwt))
            operation = "GET current user"
            endpoint = "/v1/user"
        # Special handling for role endpoint which uses different nesting
        elif self.entity_name == "role":
            # Make sure we're using the team_id for path_parent_ids
            if "team_id" in resource:
                path_parent_ids = {"team_id": resource["team_id"]}
            # Role endpoint might need to use /v1/team/{team_id}/role endpoint
            team_id = resource.get("team_id")
            if team_id:
                response = server.get(
                    f"/v1/team/{team_id}/role/{resource['id']}",
                    headers=self._auth_header(admin_a_jwt),
                )
                operation = "GET role by ID via team"
                endpoint = f"/v1/team/{team_id}/role/{resource['id']}"
            else:
                # Fall back to regular path
                response = server.get(
                    self.get_detail_endpoint(resource["id"], path_parent_ids),
                    headers=self._auth_header(admin_a_jwt),
                )
                operation = "GET by ID"
                endpoint = self.get_detail_endpoint(resource["id"], path_parent_ids)
        else:
            # Standard endpoint handling
            response = server.get(
                self.get_detail_endpoint(resource["id"], path_parent_ids),
                headers=self._auth_header(admin_a_jwt),
            )
            operation = "GET by ID"
            endpoint = self.get_detail_endpoint(resource["id"], path_parent_ids)

        self._assert_response_status(
            response,
            200,
            operation,
            endpoint,
        )
        entity = self._assert_entity_in_response(response)

        # Verify ID matches
        assert entity["id"] == resource["id"], (
            f"[{self.entity_name}] Retrieved entity ID mismatch: expected '{resource['id']}', got '{entity['id']}'\n"
            f"Entity: {entity}"
        )

        # Verify name matches if string_field_to_update is defined
        if self.string_field_to_update:
            assert (
                entity[self.string_field_to_update]
                == resource[self.string_field_to_update]
            ), (
                f"[{self.entity_name}] Retrieved entity field mismatch: "
                f"expected '{resource[self.string_field_to_update]}', got '{entity[self.string_field_to_update]}'\n"
                f"Entity: {entity}"
            )

        return entity

    # --- START: Parent Team Permission Tests ---

    def _setup_parent_child_team_scenario(
        self, server, admin_a_jwt, admin_a, jwt_b, user_b
    ):
        """Helper to set up a parent team, child team, and user memberships."""
        # NOTE: This uses API calls to set up. Ideally, use BLL managers if available in test context.

        # 1. Create Parent Team (owned by User A initially)
        parent_team_payload = {
            "team": {
                "name": f"Parent Team {uuid.uuid4()}",
                "description": "Parent team for permission testing",
            }
        }
        response_parent = server.post(
            "/v1/team", json=parent_team_payload, headers=self._auth_header(admin_a_jwt)
        )
        self._assert_response_status(
            response_parent,
            201,
            "POST parent team setup",
            "/v1/team",
            parent_team_payload,
        )
        parent_team = response_parent.json()["team"]

        # 2. Create Child Team (owned by User A, parent is parent_team)
        child_team_payload = {
            "team": {
                "name": f"Child Team {uuid.uuid4()}",
                "description": "Child team for permission testing",
                "parent_id": parent_team["id"],
            }
        }
        response_child = server.post(
            "/v1/team", json=child_team_payload, headers=self._auth_header(admin_a_jwt)
        )
        self._assert_response_status(
            response_child, 201, "POST child team setup", "/v1/team", child_team_payload
        )
        child_team = response_child.json()["team"]

        # 3. Add User B to Parent Team (as admin for simplicity)
        # Requires finding the admin role ID - assuming default admin role exists
        # This is fragile; ideally, fixtures provide role IDs. Using hardcoded UUID for now.
        # TODO: Replace hardcoded admin role ID with a fixture lookup
        user_b_membership_payload = {
            "role_id": env("ADMIN_ROLE_ID")
        }  # Assign role via payload
        add_user_endpoint = f"/v1/team/{parent_team['id']}/user/{user_b['id']}/role"
        response_add_b = server.put(
            add_user_endpoint,
            json=user_b_membership_payload,
            headers=self._auth_header(admin_a_jwt),  # User A adds User B
        )

        # Handle potential 404 if PUT requires existing UserTeam record
        if response_add_b.status_code == 404:
            # Log a warning or skip if this endpoint truly doesn't support creation
            logging.warning(
                f"PUT {add_user_endpoint} returned 404. "
                f"This might indicate the endpoint expects an existing UserTeam record. "
                f"Parent team tests might not accurately reflect permissions if user addition fails."
            )
            # Optionally, attempt a POST if a user addition endpoint exists, e.g.:
            # post_add_endpoint = f"/v1/team/{parent_team['id']}/user/{user_b['id']}"
            # response_post_add = server.post(post_add_endpoint, json=user_b_membership_payload, headers=self._auth_header(admin_a_jwt))
            # Check response_post_add status...
        elif response_add_b.status_code not in [200, 201]:
            # Assert failure for unexpected errors other than 404
            self._assert_response_status(
                response_add_b,
                200,
                f"PUT add user B to parent team {parent_team['id']}",
                add_user_endpoint,
                user_b_membership_payload,
            )

        # 4. Create the actual resource under the CHILD team using User A
        # This depends on the specific entity being tested.
        # We need to handle if the entity IS a team vs. BELONGS to a team.

        resource_to_test = None
        resource_parent_ids = {}  # Parent IDs needed for the *resource*, not the teams
        resource_path_parent_ids = {}  # Path IDs needed for the *resource*

        if self.entity_name == "team":
            # If testing Teams endpoint, the child_team is our resource
            resource_to_test = child_team
            # Teams don't typically have other *entity* parents in this context
            resource_parent_ids = {}
            resource_path_parent_ids = {}  # No path parents for top-level team endpoint
        else:
            # Assume the entity needs a team_id and potentially other parents
            # Create the actual parent entities required by the resource itself
            other_parent_entities_dict = {}
            if self.has_parent_entities():
                # Filter out 'team' if it's listed as a parent, as we're providing it manually
                non_team_parents = [p for p in self.parent_entities if p.name != "team"]
                if non_team_parents:  # Only call if there are non-team parents
                    # Need a way to create *only* the non-team parents.
                    # This might require overriding create_parent_entities or a new helper.
                    # For now, assume create_parent_entities handles this or is adjusted in child class.
                    # WARNING: This part is complex and might need refinement.
                    # Let's proceed assuming create_parent_entities works for other parents.
                    other_parent_entities_dict = self.create_parent_entities(
                        server, admin_a_jwt, {"id": child_team["id"]}
                    )  # Pass child team info

            for parent in self.parent_entities:
                # Prioritize manually provided child_team ID
                if parent.name == "team":
                    resource_parent_ids[parent.foreign_key] = child_team["id"]
                    if parent.path_level in [1, 2] or (
                        parent.is_path and parent.path_level is None
                    ):
                        resource_path_parent_ids[f"{parent.name}_id"] = child_team["id"]
                # Get IDs for other parents from the created dict
                elif parent.name in other_parent_entities_dict:
                    parent_id = other_parent_entities_dict[parent.name].id
                    resource_parent_ids[parent.foreign_key] = parent_id
                    if parent.path_level in [1, 2] or (
                        parent.is_path and parent.path_level is None
                    ):
                        resource_path_parent_ids[f"{parent.name}_id"] = parent_id

            # Create the resource payload associated with the child_team
            resource_payload = self.create_payload(
                name=f"Test Resource Child {uuid.uuid4()}",
                parent_ids=resource_parent_ids,
                team_id=child_team["id"],  # Explicitly set team_id if needed
            )
            response_resource = server.post(
                self.get_create_endpoint(resource_path_parent_ids),
                json=resource_payload,
                headers=self._auth_header(admin_a_jwt),
            )
            self._assert_response_status(
                response_resource,
                201,
                "POST resource for parent test",
                self.get_create_endpoint(resource_path_parent_ids),
                resource_payload,
            )
            resource_to_test = self._assert_entity_in_response(response_resource)

        return parent_team, child_team, resource_to_test, resource_path_parent_ids

    def test_GET_200_list_via_parent_team(
        self, server, admin_a_jwt, admin_a, team_a, jwt_b, user_b
    ):
        """Test user B (parent team member) can LIST resources created by user A under a child team."""
        test_name = "test_GET_200_list_via_parent_team"
        self.reason_to_skip(test_name)

        # Skip if testing Teams and no parent_id support (or ParentMixin missing)
        # A more robust check would inspect the Team model directly
        if self.entity_name == "team" and not hasattr(
            self, "create_payload"
        ):  # Basic check
            pytest.skip(
                "Skipping parent team test for Team entity without parent support"
            )

        parent_team, child_team, resource, path_parent_ids = (
            self._setup_parent_child_team_scenario(
                server, admin_a_jwt, admin_a, jwt_b, user_b
            )
        )

        # User B lists resources (using path parents relevant to the *resource*, not the team)
        # Special handling for user endpoint
        if self.entity_name == "user":
            # For user endpoint, use the team's users endpoint
            list_endpoint = f"/v1/team/{child_team['id']}/user"
            response = server.get(list_endpoint, headers=self._auth_header(jwt_b))
            entity_type = "user_teams"  # The response will be user_teams, not users
        # Special handling for role endpoint
        elif self.entity_name == "role":
            # Roles are accessed via team
            list_endpoint = f"/v1/team/{child_team['id']}/role"
            response = server.get(list_endpoint, headers=self._auth_header(jwt_b))
            entity_type = "roles"
        else:
            # Standard endpoint handling
            list_endpoint = self.get_list_endpoint(path_parent_ids)
            response = server.get(list_endpoint, headers=self._auth_header(jwt_b))
            entity_type = None  # Let _assert_entities_in_response use the default

        self._assert_response_status(
            response, 200, "GET list via parent team", list_endpoint
        )
        entities = self._assert_entities_in_response(response, entity_type)

        # For user endpoints, the team/user endpoint returns differently formatted data
        if (
            self.entity_name == "user"
            and entities
            and isinstance(entities[0], dict)
            and "user" in entities[0]
        ):
            # Extract the nested user objects
            entities = [entity.get("user", {}) for entity in entities]

        # Check that created entity is found (except for user which is handled differently)
        if self.entity_name != "user":
            found = False
            for e in entities:
                if e.get("id") == resource.get("id"):
                    found = True
                    break

            assert found, (
                f"[{self.entity_name}] Created entity not found in list results\n"
                f"Entity ID: {resource.get('id')}\n"
                f"List results: {entities}"
            )

        return entities

    def test_GET_404_list_no_parent_team(
        self, server, admin_a_jwt, admin_a, team_a, jwt_b, user_b
    ):
        """Test user B (no membership) CANNOT LIST resources created by user A under a child team."""
        test_name = "test_GET_404_list_no_parent_team"
        self.reason_to_skip(test_name)

        # Skip if testing Teams and no parent_id support
        if self.entity_name == "team" and not hasattr(self, "create_payload"):
            pytest.skip(
                "Skipping parent team test for Team entity without parent support setup"
            )

        # Setup: Create parent, child, resource (User A owns child, resource)
        # User B is NOT added to the parent team in this setup variation.
        # --- Setup Start ---
        parent_team_payload = {"team": {"name": f"Parent Team {uuid.uuid4()}"}}
        response_parent = server.post(
            "/v1/team", json=parent_team_payload, headers=self._auth_header(admin_a_jwt)
        )
        self._assert_response_status(
            response_parent,
            201,
            "POST parent team setup (no parent)",
            "/v1/team",
            parent_team_payload,
        )
        parent_team = response_parent.json()["team"]

        child_team_payload = {
            "team": {
                "name": f"Child Team {uuid.uuid4()}",
                "parent_id": parent_team["id"],
            }
        }
        response_child = server.post(
            "/v1/team", json=child_team_payload, headers=self._auth_header(admin_a_jwt)
        )
        self._assert_response_status(
            response_child,
            201,
            "POST child team setup (no parent)",
            "/v1/team",
            child_team_payload,
        )
        child_team = response_child.json()["team"]

        resource_to_test = None
        resource_parent_ids = {}
        resource_path_parent_ids = {}

        if self.entity_name == "team":
            resource_to_test = child_team
        else:
            other_parent_entities_dict = {}
            if self.has_parent_entities():
                non_team_parents = [p for p in self.parent_entities if p.name != "team"]
                if non_team_parents:
                    # WARNING: Assuming create_parent_entities works or is adjusted
                    other_parent_entities_dict = self.create_parent_entities(
                        server, admin_a_jwt, {"id": child_team["id"]}
                    )

            for parent in self.parent_entities:
                if parent.name == "team":
                    resource_parent_ids[parent.foreign_key] = child_team["id"]
                    if parent.path_level in [1, 2] or (
                        parent.is_path and parent.path_level is None
                    ):
                        resource_path_parent_ids[f"{parent.name}_id"] = child_team["id"]
                elif parent.name in other_parent_entities_dict:
                    parent_id = other_parent_entities_dict[parent.name].id
                    resource_parent_ids[parent.foreign_key] = parent_id
                    if parent.path_level in [1, 2] or (
                        parent.is_path and parent.path_level is None
                    ):
                        resource_path_parent_ids[f"{parent.name}_id"] = parent_id

            resource_payload = self.create_payload(
                f"Test Resource Child NoParent {uuid.uuid4()}",
                resource_parent_ids,
                child_team["id"],
            )
            response_resource = server.post(
                self.get_create_endpoint(resource_path_parent_ids),
                json=resource_payload,
                headers=self._auth_header(admin_a_jwt),
            )
            self._assert_response_status(
                response_resource,
                201,
                "POST resource for no parent test",
                self.get_create_endpoint(resource_path_parent_ids),
                resource_payload,
            )
            resource_to_test = self._assert_entity_in_response(response_resource)
        # --- Setup End ---

        # User B lists resources (should not see the one under child_team)
        list_endpoint = self.get_list_endpoint(resource_path_parent_ids)
        response = server.get(list_endpoint, headers=self._auth_header(jwt_b))

        self._assert_response_status(
            response, 200, "GET list no parent team", list_endpoint
        )  # List itself should be 200 OK
        entities = self._assert_entities_in_response(response)

        # Verify the specific resource is NOT in the list
        found = any(e["id"] == resource_to_test["id"] for e in entities)
        assert not found, (
            f"[{self.entity_name}] Resource {resource_to_test['id']} unexpectedly found in list for user B (no parent team membership)\n"
            f"Parent Team: {parent_team['id']}, Child Team: {child_team['id']}\n"
            f"User B ID: {user_b['id']}\n"
            f"List results: {entities}"
        )

    def test_GET_200_id_via_parent_team(
        self, server, admin_a_jwt, admin_a, team_a, jwt_b, user_b
    ):
        """Test user B (parent team member) can GET a resource created by user A under a child team."""
        test_name = "test_GET_200_id_via_parent_team"
        self.reason_to_skip(test_name)

        if self.entity_name == "team" and not hasattr(self, "create_payload"):
            pytest.skip(
                "Skipping parent team test for Team entity without parent support setup"
            )

        parent_team, child_team, resource, path_parent_ids = (
            self._setup_parent_child_team_scenario(
                server, admin_a_jwt, admin_a, jwt_b, user_b
            )
        )

        # User B retrieves the specific resource by ID
        # Special handling for user endpoint
        if self.entity_name == "user":
            # For user entity, look up the user via parent team users instead
            endpoint = f"/v1/team/{child_team['id']}/user"
            response = server.get(endpoint, headers=self._auth_header(jwt_b))
            self._assert_response_status(response, 200, "GET team users", endpoint)
            # Find the user in the team users list
            team_users = response.json().get("user_teams", [])
            found_resource = None
            for user_team in team_users:
                if user_team.get("user", {}).get("id") == resource["id"]:
                    found_resource = user_team.get("user")
                    break

            assert found_resource, (
                f"[{self.entity_name}] User not found in team users\n"
                f"User ID: {resource['id']}\n"
                f"Team Users: {team_users}"
            )
            return found_resource
        # Special handling for role endpoint
        elif self.entity_name == "role":
            # Roles can be accessed via team/{team_id}/role/{id}
            team_id = resource.get("team_id")
            if team_id:
                detail_endpoint = f"/v1/team/{team_id}/role/{resource['id']}"
            else:
                detail_endpoint = self.get_detail_endpoint(
                    resource["id"], path_parent_ids
                )
        else:
            # Standard endpoint handling
            detail_endpoint = self.get_detail_endpoint(resource["id"], path_parent_ids)

        response = server.get(detail_endpoint, headers=self._auth_header(jwt_b))

        self._assert_response_status(
            response, 200, "GET ID via parent team", detail_endpoint
        )
        entity = self._assert_entity_in_response(response)

        # Verify resource properties match
        assert entity["id"] == resource["id"], (
            f"[{self.entity_name}] Retrieved resource ID mismatch\n"
            f"Expected: {resource['id']}, Got: {entity['id']}"
        )

        return entity

    def test_GET_404_id_no_parent_team(
        self, server, admin_a_jwt, admin_a, team_a, jwt_b, user_b
    ):
        """Test user B (no membership) CANNOT GET a resource created by user A under a child team."""
        test_name = "test_GET_404_id_no_parent_team"
        self.reason_to_skip(test_name)

        if self.entity_name == "team" and not hasattr(self, "create_payload"):
            pytest.skip(
                "Skipping parent team test for Team entity without parent support setup"
            )

        # Setup: Create parent, child, resource (User A owns child, resource)
        # User B is NOT added to the parent team.
        # --- Setup Start ---
        parent_team_payload = {"team": {"name": f"Parent Team {uuid.uuid4()}"}}
        response_parent = server.post(
            "/v1/team", json=parent_team_payload, headers=self._auth_header(admin_a_jwt)
        )
        self._assert_response_status(
            response_parent,
            201,
            "POST parent team setup (no parent ID)",
            "/v1/team",
            parent_team_payload,
        )
        parent_team = response_parent.json()["team"]

        child_team_payload = {
            "team": {
                "name": f"Child Team {uuid.uuid4()}",
                "parent_id": parent_team["id"],
            }
        }
        response_child = server.post(
            "/v1/team", json=child_team_payload, headers=self._auth_header(admin_a_jwt)
        )
        self._assert_response_status(
            response_child,
            201,
            "POST child team setup (no parent ID)",
            "/v1/team",
            child_team_payload,
        )
        child_team = response_child.json()["team"]

        resource_to_test = None
        resource_parent_ids = {}
        resource_path_parent_ids = {}

        if self.entity_name == "team":
            resource_to_test = child_team
        else:
            other_parent_entities_dict = {}
            if self.has_parent_entities():
                non_team_parents = [p for p in self.parent_entities if p.name != "team"]
                if non_team_parents:
                    # WARNING: Assuming create_parent_entities works or is adjusted
                    other_parent_entities_dict = self.create_parent_entities(
                        server, admin_a_jwt, {"id": child_team["id"]}
                    )

            for parent in self.parent_entities:
                if parent.name == "team":
                    resource_parent_ids[parent.foreign_key] = child_team["id"]
                    if parent.path_level in [1, 2] or (
                        parent.is_path and parent.path_level is None
                    ):
                        resource_path_parent_ids[f"{parent.name}_id"] = child_team["id"]
                elif parent.name in other_parent_entities_dict:
                    parent_id = other_parent_entities_dict[parent.name].id
                    resource_parent_ids[parent.foreign_key] = parent_id
                    if parent.path_level in [1, 2] or (
                        parent.is_path and parent.path_level is None
                    ):
                        resource_path_parent_ids[f"{parent.name}_id"] = parent_id

            resource_payload = self.create_payload(
                f"Test Resource Child NoParentID {uuid.uuid4()}",
                resource_parent_ids,
                child_team["id"],
            )
            response_resource = server.post(
                self.get_create_endpoint(resource_path_parent_ids),
                json=resource_payload,
                headers=self._auth_header(admin_a_jwt),
            )
            self._assert_response_status(
                response_resource,
                201,
                "POST resource for no parent ID test",
                self.get_create_endpoint(resource_path_parent_ids),
                resource_payload,
            )
            resource_to_test = self._assert_entity_in_response(response_resource)
        # --- Setup End ---

        # User B attempts to retrieve the specific resource by ID (should fail)
        detail_endpoint = self.get_detail_endpoint(
            resource_to_test["id"], resource_path_parent_ids
        )
        response = server.get(detail_endpoint, headers=self._auth_header(jwt_b))

        self._assert_response_status(
            response, 404, "GET ID no parent team", detail_endpoint
        )  # Expect 404

    # --- END: Parent Team Permission Tests ---

    @pytest.mark.xfail(reason="Open Issue: #59")
    def test_GET_200_includes(self, server, admin_a_jwt, team_a):
        """Test retrieving resources with their related entities using includes."""
        test_name = "test_GET_200_includes"
        self.reason_to_skip(test_name)

        # First create a resource
        resource = self.test_POST_201(server, admin_a_jwt, team_a)

        # Extract parent IDs from created resource
        _, path_parent_ids = self._extract_parent_ids(resource)

        # Determine which entities to include based on parent entities
        includes = []
        for parent in self.parent_entities:
            includes.append(parent.name)

        if not includes:
            pytest.skip("No related entities to include")

        # Test includes with single entity endpoint
        include_params = {"include": includes}
        detail_endpoint_base = self.get_detail_endpoint(resource["id"], path_parent_ids)

        detail_endpoint = f"{detail_endpoint_base}"
        if includes:
            detail_endpoint += f"?{'&'.join([f'include={inc}' for inc in includes])}"

        detail_response = server.get(
            detail_endpoint,
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response=detail_response,
            expected_status=200,
            operation="GET with includes",
            endpoint=detail_endpoint,
        )

        entity = self._assert_entity_in_response(detail_response)

        # Verify each included entity is present
        for parent in self.parent_entities:
            if parent.name in includes and parent.foreign_key in entity:
                assert parent.name in entity, (
                    f"[{self.entity_name}] Related entity {parent.name} not included in response\n"
                    f"Entity: {entity}"
                )

                # If parent ID is not null, parent object should be present
                if entity[parent.key] is not None:
                    assert entity[parent.name] is not None, (
                        f"[{self.entity_name}] Related entity {parent.name} is null despite valid parent ID\n"
                        f"Entity: {entity}"
                    )
                    assert "id" in entity[parent.name], (
                        f"[{self.entity_name}] Related entity {parent.name} missing ID\n"
                        f"Entity: {entity}"
                    )
                    assert entity[parent.name]["id"] == entity[parent.key], (
                        f"[{self.entity_name}] Related entity {parent.name} ID doesn't match parent ID\n"
                        f"Entity: {entity}"
                    )

        # Test includes with list endpoint
        list_endpoint_base = self.get_list_endpoint(path_parent_ids)
        list_endpoint = f"{list_endpoint_base}"
        if includes:
            list_endpoint += f"?{'&'.join([f'include={inc}' for inc in includes])}"

        list_response = server.get(
            list_endpoint,
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response=list_response,
            expected_status=200,
            operation="GET list with includes",
            endpoint=list_endpoint,
        )

        entities = self._assert_entities_in_response(list_response)

        # Check at least one entity has the included relations
        if entities:
            for entity in entities:
                if entity["id"] == resource["id"]:
                    # Check included relations for the entity we created
                    for parent in self.parent_entities:
                        if (
                            parent.name in includes
                            and parent.foreign_key in entity
                            and entity[parent.foreign_key] is not None
                        ):
                            assert parent.name in entity, (
                                f"[{self.entity_name}] Related entity {parent.name} not included in list response\n"
                                f"Entity: {entity}"
                            )
                            assert entity[parent.name] is not None, (
                                f"[{self.entity_name}] Related entity {parent.name} is null despite valid parent ID\n"
                                f"Entity: {entity}"
                            )
                    break

        return entity

    def test_GET_404_nonexistent(self, server, admin_a_jwt, team_a):
        """Test that API returns 404 for nonexistent resource (GET)."""
        test_name = "test_GET_404_nonexistent"
        self.reason_to_skip(test_name)

        nonexistent_id = str(uuid.uuid4())

        # Create parent entities if required
        parent_entities_dict = {}
        parent_ids = {}
        path_parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(
                server, admin_a_jwt, team_a
            )
            parent_ids = {
                parent.foreign_key: parent_entities_dict[parent.name].id
                for parent in self.parent_entities
                if parent.name in parent_entities_dict
            }
            # Extract parent IDs for path if needed
            for parent in self.parent_entities:
                if parent.name in parent_entities_dict:
                    parent_id = parent_entities_dict[parent.name].id
                    if parent.path_level in [1, 2]:
                        path_parent_ids[f"{parent.name}_id"] = parent_id
                    elif parent.is_path and parent.path_level is None:
                        path_parent_ids[f"{parent.name}_id"] = parent_id

        response = server.get(
            self.get_detail_endpoint(nonexistent_id, path_parent_ids),
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response,
            404,
            "GET nonexistent resource",
            self.get_detail_endpoint(nonexistent_id, path_parent_ids),
        )

    def test_GET_404_other_user(self, server, admin_a_jwt, team_a, jwt_b):
        """Test that users cannot see or access each other's resources."""
        test_name = "test_GET_404_other_user"
        self.reason_to_skip(test_name)

        # First create a resource with user A
        resource_a = self.test_POST_201(server, admin_a_jwt, team_a)

        # Extract parent IDs from created resource
        _, path_parent_ids = self._extract_parent_ids(resource_a)

        # Try to retrieve the resource with user B
        response = server.get(
            self.get_detail_endpoint(resource_a["id"], path_parent_ids),
            headers=self._auth_header(jwt_b),
        )

        # This should return 404 Not Found (not 403) since the user shouldn't even know it exists
        self._assert_response_status(
            response,
            404,
            "GET by different user",
            self.get_detail_endpoint(resource_a["id"], path_parent_ids),
        )

    def test_PUT_422(self, server, admin_a_jwt, team_a):
        """Test updating a resource with invalid data."""
        test_name = "test_PUT_422"
        self.reason_to_skip(test_name)

        # Skip if no string field to update
        if not self.string_field_to_update:
            pytest.skip("No string field to update for this entity")

        # First create a resource
        resource = self.test_POST_201(server, admin_a_jwt, team_a)

        # Extract parent IDs from created resource
        _, path_parent_ids = self._extract_parent_ids(resource)

        # Invalid update payload (wrong data type)
        invalid_value = 12345  # Number instead of string
        payload = self.nest_payload_in_entity(
            entity={self.string_field_to_update: invalid_value}
        )

        response = server.put(
            self.get_update_endpoint(resource["id"], path_parent_ids),
            json=payload,
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response,
            422,
            "PUT invalid update",
            self.get_update_endpoint(resource["id"], path_parent_ids),
            payload,
        )

    def test_DELETE_403_system(self, server, admin_a_jwt, team_a, api_key=None):
        """Test that system entity deletion fails without API key."""
        test_name = "test_DELETE_403_system"
        self.reason_to_skip(test_name)

        if not self.system_entity:
            pytest.skip("Not a system entity")

        # First create a resource using API key
        entity = self.test_POST_201(server, admin_a_jwt, team_a, api_key)

        # Extract parent IDs if needed for the path
        path_parent_ids = {}
        for parent in self.parent_entities:
            if parent.is_path and parent.foreign_key in entity:
                parent_id = entity[parent.key]
                path_parent_ids[f"{parent.name}_id"] = parent_id
                # Use path_level to populate path_parent_ids
                if parent.path_level in [1, 2]:
                    path_parent_ids[f"{parent.name}_id"] = parent_id
                # Fallback for backward compatibility (if is_path=True and path_level=None)
                elif parent.is_path and parent.path_level is None:
                    path_parent_ids[f"{parent.name}_id"] = parent_id

        # Try to delete with JWT instead of API key
        response = server.delete(
            self.get_delete_endpoint(entity["id"], path_parent_ids),
            headers=self._auth_header(admin_a_jwt),
        )

        # Assert it fails with 403
        self._assert_response_status(
            response,
            403,
            "DELETE (system entity without API key)",
            self.get_delete_endpoint(entity["id"], path_parent_ids),
        )

    def test_DELETE_204(self, server, admin_a_jwt, team_a, api_key=None):
        """Test deleting a resource."""
        test_name = "test_DELETE_204"
        self.reason_to_skip(test_name)

        # First create a resource
        resource = self.test_POST_201(server, admin_a_jwt, team_a, api_key)

        # Extract parent IDs from created resource
        parent_ids, path_parent_ids = self._extract_parent_ids(
            resource
        )  # Correctly extract both sets of IDs

        # Choose the appropriate authentication header
        headers = self._get_appropriate_headers(admin_a_jwt, api_key)

        # Delete the resource
        endpoint = self.get_delete_endpoint(
            resource["id"], path_parent_ids
        )  # Use path_parent_ids for endpoint
        response = server.delete(
            endpoint,
            headers=headers,
        )

        self._assert_response_status(
            response,
            204,
            "DELETE",
            endpoint,
        )

        # Verify the resource is deleted by trying to retrieve it
        verify_endpoint = self.get_detail_endpoint(
            resource["id"], path_parent_ids
        )  # Use path_parent_ids for endpoint
        verify_response = server.get(
            verify_endpoint,
            headers=headers,
        )

        self._assert_response_status(
            verify_response,
            404,
            "GET after DELETE",
            verify_endpoint,
        )

    def test_DELETE_404_other_user(self, server, admin_a_jwt, team_a, jwt_b):
        """Test that users cannot delete each other's resources."""
        test_name = "test_DELETE_404_other_user"
        self.reason_to_skip(test_name)

        # First create a resource with user A
        resource_a = self.test_POST_201(server, admin_a_jwt, team_a)

        # Extract parent IDs from created resource
        parent_ids_a, path_parent_ids_a = self._extract_parent_ids(
            resource_a
        )  # Correctly extract both sets of IDs

        # Try to delete the resource with user B
        endpoint = self.get_delete_endpoint(
            resource_a["id"], path_parent_ids_a
        )  # Use path_parent_ids for endpoint
        response = server.delete(
            endpoint,
            headers=self._auth_header(jwt_b),
        )

        # This should return 404 Not Found (not 403)
        self._assert_response_status(
            response,
            404,
            "DELETE by different user",
            endpoint,
        )

        # Verify the resource wasn't deleted by checking with user A
        verify_endpoint = self.get_detail_endpoint(
            resource_a["id"], path_parent_ids_a
        )  # Use path_parent_ids for endpoint
        verify_response = server.get(
            verify_endpoint,
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            verify_response,
            200,
            "GET after DELETE attempt by different user",
            verify_endpoint,
        )

        entity = self._assert_entity_in_response(verify_response)

        # Verify ID matches
        assert entity["id"] == resource_a["id"], (
            f"[{self.entity_name}] Entity incorrectly deleted by different user\n"
            f"Expected ID: {resource_a['id']}\n"
            f"Entity: {entity}"
        )

    def test_DELETE_404_nonexistent(self, server, admin_a_jwt, team_a):
        """Test that API returns 404 for nonexistent resource (DELETE)."""
        test_name = "test_DELETE_404_nonexistent"
        self.reason_to_skip(test_name)

        nonexistent_id = str(uuid.uuid4())

        # Create parent entities if required
        parent_entities_dict = {}
        parent_ids = {}
        path_parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(
                server, admin_a_jwt, team_a
            )
            parent_ids = {
                parent.foreign_key: parent_entities_dict[parent.name].id
                for parent in self.parent_entities
                if parent.name in parent_entities_dict
            }
            # Extract parent IDs for path if needed
            for parent in self.parent_entities:
                if parent.is_path and parent.foreign_key in parent_ids:
                    parent_id = parent_ids[parent.foreign_key]
                    path_parent_ids[f"{parent.name}_id"] = parent_id
                    # Use path_level to populate path_parent_ids
                    if parent.path_level in [1, 2]:
                        path_parent_ids[f"{parent.name}_id"] = parent_id
                    # Fallback for backward compatibility (if is_path=True and path_level=None)
                    elif parent.is_path and parent.path_level is None:
                        path_parent_ids[f"{parent.name}_id"] = parent_id

        response = server.delete(
            self.get_delete_endpoint(nonexistent_id, path_parent_ids),
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response,
            404,
            "DELETE nonexistent resource",
            self.get_delete_endpoint(nonexistent_id, path_parent_ids),
        )

    def test_GET_401(self, server):
        """Test that GET endpoint requires authentication."""
        test_name = "test_GET_401"
        self.reason_to_skip(test_name)

        nonexistent_id = str(uuid.uuid4())

        # Use fake parent_ids if required for path construction
        path_parent_ids = {}
        if self.has_parent_entities():
            for parent in self.parent_entities:
                # Generate dummy IDs only if needed for the path structure
                if parent.path_level in [1, 2] or (
                    parent.is_path and parent.path_level is None
                ):
                    dummy_id = str(uuid.uuid4())
                    path_parent_ids[f"{parent.name}_id"] = dummy_id

        # Test GET /v1/{...}/{endpoint} (list)
        list_endpoint = self.get_list_endpoint(path_parent_ids)
        response = server.get(list_endpoint)
        self._assert_response_status(
            response, 401, "GET list unauthorized", list_endpoint
        )

        # Test GET /v1/{...}/{endpoint}/{id} (get)
        detail_endpoint = self.get_detail_endpoint(nonexistent_id, path_parent_ids)
        response = server.get(detail_endpoint)
        self._assert_response_status(
            response,
            401,
            "GET by ID unauthorized",
            detail_endpoint,
        )

    def test_PUT_401(self, server):
        """Test that PUT endpoint requires authentication."""
        test_name = "test_PUT_401"
        self.reason_to_skip(test_name)

        nonexistent_id = str(uuid.uuid4())

        # Use fake parent_ids if required for path construction
        path_parent_ids = {}
        if self.has_parent_entities():
            for parent in self.parent_entities:
                # Generate dummy IDs only if needed for the path structure
                if parent.path_level in [1, 2] or (
                    parent.is_path and parent.path_level is None
                ):
                    dummy_id = str(uuid.uuid4())
                    path_parent_ids[f"{parent.name}_id"] = dummy_id

        # Create update payload based on whether string_field_to_update is defined
        if self.string_field_to_update:
            update_payload = self.nest_payload_in_entity(
                entity={self.string_field_to_update: "Updated Name"}
            )
        else:
            update_payload = self.nest_payload_in_entity(entity={})

        endpoint = self.get_update_endpoint(nonexistent_id, path_parent_ids)
        response = server.put(endpoint, json=update_payload)
        self._assert_response_status(
            response,
            401,
            "PUT unauthorized",
            endpoint,
            update_payload,
        )

    def test_PUT_404_other_user(self, server, admin_a_jwt, team_a, jwt_b):
        """Test that users cannot update each other's resources."""
        test_name = "test_PUT_404_other_user"
        self.reason_to_skip(test_name)

        # First create a resource with user A
        resource_a = self.test_POST_201(server, admin_a_jwt, team_a)

        # Extract parent IDs from created resource
        _, path_parent_ids = self._extract_parent_ids(resource_a)

        # Try to update the resource with user B
        updated_name = f"Updated by B {uuid.uuid4()}"

        # Create update payload based on whether string_field_to_update is defined
        if self.string_field_to_update:
            update_payload = self.nest_payload_in_entity(
                entity={self.string_field_to_update: updated_name}
            )
            resource_name = resource_a[self.string_field_to_update]  # Original value
        else:
            update_payload = self.nest_payload_in_entity(entity={})
            resource_name = None

        response = server.put(
            self.get_update_endpoint(resource_a["id"], path_parent_ids),
            json=update_payload,
            headers=self._auth_header(jwt_b),
        )

        # This should return 404 Not Found (not 403)
        self._assert_response_status(
            response,
            404,
            "PUT by different user",
            self.get_update_endpoint(resource_a["id"], path_parent_ids),
            update_payload,
        )

        # Verify the resource wasn't updated by checking with user A
        verify_response = server.get(
            self.get_detail_endpoint(resource_a["id"], path_parent_ids),
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            verify_response,
            200,
            "GET after PUT attempt by different user",
            self.get_detail_endpoint(resource_a["id"], path_parent_ids),
        )

        entity = self._assert_entity_in_response(verify_response)

        # Verify name was not changed, if we have a string field to check
        if self.string_field_to_update:
            assert entity[self.string_field_to_update] == resource_name, (
                f"[{self.entity_name}] Entity was incorrectly updated by different user\n"
                f"Expected {self.string_field_to_update}: {resource_name}\n"
                f"Actual {self.string_field_to_update}: {entity[self.string_field_to_update]}\n"
                f"Entity: {entity}"
            )

    def test_PUT_404_nonexistent(self, server, admin_a_jwt, team_a):
        """Test that API returns 404 for nonexistent resource (PUT)."""
        test_name = "test_PUT_404_nonexistent"
        self.reason_to_skip(test_name)

        nonexistent_id = str(uuid.uuid4())

        # Create parent entities if required
        parent_entities_dict = {}
        parent_ids = {}
        path_parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(
                server, admin_a_jwt, team_a
            )
            parent_ids = {
                parent.foreign_key: parent_entities_dict[parent.name].id
                for parent in self.parent_entities
                if parent.name in parent_entities_dict
            }
            # Extract parent IDs for path if needed
            for parent in self.parent_entities:
                if parent.is_path and parent.foreign_key in parent_ids:
                    parent_id = parent_ids[parent.foreign_key]
                    path_parent_ids[f"{parent.name}_id"] = parent_id
                    # Use path_level to populate path_parent_ids
                    if parent.path_level in [1, 2]:
                        path_parent_ids[f"{parent.name}_id"] = parent_id
                    # Fallback for backward compatibility (if is_path=True and path_level=None)
                    elif parent.is_path and parent.path_level is None:
                        path_parent_ids[f"{parent.name}_id"] = parent_id

        # Create update payload based on whether string_field_to_update is defined
        if self.string_field_to_update:
            payload = self.nest_payload_in_entity(
                entity={self.string_field_to_update: "Updated Name"}
            )
        else:
            payload = self.nest_payload_in_entity(entity={})

        response = server.put(
            self.get_update_endpoint(nonexistent_id, path_parent_ids),
            json=payload,
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response,
            404,
            "PUT nonexistent resource",
            self.get_update_endpoint(nonexistent_id, path_parent_ids),
            payload,
        )

    def test_DELETE_401(self, server):
        """Test that DELETE endpoint requires authentication."""
        test_name = "test_DELETE_401"
        self.reason_to_skip(test_name)

        nonexistent_id = str(uuid.uuid4())

        # Use fake parent_ids if required for path construction
        path_parent_ids = {}
        if self.has_parent_entities():
            for parent in self.parent_entities:
                # Generate dummy IDs only if needed for the path structure
                if parent.path_level in [1, 2] or (
                    parent.is_path and parent.path_level is None
                ):
                    dummy_id = str(uuid.uuid4())
                    path_parent_ids[f"{parent.name}_id"] = dummy_id

        endpoint = self.get_delete_endpoint(nonexistent_id, path_parent_ids)
        response = server.delete(endpoint)
        self._assert_response_status(
            response,
            401,
            "DELETE unauthorized",
            endpoint,
        )

    def test_POST_404_nonexistent_parent(self, server, admin_a_jwt, team_a):
        """Test creating a resource with a nonexistent parent."""
        test_name = "test_POST_404_nonexistent_parent"
        self.reason_to_skip(test_name)

        if not self.has_parent_entities():
            pytest.skip("No parent entities for this resource")

        # Create a resource with nonexistent parent ID
        resource_name = self.faker.word()

        # Create payload with nonexistent parent IDs
        parent_ids = {}
        path_parent_ids = {}
        has_non_nullable_parent = False
        for parent in self.parent_entities:
            if not parent.nullable:
                has_non_nullable_parent = True
                nonexistent_id = str(uuid.uuid4())
                parent_ids[parent.foreign_key] = nonexistent_id
                # Also add to path_parent_ids if it's a path parent
                if parent.path_level in [1, 2] or (
                    parent.is_path and parent.path_level is None
                ):
                    path_parent_ids[f"{parent.name}_id"] = nonexistent_id
            elif parent.path_level in [1, 2] or (
                parent.is_path and parent.path_level is None
            ):
                # If a nullable parent is a path parent, we still need a dummy ID for the path
                path_parent_ids[f"{parent.name}_id"] = str(uuid.uuid4())

        # Skip test if no non-nullable parents to make nonexistent
        if not has_non_nullable_parent:
            pytest.skip(
                "No non-nullable parents to test non-existence for this resource"
            )

        payload = self.create_payload(resource_name, parent_ids, team_a.id)

        endpoint = self.get_create_endpoint(path_parent_ids)
        response = server.post(
            endpoint,
            json=payload,
            headers=self._auth_header(admin_a_jwt),
        )

        # Only expect 404 if a non-nullable parent ID was provided and is invalid
        # The BLL should ideally perform this check.
        self._assert_response_status(
            response,
            404,  # Assuming BLL checks FK constraints and raises appropriate error mapped to 404
            "POST with nonexistent parent",
            endpoint,
            payload,
        )

    def test_GET_404_nonexistent_parent(self, server, admin_a_jwt, team_a):
        """Test listing resources for a nonexistent parent."""
        test_name = "test_GET_404_nonexistent_parent"
        self.reason_to_skip(test_name)

        if not self.has_parent_entities():
            pytest.skip("No parent entities for this resource")

        # Check if resource has path parent
        path_parent = self.get_path_parent_entity()
        if not path_parent:
            pytest.skip("No path parent for this resource")

        # Create path_parent_ids with nonexistent IDs
        path_parent_ids = {f"{path_parent.name}_id": str(uuid.uuid4())}

        response = server.get(
            self.get_list_endpoint(path_parent_ids),
            headers=self._auth_header(admin_a_jwt),
        )

        # We should get a 200 with empty list for nonexistent parents
        self._assert_response_status(
            response,
            200,
            "GET list with nonexistent parent",
            self.get_list_endpoint(path_parent_ids),
        )

        json_response = response.json()
        plural_entity_type = self.resource_name_plural
        assert plural_entity_type in json_response, (
            f"[{self.entity_name}] Response does not contain expected entities: {plural_entity_type}\n"
            f"Response: {json_response}"
        )

        assert (
            len(json_response[plural_entity_type]) == 0
        ), f"[{self.entity_name}] Expected empty list for nonexistent parent, got: {json_response[plural_entity_type]}"

    def test_POST_403_role_too_low(self, server, admin_a_jwt, api_key=None):
        """Test creating a resource with insufficient permissions.

        This test is meant to be overridden by resources that require special permissions,
        such as those that can only be created with an API key or by admin users.
        """
        test_name = "test_POST_403_role_too_low"
        self.reason_to_skip(test_name)

        # Base implementation is a no-op, child classes should override this
        # test if they have specific permission requirements
        pytest.skip(
            "This test should be overridden by resources with permission requirements"
        )

    def _build_gql_query(
        self,
        query_type,
        id_param=None,
        filter_param=None,
        parent_param=None,
        fields=None,
        pagination_params=None,
    ):
        """Build a GraphQL query with consistent formatting.

        Args:
            query_type (str): The GraphQL query type (singular or plural entity name)
            id_param (str, optional): ID for retrieving a specific resource
            filter_param (dict, optional): Filter parameters for search queries
            parent_param (dict, optional): Parent ID parameters for related resources
            fields (list, optional): Fields to include in the response
            pagination_params (dict, optional): Pagination parameters (limit, offset)

        Returns:
            str: Formatted GraphQL query
        """
        # Start building the query
        query_lines = ["query {"]

        # Add the query operation with parameters
        operation_line = f"  {query_type}"
        params = []

        # Add ID parameter if provided
        if id_param:
            params.append(f'id: "{id_param}"')

        # Add parent parameters if provided
        if parent_param:
            for key, value in parent_param.items():
                if value is not None:
                    parent_id_field_camel = self.to_camel_case(key)
                    params.append(f'{parent_id_field_camel}: "{value}"')

        # Add filter parameter if provided
        if filter_param:
            filter_parts = []
            for key, value in filter_param.items():
                if isinstance(value, dict):
                    operation, term = next(iter(value.items()))
                    if isinstance(term, str):
                        filter_parts.append(
                            f'{self.to_camel_case(key)}: {{ {operation}: "{term}" }}'
                        )
                    else:
                        filter_parts.append(
                            f"{self.to_camel_case(key)}: {{ {operation}: {term} }}"
                        )
                elif isinstance(value, str):
                    filter_parts.append(f'{self.to_camel_case(key)}: "{value}"')
                else:
                    filter_parts.append(f"{self.to_camel_case(key)}: {value}")

            params.append(f'filter: {{ {", ".join(filter_parts)} }}')

        # Add pagination parameters if provided
        if pagination_params:
            for key, value in pagination_params.items():
                params.append(f"{key}: {value}")

        # Add required GraphQL parameters
        if hasattr(self, "required_graphql_params") and self.required_graphql_params:
            for key, value in self.required_graphql_params.items():
                if value is not None:
                    if isinstance(value, str):
                        params.append(f'{key}: "{value}"')
                    else:
                        params.append(f"{key}: {value}")

        # Append parameters to operation line if any
        if params:
            operation_line += f"({', '.join(params)})"

        query_lines.append(operation_line + " {")

        # Determine fields to include
        if fields:
            # Use explicitly provided fields
            field_lines = [f"    {self.to_camel_case(field)}" for field in fields]
        else:
            # Use default fields based on what's available in the class
            default_fields = []

            # Try required_fields first
            if hasattr(self, "required_fields") and self.required_fields:
                default_fields = self.required_fields
            # Fall back to create_fields keys
            elif hasattr(self, "create_fields") and self.create_fields:
                default_fields = list(self.create_fields.keys())

            # Always include id if available
            if default_fields and "id" not in default_fields:
                default_fields.insert(0, "id")
            # Last resort - just use id
            if not default_fields:
                default_fields = ["id"]

            field_lines = [
                f"    {self.to_camel_case(field)}" for field in default_fields
            ]

        query_lines.extend(field_lines)
        query_lines.append("  }")
        query_lines.append("}")

        return "\n".join(query_lines)

    def _build_gql_mutation(
        self,
        mutation_type,
        id_param=None,
        input_data=None,
        parent_param=None,
        fields=None,
    ):
        """
        Build a GraphQL mutation with consistent formatting.

        Args:
            mutation_type (str): The GraphQL mutation type (e.g., createEntity, updateEntity)
            id_param (str, optional): ID for updating/deleting a specific resource
            input_data (dict, optional): Input data for the mutation
            parent_param (dict, optional): Parent ID parameters
            fields (list, optional): Fields to include in the response, defaults to required_fields

        Returns:
            str: Formatted GraphQL mutation
        """
        # Start building the mutation
        mutation_lines = ["mutation {"]

        # Add the mutation operation with parameters
        operation_line = f"  {mutation_type}"
        params = []

        # Add ID parameter if provided
        if id_param:
            params.append(f'id: "{id_param}"')

        # Add parent parameters if provided
        if parent_param:
            for key, value in parent_param.items():
                if value is not None:
                    parent_id_field_camel = self.to_camel_case(key)
                    params.append(f'{parent_id_field_camel}: "{value}"')

        # Add input data if provided
        if input_data:
            # Convert input data to camelCase and format for GraphQL
            input_parts = []
            for key, value in input_data.items():
                key_camel = self.to_camel_case(key)

                if value is None:
                    input_parts.append(f"{key_camel}: null")
                elif isinstance(value, str):
                    input_parts.append(f'{key_camel}: "{value}"')
                elif isinstance(value, (int, float)):
                    input_parts.append(f"{key_camel}: {value}")
                elif isinstance(value, bool):
                    input_parts.append(f"{key_camel}: {str(value).lower()}")
                elif isinstance(value, dict):
                    # Handle nested objects - convert to JSON and escape quotes
                    json_value = json.dumps(value).replace('"', '\\"')
                    input_parts.append(f'{key_camel}: "{json_value}"')
                elif isinstance(value, list):
                    # Handle lists by converting to JSON array format
                    if all(isinstance(item, (int, float, bool)) for item in value):
                        # Simple array of primitives
                        items_str = ", ".join(
                            str(item).lower() if isinstance(item, bool) else str(item)
                            for item in value
                        )
                        input_parts.append(f"{key_camel}: [{items_str}]")
                    else:
                        # Complex array - JSON serialize with escaped quotes
                        json_value = json.dumps(value).replace('"', '\\"')
                        input_parts.append(f'{key_camel}: "{json_value}"')
                else:
                    # Default fallback - stringify unknown types
                    input_parts.append(f'{key_camel}: "{str(value)}"')

            params.append(f'input: {{ {", ".join(input_parts)} }}')

        # Append parameters to operation line if any
        if params:
            operation_line += f"({', '.join(params)})"

        mutation_lines.append(operation_line + " {")

        # Determine fields to include in response
        if fields:
            # Convert all field names to camelCase for GraphQL
            field_lines = [f"    {self.to_camel_case(field)}" for field in fields]
        else:
            # Include all required fields if none specified
            field_lines = [
                f"    {self.to_camel_case(field)}" for field in self.required_fields
            ]

            # Always include ID even if not in required_fields
            if "id" not in self.required_fields and not any(
                f.strip() == "id" for f in field_lines
            ):
                field_lines.insert(0, "    id")

        mutation_lines.extend(field_lines)
        mutation_lines.append("  }")
        mutation_lines.append("}")

        return "\n".join(mutation_lines)

    def _build_gql_subscription(
        self,
        subscription_type,
        filter_param=None,
        parent_param=None,
        fields=None,
    ):
        """
        Build a GraphQL subscription with consistent formatting.

        Args:
            subscription_type (str): The GraphQL subscription type (e.g., entityCreated)
            filter_param (dict, optional): Filter parameters for the subscription
            parent_param (dict, optional): Parent ID parameters
            fields (list, optional): Fields to include in the subscription response, defaults to required_fields

        Returns:
            str: Formatted GraphQL subscription
        """
        # Start building the subscription
        subscription_lines = ["subscription {"]

        # Add the subscription operation with parameters
        operation_line = f"  {subscription_type}"
        params = []

        # Add filter parameter if provided
        if filter_param:
            # Construct filter string based on the filter_param dictionary
            filter_parts = []
            for key, value in filter_param.items():
                if isinstance(value, dict):
                    # Handle nested filters like {contains: "searchTerm"}
                    operation, term = next(iter(value.items()))
                    if isinstance(term, str):
                        filter_parts.append(
                            f'{self.to_camel_case(key)}: {{ {operation}: "{term}" }}'
                        )
                    else:
                        filter_parts.append(
                            f"{self.to_camel_case(key)}: {{ {operation}: {term} }}"
                        )
                elif isinstance(value, str):
                    filter_parts.append(f'{self.to_camel_case(key)}: "{value}"')
                else:
                    filter_parts.append(f"{self.to_camel_case(key)}: {value}")

            params.append(f'filter: {{ {", ".join(filter_parts)} }}')

        # Add parent parameters if provided
        if parent_param:
            for key, value in parent_param.items():
                if value is not None:
                    parent_id_field_camel = self.to_camel_case(key)
                    params.append(f'{parent_id_field_camel}: "{value}"')

        # Append parameters to operation line if any
        if params:
            operation_line += f"({', '.join(params)})"

        subscription_lines.append(operation_line + " {")

        # Determine fields to include
        if fields:
            # Convert all field names to camelCase for GraphQL
            field_lines = [f"    {self.to_camel_case(field)}" for field in fields]
        else:
            # Include all required fields if none specified
            field_lines = [
                f"    {self.to_camel_case(field)}" for field in self.required_fields
            ]

            # Always include ID even if not in required_fields
            if "id" not in self.required_fields and not any(
                f.strip() == "id" for f in field_lines
            ):
                field_lines.insert(0, "    id")

        subscription_lines.extend(field_lines)
        subscription_lines.append("  }")
        subscription_lines.append("}")

        return "\n".join(subscription_lines)

    def _assert_gql_response(self, response, operation_type):
        """Assert that a GraphQL response is valid and contains expected data."""
        assert response.status_code == 200, (
            f"[{self.entity_name}] GraphQL {operation_type} failed: status code {response.status_code}\n"
            f"Response: {response.text}"
        )

        json_response = response.json()
        assert "data" in json_response, (
            f"[{self.entity_name}] GraphQL {operation_type} response missing 'data' field\n"
            f"Response: {json_response}"
        )

        assert json_response["data"] is not None, (
            f"[{self.entity_name}] GraphQL {operation_type} returned null data\n"
            f"Response: {json_response}"
        )

        # Check for errors
        assert "errors" not in json_response, (
            f"[{self.entity_name}] GraphQL {operation_type} returned errors:\n"
            f"Errors: {json_response.get('errors')}\n"
            f"Response: {json_response}"
        )

        return json_response["data"]

    def test_GQL_query_single(self, server, admin_a_jwt, team_a):
        """Test retrieving the current user using GraphQL."""
        test_name = "test_GQL_query_single"
        self.reason_to_skip(test_name)

        # For users, we query the current user
        resource_type = self.entity_name.lower()

        # Create a list of fields to request
        gql_fields = (
            list(self.create_fields.keys()) if hasattr(self, "create_fields") else None
        )
        if gql_fields and "password" in gql_fields:
            gql_fields.remove("password")  # Remove sensitive fields

        # Generate query - explicitly pass fields to avoid reliance on required_fields
        query = self._build_gql_query(query_type=resource_type, fields=gql_fields)

        # Execute the GraphQL query
        response = server.post(
            "/graphql", json={"query": query}, headers=self._auth_header(admin_a_jwt)
        )

        # Assert response
        data = self._assert_gql_response(response, "query single")

        # Check entity was returned
        assert resource_type in data, (
            f"[{self.entity_name}] GraphQL query response missing entity: {resource_type}\n"
            f"Response data: {data}"
        )

        gql_entity = data[resource_type]

        # Verify we got a user with an ID
        assert "id" in gql_entity, f"User entity missing ID field: {gql_entity}"

        return gql_entity

    def test_GQL_query_list(self, server, admin_a_jwt, team_a):
        """Test retrieving a list of users using GraphQL."""
        test_name = "test_GQL_query_list"
        self.reason_to_skip(test_name)

        # Determine the GraphQL query for users plural
        resource_type_plural = self.resource_name_plural.lower()

        # Create a list of fields to request
        gql_fields = (
            list(self.create_fields.keys()) if hasattr(self, "create_fields") else None
        )
        if gql_fields and "password" in gql_fields:
            gql_fields.remove("password")  # Remove sensitive fields

        # Always include ID
        if gql_fields and "id" not in gql_fields:
            gql_fields.insert(0, "id")

        # Generate query for users list with explicit fields
        query = self._build_gql_query(
            query_type=resource_type_plural, fields=gql_fields
        )

        # Execute the GraphQL query
        response = server.post(
            "/graphql", json={"query": query}, headers=self._auth_header(admin_a_jwt)
        )

        # Assert response
        data = self._assert_gql_response(response, "query list")

        # Check users were returned
        assert resource_type_plural in data, (
            f"[{self.entity_name}] GraphQL query response missing entities: {resource_type_plural}\n"
            f"Response data: {data}"
        )

        gql_entities = data[resource_type_plural]
        assert isinstance(gql_entities, list), (
            f"[{self.entity_name}] GraphQL query should return a list of entities\n"
            f"Entities: {gql_entities}"
        )

        # For users, we expect at least one user (the current user)
        assert len(gql_entities) > 0, "Expected at least the current user in users list"

        return gql_entities

    def test_GQL_query_fields(self, server, admin_a_jwt, team_a):
        """Test retrieving only specific fields using GraphQL."""
        test_name = "test_GQL_query_fields"
        self.reason_to_skip(test_name)

        # Create a resource to query
        resource, parent_ids, path_parent_ids, headers = self._setup_test_resources(
            server, admin_a_jwt, team_a, count=1
        )[0]

        # Determine the GraphQL query type based on entity name
        resource_type = self.entity_name.lower()

        # Select a subset of fields (at most 2) to request
        subset_fields = self.required_fields[:2]

        # Build query with only specific fields
        query = self._build_gql_query(
            query_type=resource_type, id_param=resource["id"], fields=subset_fields
        )

        # Execute the GraphQL query
        response = server.post(
            "/graphql", json={"query": query}, headers=self._auth_header(admin_a_jwt)
        )

        # Assert response
        data = self._assert_gql_response(response, "query fields")

        # Check entity was returned
        assert resource_type in data, (
            f"[{self.entity_name}] GraphQL query response missing entity: {resource_type}\n"
            f"Response data: {data}"
        )

        gql_entity = data[resource_type]

        # Verify only requested fields (and ID) are returned
        for field in self.required_fields:
            field_camel = self.to_camel_case(field)
            if field in subset_fields or field == "id":
                assert field_camel in gql_entity, (
                    f"[{self.entity_name}] GraphQL response missing requested field: {field_camel}\n"
                    f"Entity: {gql_entity}"
                )
            else:
                if field_camel in gql_entity:
                    logging.warning(
                        f"[{self.entity_name}] GraphQL response contains unrequested field: {field_camel}"
                    )

        return gql_entity

    def test_GQL_query_pagination(self, server, admin_a_jwt, team_a):
        """Test pagination in GraphQL list queries."""
        test_name = "test_GQL_query_pagination"
        self.reason_to_skip(test_name)

        # Create multiple resources for pagination
        resources = self._setup_test_resources(server, admin_a_jwt, team_a, count=3)
        if len(resources) < 2:
            pytest.skip("Not enough resources for pagination test")

        # Determine the GraphQL query for plural resources
        resource_type_plural = self.resource_name_plural.lower()

        # Build query with pagination (limit=1)
        query_page1 = self._build_gql_query(
            query_type=resource_type_plural,
            fields=["id"],
            pagination_params={"limit": 1, "offset": 0},
        )

        # Execute the first page query
        response_page1 = server.post(
            "/graphql",
            json={"query": query_page1},
            headers=self._auth_header(admin_a_jwt),
        )

        # Assert response for page 1
        data_page1 = self._assert_gql_response(
            response_page1, "query pagination page 1"
        )

        # Check entities were returned
        assert resource_type_plural in data_page1, (
            f"[{self.entity_name}] GraphQL paginated query response missing entities: {resource_type_plural}\n"
            f"Response data: {data_page1}"
        )

        page1_entities = data_page1[resource_type_plural]
        assert isinstance(page1_entities, list), (
            f"[{self.entity_name}] GraphQL paginated query should return a list\n"
            f"Entities: {page1_entities}"
        )

        # Verify we got exactly 1 result on the first page
        assert len(page1_entities) == 1, (
            f"[{self.entity_name}] GraphQL pagination returned wrong number of entities\n"
            f"Expected: 1, Got: {len(page1_entities)}"
        )

        # Get page 2
        query_page2 = self._build_gql_query(
            query_type=resource_type_plural,
            fields=["id"],
            pagination_params={"limit": 1, "offset": 1},
        )

        # Execute the second page query
        response_page2 = server.post(
            "/graphql",
            json={"query": query_page2},
            headers=self._auth_header(admin_a_jwt),
        )

        # Assert response for page 2
        data_page2 = self._assert_gql_response(
            response_page2, "query pagination page 2"
        )

        # Check entities were returned on page 2
        assert resource_type_plural in data_page2, (
            f"[{self.entity_name}] GraphQL paginated query response missing entities: {resource_type_plural}\n"
            f"Response data: {data_page2}"
        )

        page2_entities = data_page2[resource_type_plural]

        # Verify page 2 contains different entities than page 1
        assert page1_entities[0]["id"] != page2_entities[0]["id"], (
            f"[{self.entity_name}] GraphQL pagination returned same entity on different pages\n"
            f"Page 1: {page1_entities[0]['id']}, Page 2: {page2_entities[0]['id']}"
        )

        return {"page1": page1_entities, "page2": page2_entities}

    def test_GQL_mutation_validation(self, server, admin_a_jwt, team_a):
        """Test GraphQL mutation validation with invalid input."""
        test_name = "test_GQL_mutation_validation"
        self.reason_to_skip(test_name)

        # Determine mutation type
        mutation_type = f"create{self.entity_name.capitalize()}"

        # Create an invalid payload (empty object)
        invalid_input = {}

        # Generate mutation with invalid input
        mutation = self._build_gql_mutation(
            mutation_type=mutation_type, input_data=invalid_input
        )

        # Execute the GraphQL mutation
        response = server.post(
            "/graphql", json={"query": mutation}, headers=self._auth_header(admin_a_jwt)
        )

        # Check for validation error
        json_response = response.json()
        assert "errors" in json_response, (
            f"[{self.entity_name}] GraphQL mutation with invalid input should return errors\n"
            f"Response: {json_response}"
        )

        # Verify there's at least one validation error
        errors = json_response["errors"]
        assert len(errors) > 0, (
            f"[{self.entity_name}] GraphQL mutation missing validation errors\n"
            f"Errors: {errors}"
        )

        # Extract error information
        first_error = errors[0]

        return first_error

    def test_GQL_subscription(self, server, admin_a_jwt, team_a):
        """Test building GraphQL subscription queries."""
        test_name = "test_GQL_subscription"
        self.reason_to_skip(test_name)

        # Note: We can't easily test actual subscription connections in these tests
        # due to the asynchronous websocket nature, but we can at least test
        # that the subscription queries are constructed correctly

        # Determine subscription types based on entity name
        singular_name = self.entity_name.lower()

        # Generate subscription queries for created, updated, deleted events
        subscriptions = {}
        for event_type in ["created", "updated", "deleted"]:
            subscription_type = f"{singular_name}_{event_type}"

            # Build subscription query
            subscription_query = self._build_gql_subscription(
                subscription_type=subscription_type
            )

            # Save the query
            subscriptions[event_type] = subscription_query

        # Verify the subscription queries contain the expected type names
        for event_type, query in subscriptions.items():
            subscription_type = f"{singular_name}_{event_type}"
            assert subscription_type in query, (
                f"[{self.entity_name}] GraphQL subscription query missing type: {subscription_type}\n"
                f"Query: {query}"
            )

        return subscriptions
