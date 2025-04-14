import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import pytest
from pydantic import BaseModel

from endpoints.StaticExampleFactory import ExampleGenerator
from lib.Environment import env
from lib.Strings import pluralize

logger = logging.getLogger(__name__)


class SkippedTest(BaseModel):
    name: str
    reason: str


class ParentEntity(BaseModel):
    """Model for parent entity configuration"""

    name: str
    key: str
    nullable: bool = False
    system: bool = False
    is_path: bool = (
        False  # If True, this parent's ID will be included in the endpoint path
    )


class AbstractEndpointTest:
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
    parent_entities: List[ParentEntity] = []  # List of ParentEntity objects

    # Search configuration - can be overridden by child classes
    supports_search: bool = True
    searchable_fields: List[str] = ["name"]  # Default searchable fields
    search_example_value: str = None  # Example value to search for

    # Tests to skip - Array of SkippedTest objects
    skip_tests: List[SkippedTest] = []

    def should_skip_test(self, test_name: str) -> bool:
        """Check if a test should be skipped based on the skip_tests list."""
        for skip in self.skip_tests:
            if skip.name == test_name:
                pytest.skip(skip.reason)
                return True
        return False

    # Endpoint property getters
    @property
    def list_endpoint_template(self) -> str:
        """Template for the list endpoint, with placeholders for parent IDs if needed."""
        path_parent = self.get_path_parent_entity()
        if path_parent:
            return (
                f"/v1/{path_parent.name}/{{{path_parent.name}_id}}/{self.base_endpoint}"
            )
        return f"/v1/{self.base_endpoint}"

    @property
    def create_endpoint_template(self) -> str:
        """Template for the create endpoint, with placeholders for parent IDs if needed."""
        return self.list_endpoint_template

    @property
    def get_endpoint_template(self) -> str:
        """Template for retrieving a specific resource, with placeholders for parent and resource IDs."""
        path_parent = self.get_path_parent_entity()
        if path_parent:
            return f"/v1/{path_parent.name}/{{{path_parent.name}_id}}/{self.base_endpoint}/{{resource_id}}"
        return f"/v1/{self.base_endpoint}/{{resource_id}}"

    @property
    def update_endpoint_template(self) -> str:
        """Template for updating a specific resource."""
        return self.get_endpoint_template

    @property
    def delete_endpoint_template(self) -> str:
        """Template for deleting a specific resource."""
        return self.get_endpoint_template

    @property
    def search_endpoint_template(self) -> str:
        """Template for the search endpoint."""
        return f"{self.list_endpoint_template}/search"

    @property
    def resource_name_plural(self) -> str:
        """Get the plural form of the resource name."""
        return pluralize(self.entity_name)

    def get_path_parent_entity(self) -> Optional[ParentEntity]:
        """Get the parent entity that should be included in the path, if any."""
        path_parents = [p for p in self.parent_entities if p.is_path]
        return path_parents[0] if path_parents else None

    def has_parent_entities(self) -> bool:
        """Check if this resource has any parent entities."""
        return len(self.parent_entities) > 0

    def has_nullable_parent_entities(self) -> bool:
        """Check if this resource has any nullable parent entities."""
        return any(parent.nullable for parent in self.parent_entities)

    def get_parent_entity_by_name(self, name: str) -> Optional[ParentEntity]:
        """Get a parent entity by name."""
        for parent in self.parent_entities:
            if parent.name == name:
                return parent
        return None

    def get_list_endpoint(self, parent_ids: Dict[str, str] = None) -> str:
        """Get the endpoint for listing resources."""
        parent_ids = parent_ids or {}
        path_parent = self.get_path_parent_entity()

        if path_parent and f"{path_parent.name}_id" not in parent_ids:
            raise ValueError(
                f"Path parent ID required for {self.entity_name} list endpoint"
            )

        if path_parent:
            return self.list_endpoint_template.format(**parent_ids)
        return self.list_endpoint_template

    def get_create_endpoint(self, parent_ids: Dict[str, str] = None) -> str:
        """Get the template for creating resources."""
        parent_ids = parent_ids or {}
        path_parent = self.get_path_parent_entity()

        if path_parent and f"{path_parent.name}_id" not in parent_ids:
            raise ValueError(
                f"Path parent ID required for {self.entity_name} create endpoint"
            )

        if path_parent:
            return self.create_endpoint_template.format(**parent_ids)
        return self.create_endpoint_template

    def get_detail_endpoint(
        self, resource_id: str, parent_ids: Dict[str, str] = None
    ) -> str:
        """Get the endpoint for retrieving a specific resource."""
        parent_ids = parent_ids or {}
        path_parent = self.get_path_parent_entity()

        if path_parent and f"{path_parent.name}_id" not in parent_ids:
            raise ValueError(
                f"Path parent ID required for {self.entity_name} detail endpoint"
            )

        endpoint_params = {"resource_id": resource_id}
        endpoint_params.update(parent_ids)

        return self.get_endpoint_template.format(**endpoint_params)

    def get_update_endpoint(
        self, resource_id: str, parent_ids: Dict[str, str] = None
    ) -> str:
        """Get the endpoint for updating a specific resource."""
        parent_ids = parent_ids or {}
        path_parent = self.get_path_parent_entity()

        if path_parent and f"{path_parent.name}_id" not in parent_ids:
            raise ValueError(
                f"Path parent ID required for {self.entity_name} update endpoint"
            )

        endpoint_params = {"resource_id": resource_id}
        endpoint_params.update(parent_ids)

        return self.update_endpoint_template.format(**endpoint_params)

    def get_delete_endpoint(
        self, resource_id: str, parent_ids: Dict[str, str] = None
    ) -> str:
        """Get the endpoint for deleting a specific resource."""
        parent_ids = parent_ids or {}
        path_parent = self.get_path_parent_entity()

        if path_parent and f"{path_parent.name}_id" not in parent_ids:
            raise ValueError(
                f"Path parent ID required for {self.entity_name} delete endpoint"
            )

        endpoint_params = {"resource_id": resource_id}
        endpoint_params.update(parent_ids)

        return self.delete_endpoint_template.format(**endpoint_params)

    def get_search_endpoint(self, parent_ids: Dict[str, str] = None) -> str:
        """Get the endpoint for searching resources."""
        parent_ids = parent_ids or {}
        path_parent = self.get_path_parent_entity()

        if path_parent and f"{path_parent.name}_id" not in parent_ids:
            raise ValueError(
                f"Path parent ID required for {self.entity_name} search endpoint"
            )

        # Format the search endpoint template with parent IDs if available
        if path_parent and parent_ids:
            return self.search_endpoint_template.format(**parent_ids)

        return self.search_endpoint_template

    # Authentication headers - centralized for better maintainability
    @staticmethod
    def _auth_header(jwt_token: str) -> Dict[str, str]:
        """Return authorization header with the given jwt_token."""
        return {"Authorization": f"Bearer {jwt_token}"}

    @staticmethod
    def _api_key_header(api_key: str = None) -> Dict[str, str]:
        """Return API key header with the given api_key or the default API key."""
        api_key = api_key or env("ROOT_API_KEY")
        return {"X-API-Key": api_key}

    def nest_payload_in_entity(
        self, entity: Union[Dict[str, Any], List[Dict[str, Any]]]
    ) -> Union[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """Factory method to create payloads with consistent structure.

        Args:
            entity: The entity data or list of entity data to wrap

        Returns:
            dict: A properly structured payload for API requests
        """
        # If entity is a list, use plural form of entity name
        if isinstance(entity, list):
            return {self.resource_name_plural: entity}
        # Otherwise use singular form
        return {self.entity_name: entity}

    def generate_name(self) -> str:
        """Generate a unique test name for the resource."""
        return f"Test {self.entity_name} {uuid.uuid4()}"

    def generate_test_data(
        self, model_cls: Type[BaseModel] = None, field_overrides: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Generate test data using the ExampleGenerator.

        Args:
            model_cls: Optional model class for generation
            field_overrides: Optional dict of field overrides

        Returns:
            dict: Generated test data
        """
        if model_cls:
            data = ExampleGenerator.generate_example_for_model(model_cls)
        else:
            # Create a generic example with required fields
            data = {}
            for field in self.required_fields:
                data[field] = ExampleGenerator.get_example_value(str, field)

        # Apply overrides
        if field_overrides:
            for field, value in field_overrides.items():
                data[field] = value

        return data

    def create_payload(
        self, name: str = None, parent_ids: Dict[str, str] = None, team_id: str = None
    ) -> Dict[str, Any]:
        """Create the payload for the creation request.

        Args:
            name: Optional name for the resource
            parent_ids: Optional dictionary of parent IDs if required
            team_id: Optional team ID

        Returns:
            dict: A properly structured payload for API requests
        """
        # Use ExampleGenerator to create realistic test data
        field_overrides = {"name": name or self.generate_name()}
        if team_id:
            field_overrides["team_id"] = team_id

        # Add parent IDs to field overrides
        if parent_ids:
            for parent in self.parent_entities:
                if parent.key in parent_ids:
                    field_overrides[parent.key] = parent_ids[parent.key]

        payload = self.generate_test_data(field_overrides=field_overrides)
        return self.nest_payload_in_entity(entity=payload)

    def create_search_payload(self, field: str, value: Any) -> Dict[str, Any]:
        """Create a search payload using the specified field and value.

        Args:
            field: The field to search on
            value: The value or condition to search for

        Returns:
            dict: A properly structured search payload
        """
        search_data = {}
        search_data[field] = value
        return self.nest_payload_in_entity(entity=search_data)

    def to_camel_case(self, snake_str: str) -> str:
        """Convert snake_case to camelCase for GraphQL compatibility."""
        components = snake_str.split("_")
        return components[0] + "".join(x.title() for x in components[1:])

    def _extract_parent_ids(
        self, entity: Dict[str, Any]
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Extract parent IDs and path parent IDs from an entity.

        Args:
            entity: The entity to extract IDs from

        Returns:
            tuple: (parent_ids, path_parent_ids)
        """
        parent_ids = {}
        path_parent_ids = {}

        for parent in self.parent_entities:
            if parent.key in entity:
                parent_ids[parent.key] = entity[parent.key]
                if parent.is_path:
                    path_parent_ids[f"{parent.name}_id"] = entity[parent.key]

        return parent_ids, path_parent_ids

    def _get_appropriate_headers(
        self, jwt_token: str, api_key: str = None
    ) -> Dict[str, str]:
        """Get the appropriate headers based on entity type.

        Args:
            jwt_token: JWT token for authorization
            api_key: Optional API key for system entities

        Returns:
            dict: Headers for the request
        """
        return (
            self._api_key_header(api_key)
            if self.system_entity
            else self._auth_header(jwt_token)
        )

    def _assert_response_status(
        self, response, expected_status, operation, endpoint, payload=None
    ):
        """Assert that response has the expected status code with detailed error message."""
        assert response.status_code == expected_status, (
            f"[{self.entity_name}] {operation} failed: Expected status {expected_status}, got {response.status_code}\n"
            f"Response text: {response.text}\n"
            f"Endpoint: {endpoint}\n"
            f"Payload: {payload if payload else 'None'}\n"
            f"Request headers: {dict(response.request.headers)}"
        )

    def _assert_entity_in_response(
        self, response, entity_field=None, expected_value=None
    ):
        """Assert that the entity is in the response with the expected field value."""
        json_response = response.json()
        assert self.entity_name in json_response, (
            f"[{self.entity_name}] Response does not contain expected entity: {self.entity_name}\n"
            f"Response: {json_response}"
        )

        entity = json_response[self.entity_name]

        # Check specific field if provided
        if entity_field and expected_value is not None:
            assert entity_field in entity, (
                f"[{self.entity_name}] Entity does not contain expected field: {entity_field}\n"
                f"Entity: {entity}"
            )
            assert entity[entity_field] == expected_value, (
                f"[{self.entity_name}] Field value mismatch: expected '{expected_value}', got '{entity[entity_field]}'\n"
                f"Entity: {entity}"
            )

        # Check required fields
        for field in self.required_fields:
            assert field in entity, (
                f"[{self.entity_name}] Required field missing: {field}\n"
                f"Entity: {entity}"
            )

        return entity

    def _assert_entities_in_response(self, response, entity_type=None):
        """Assert that entities are in the response as a list."""
        json_response = response.json()
        entity_type = entity_type or self.resource_name_plural

        assert entity_type in json_response, (
            f"[{self.entity_name}] Response does not contain expected entities: {entity_type}\n"
            f"Response: {json_response}"
        )

        entities = json_response[entity_type]
        assert isinstance(entities, list), (
            f"[{self.entity_name}] Expected a list of entities, got: {type(entities)}\n"
            f"Entities: {entities}"
        )

        # Check required fields for each entity
        for entity in entities:
            for field in self.required_fields:
                assert field in entity, (
                    f"[{self.entity_name}] Required field missing in entity: {field}\n"
                    f"Entity: {entity}"
                )

        return entities

    def _assert_parent_ids_match(self, entity, parent_ids):
        """Assert that parent IDs in entity match the expected parent IDs."""
        for parent in self.parent_entities:
            if parent.key in parent_ids and parent.key in entity:
                assert entity[parent.key] == parent_ids[parent.key], (
                    f"[{self.entity_name}] Parent ID mismatch for {parent.name}: "
                    f"expected '{parent_ids[parent.key]}', got '{entity[parent.key]}'\n"
                    f"Entity: {entity}"
                )

    def _setup_test_resources(self, server, jwt_token, team, count=1, api_key=None):
        """Set up test resources for batch operations.

        Args:
            server: Test server fixture
            jwt_token: JWT token for authentication
            team: Team information
            count: Number of resources to create
            api_key: Optional API key for system entities

        Returns:
            tuple: (resources, path_parent_ids, headers)
        """
        # Create resources
        resources = []
        for i in range(count):
            resources.append(self.test_POST_201(server, jwt_token, team, api_key))

        # Get path parent IDs from the first resource
        _, path_parent_ids = self._extract_parent_ids(resources[0])

        # Get appropriate headers
        headers = self._get_appropriate_headers(jwt_token, api_key)

        return resources, path_parent_ids, headers

    def test_POST_201(self, server, jwt_a, team_a, api_key=None):
        """Test successful resource creation with valid authentication."""
        test_name = "test_POST_201"
        self.should_skip_test(test_name)

        # Generate a unique name for the test resource
        resource_name = self.generate_name()

        # Create parent entities if required
        parent_ids = {}
        path_parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(server, jwt_a, team_a)
            for parent in self.parent_entities:
                if parent.name in parent_entities_dict:
                    parent_ids[parent.key] = parent_entities_dict[parent.name]["id"]
                    if parent.is_path:
                        path_parent_ids[f"{parent.name}_id"] = parent_entities_dict[
                            parent.name
                        ]["id"]

        # Create the payload using the child class implementation
        payload = self.create_payload(
            resource_name, parent_ids, team_a.get("id", None) if team_a else None
        )

        # Choose the appropriate authentication header
        headers = self._get_appropriate_headers(jwt_a, api_key)

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
            response, self.string_field_to_update, resource_name
        )
        self._assert_parent_ids_match(entity, parent_ids)

        return entity

    def test_POST_201_null_parents(self, server, jwt_a, team_a, api_key=None):
        """Test creating a resource with nullable parent fields set to null."""
        test_name = "test_POST_201_null_parents"
        self.should_skip_test(test_name)

        # Check if there are any nullable parents
        nullable_parents = [p for p in self.parent_entities if p.nullable]
        if not nullable_parents:
            pytest.skip("No nullable parents for this entity")

        # Generate a unique name for the test resource
        resource_name = self.generate_name()

        # Create non-nullable parent entities if required
        parent_ids = {}
        path_parent_ids = {}

        # First handle non-nullable parents (we need actual IDs for these)
        for parent in self.parent_entities:
            if not parent.nullable:
                if "parent_entities_dict" not in locals():
                    parent_entities_dict = self.create_parent_entities(
                        server, jwt_a, team_a
                    )

                if parent.name in parent_entities_dict:
                    parent_ids[parent.key] = parent_entities_dict[parent.name]["id"]
                    if parent.is_path:
                        path_parent_ids[f"{parent.name}_id"] = parent_entities_dict[
                            parent.name
                        ]["id"]

        # Create the payload - set nullable parents to None
        payload = {"name": resource_name}

        # Add IDs for non-nullable parents
        for parent in self.parent_entities:
            if not parent.nullable and parent.key in parent_ids:
                payload[parent.key] = parent_ids[parent.key]
            elif parent.nullable:
                payload[parent.key] = None

        if team_a and "team_id" in self.required_fields:
            payload["team_id"] = team_a.get("id", None)

        # Nest the payload in the entity
        nested_payload = self.nest_payload_in_entity(entity=payload)

        # Choose the appropriate authentication header
        headers = self._get_appropriate_headers(jwt_a, api_key)

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
            response, self.string_field_to_update, resource_name
        )

        # Verify nullable parents are null/None in the response
        for parent in nullable_parents:
            assert parent.key in entity, (
                f"Expected nullable parent {parent.key} to be in response\n"
                f"Entity: {entity}"
            )
            assert entity[parent.key] is None, (
                f"Expected nullable parent {parent.key} to be None, got {entity[parent.key]}\n"
                f"Entity: {entity}"
            )

        return entity

    def test_POST_201_batch(self, server, jwt_a, team_a, api_key=None):
        """Test successful batch creation of resources."""
        test_name = "test_POST_201_batch"
        self.should_skip_test(test_name)

        # Number of entities to create in batch
        batch_size = 3

        # Create parent entities if required
        parent_ids = {}
        path_parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(server, jwt_a, team_a)
            for parent in self.parent_entities:
                if parent.name in parent_entities_dict:
                    parent_ids[parent.key] = parent_entities_dict[parent.name]["id"]
                    if parent.is_path:
                        path_parent_ids[f"{parent.name}_id"] = parent_entities_dict[
                            parent.name
                        ]["id"]

        # Create multiple resource entities
        batch_entities = []
        expected_names = []
        for i in range(batch_size):
            resource_name = f"{self.generate_name()} Batch Item {i+1}"
            expected_names.append(resource_name)
            entity = {"name": resource_name}

            # Add parent IDs
            for parent in self.parent_entities:
                if parent.key in parent_ids:
                    entity[parent.key] = parent_ids[parent.key]

            if team_a and "team_id" in self.required_fields:
                entity["team_id"] = team_a.get("id", None)

            batch_entities.append(entity)

        # Nest the entities in a list under the pluralized entity name
        nested_payload = {self.resource_name_plural: batch_entities}

        # Choose the appropriate authentication header
        headers = self._get_appropriate_headers(jwt_a, api_key)

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

            # Check that each entity has a name containing "Batch Item"
            assert self.string_field_to_update in entity, (
                f"[{self.entity_name}] Field {self.string_field_to_update} missing in batch entity\n"
                f"Entity: {entity}"
            )
            assert "Batch Item" in entity[self.string_field_to_update], (
                f"[{self.entity_name}] Expected 'Batch Item' in entity name, got: {entity[self.string_field_to_update]}\n"
                f"Entity: {entity}"
            )

            # Check parent IDs
            self._assert_parent_ids_match(entity, parent_ids)

        return entities

    def test_PUT_200_batch(self, server, jwt_a, team_a, api_key=None):
        """Test batch updating resources."""
        test_name = "test_PUT_200_batch"
        self.should_skip_test(test_name)

        # Create multiple resources to update in batch
        resources, path_parent_ids, headers = self._setup_test_resources(
            server, jwt_a, team_a, count=3, api_key=api_key
        )

        # Prepare batch update data
        updated_name = f"Batch Updated {self.entity_name} {uuid.uuid4()}"
        target_ids = [r["id"] for r in resources]

        payload = {
            self.entity_name: {self.string_field_to_update: updated_name},
            "target_ids": target_ids,
        }

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
            assert entity[self.string_field_to_update] == updated_name, (
                f"[{self.entity_name}] Entity not batch updated: expected '{updated_name}', "
                f"got '{entity[self.string_field_to_update]}'\n"
                f"Entity: {entity}"
            )

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
            assert retrieved_entity[self.string_field_to_update] == updated_name, (
                f"[{self.entity_name}] Entity batch update didn't persist: expected '{updated_name}', "
                f"got '{retrieved_entity[self.string_field_to_update]}'\n"
                f"Entity: {retrieved_entity}"
            )

        return updated_entities

    def test_DELETE_204_batch(self, server, jwt_a, team_a, api_key=None):
        """Test batch deleting resources."""
        test_name = "test_DELETE_204_batch"
        self.should_skip_test(test_name)

        # Create multiple resources to delete in batch
        resources, path_parent_ids, headers = self._setup_test_resources(
            server, jwt_a, team_a, count=3, api_key=api_key
        )

        # Prepare batch delete data
        target_ids = [r["id"] for r in resources]
        payload = {"target_ids": target_ids}

        # Make the batch delete request
        response = server.delete(
            self.get_list_endpoint(path_parent_ids),
            json=payload,
            headers=headers,
        )

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

    def test_GET_200_pagination(self, server, jwt_a, team_a):
        """Test pagination for list endpoints."""
        test_name = "test_GET_200_pagination"
        self.should_skip_test(test_name)

        # Create multiple resources to test pagination
        resources, path_parent_ids, headers = self._setup_test_resources(
            server, jwt_a, team_a, count=3
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

    # TODO Implement Pydantic models in a way that says: If these fields are here, validate them. If they aren't, omit them. If there are extra fields, that's a problem.
    # def test_GET_200_fields(self, server, jwt_a, team_a):
    #     """Test retrieving resources with the fields parameter."""
    #     test_name = "test_GET_200_fields"
    #     self.should_skip_test(test_name)

    #     # Create a resource
    #     resource, parent_ids, path_parent_ids, headers = self._setup_test_resources(
    #         server, jwt_a, team_a, count=1
    #     )[0]

    #     # Select a subset of fields
    #     subset_fields = self.required_fields[
    #         :2
    #     ]  # Just use the first two required fields
    #     fields_param = f"?{'&'.join([f'fields={field}' for field in subset_fields])}"

    #     # Test with single entity endpoint
    #     response = server.get(
    #         f"{self.get_detail_endpoint(resource['id'], path_parent_ids)}{fields_param}",
    #         headers=headers,
    #     )

    #     self._assert_response_status(
    #         response,
    #         200,
    #         "GET with fields parameter",
    #         f"{self.get_detail_endpoint(resource['id'], path_parent_ids)}{fields_param}",
    #     )

    #     entity = self._assert_entity_in_response(response)

    #     # Verify only the requested fields (plus id) are present
    #     expected_fields = set(subset_fields + ["id"])
    #     actual_fields = set(entity.keys())

    #     assert actual_fields.issubset(set(self.required_fields + ["id"])), (
    #         f"[{self.entity_name}] Response contains fields not in required fields list\n"
    #         f"Extra fields: {actual_fields - set(self.required_fields + ['id'])}\n"
    #         f"Entity: {entity}"
    #     )

    #     assert expected_fields.issubset(actual_fields), (
    #         f"[{self.entity_name}] Response missing requested fields\n"
    #         f"Missing fields: {expected_fields - actual_fields}\n"
    #         f"Entity: {entity}"
    #     )

    #     return entity

    def test_POST_422_batch(self, server, jwt_a, team_a, api_key=None):
        """Test batch creation with invalid entities fails."""
        test_name = "test_POST_422_batch"
        self.should_skip_test(test_name)

        # Create parent entities if required
        parent_ids = {}
        path_parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(server, jwt_a, team_a)
            for parent in self.parent_entities:
                if parent.name in parent_entities_dict:
                    parent_ids[parent.key] = parent_entities_dict[parent.name]["id"]
                    if parent.is_path:
                        path_parent_ids[f"{parent.name}_id"] = parent_entities_dict[
                            parent.name
                        ]["id"]

        # Valid entity
        valid_entity = {"name": self.generate_name()}

        # Add parent IDs to valid entity
        for parent in self.parent_entities:
            if parent.key in parent_ids:
                valid_entity[parent.key] = parent_ids[parent.key]

        if team_a and "team_id" in self.required_fields:
            valid_entity["team_id"] = team_a.get("id", None)

        # Invalid entity - missing required fields
        invalid_entity = {}  # Empty entity missing required fields

        # Create the batch payload
        batch_entities = [valid_entity, invalid_entity]
        nested_payload = {self.resource_name_plural: batch_entities}

        # Choose the appropriate authentication header
        headers = self._get_appropriate_headers(jwt_a, api_key)

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

    def test_POST_401(self, server):
        """Test creating resource without proper authorization."""
        test_name = "test_POST_401"
        self.should_skip_test(test_name)

        resource_name = f"Test {self.entity_name}"

        # Get fake parent_ids if required
        parent_ids = {}
        if self.has_parent_entities():
            for parent in self.parent_entities:
                parent_ids[parent.key] = str(uuid.uuid4())

        # Set a flag to inform create_payload this is for unauthorized test
        self._test_create_unauthorized = True

        try:
            # Create the payload using the child class implementation
            payload = self.create_payload(resource_name, parent_ids)

            # Test without authorization header
            response = server.post(self.get_create_endpoint(parent_ids), json=payload)
            self._assert_response_status(
                response,
                401,
                "POST (no auth)",
                self.get_create_endpoint(parent_ids),
                payload,
            )

            # Test with invalid token
            headers = self._auth_header("invalid.token")
            response = server.post(
                self.get_create_endpoint(parent_ids),
                json=payload,
                headers=headers,
            )
            self._assert_response_status(
                response,
                401,
                "POST (invalid auth)",
                self.get_create_endpoint(parent_ids),
                payload,
            )
        finally:
            # Clean up
            self._test_create_unauthorized = False

    def test_POST_403_system(self, server, jwt_a, team_a):
        """Test that system entity creation fails without API key."""
        test_name = "test_POST_403_system"
        self.should_skip_test(test_name)

        if not self.system_entity:
            pytest.skip("Not a system entity")

        # Generate a unique name for the test resource
        resource_name = self.generate_name()

        # Create parent entities if required
        parent_ids = {}
        path_parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(server, jwt_a, team_a)
            for parent in self.parent_entities:
                if parent.name in parent_entities_dict:
                    parent_ids[parent.key] = parent_entities_dict[parent.name]["id"]
                    if parent.is_path:
                        path_parent_ids[f"{parent.name}_id"] = parent_entities_dict[
                            parent.name
                        ]["id"]

        # Create the payload
        payload = self.create_payload(
            resource_name, parent_ids, team_a.get("id", None) if team_a else None
        )

        # Try to create with JWT instead of API key
        response = server.post(
            self.get_create_endpoint(path_parent_ids),
            json=payload,
            headers=self._auth_header(jwt_a),
        )

        # Assert it fails with 403
        self._assert_response_status(
            response,
            403,
            "POST (system entity without API key)",
            self.get_create_endpoint(path_parent_ids),
            payload,
        )

    def test_GET_200_list(self, server, jwt_a, team_a):
        """Test retrieving the list of available resources."""
        self.should_skip_test("test_GET_200_list")

        # Create an entity first to ensure there's something to list
        entity = self.test_POST_201(server, jwt_a, team_a)

        # Extract parent IDs from created entity
        parent_ids = {}
        for parent in self.parent_entities:
            if parent.key in entity:
                parent_ids[f"{parent.name}_id"] = entity[parent.key]

        response = server.get(
            self.get_list_endpoint(parent_ids), headers=self._auth_header(jwt_a)
        )

        self._assert_response_status(
            response, 200, "GET list", self.get_list_endpoint(parent_ids)
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

    def test_GET_200_id(self, server, jwt_a, team_a):
        """Test retrieving a specific resource by ID."""
        test_name = "test_GET_200_id"
        self.should_skip_test(test_name)

        # First create a resource
        resource = self.test_POST_201(server, jwt_a, team_a)

        # Extract parent IDs from created resource
        parent_ids = {}
        for parent in self.parent_entities:
            if parent.key in resource:
                parent_ids[f"{parent.name}_id"] = resource[parent.key]

        # Get the specific resource
        response = server.get(
            self.get_detail_endpoint(resource["id"], parent_ids),
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response,
            200,
            "GET by ID",
            self.get_detail_endpoint(resource["id"], parent_ids),
        )
        entity = self._assert_entity_in_response(response)

        # Verify ID matches
        assert entity["id"] == resource["id"], (
            f"[{self.entity_name}] Retrieved entity ID mismatch: expected '{resource['id']}', got '{entity['id']}'\n"
            f"Entity: {entity}"
        )

        # Verify name matches
        assert (
            entity[self.string_field_to_update] == resource[self.string_field_to_update]
        ), (
            f"[{self.entity_name}] Retrieved entity name mismatch: "
            f"expected '{resource[self.string_field_to_update]}', got '{entity[self.string_field_to_update]}'\n"
            f"Entity: {entity}"
        )

        return entity

    def test_GET_200_includes(self, server, jwt_a, team_a):
        """Test retrieving resources with their related entities using includes."""
        test_name = "test_GET_200_includes"
        self.should_skip_test(test_name)

        # First create a resource
        resource = self.test_POST_201(server, jwt_a, team_a)

        # Extract parent IDs from created resource
        path_parent_ids = {}
        for parent in self.parent_entities:
            if parent.is_path and parent.key in resource:
                path_parent_ids[f"{parent.name}_id"] = resource[parent.key]

        # Determine which entities to include based on parent entities
        includes = []
        for parent in self.parent_entities:
            includes.append(parent.name)

        if not includes:
            pytest.skip("No related entities to include")

        # Test includes with single entity endpoint
        include_params = {"include": includes}
        detail_endpoint = f"{self.get_detail_endpoint(resource['id'], path_parent_ids)}"

        if includes:
            detail_endpoint += f"?{'&'.join([f'include={inc}' for inc in includes])}"

        detail_response = server.get(
            detail_endpoint,
            headers=self._auth_header(jwt_a),
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
            if parent.name in includes and parent.key in entity:
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
        list_endpoint = self.get_list_endpoint(path_parent_ids)
        if includes:
            list_endpoint += f"?{'&'.join([f'include={inc}' for inc in includes])}"

        list_response = server.get(
            list_endpoint,
            headers=self._auth_header(jwt_a),
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
                            and parent.key in entity
                            and entity[parent.key] is not None
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

    def test_GET_404_nonexistent(self, server, jwt_a, team_a):
        """Test that API returns 404 for nonexistent resource (GET)."""
        test_name = "test_GET_404_nonexistent"
        self.should_skip_test(test_name)

        nonexistent_id = str(uuid.uuid4())

        # Create parent entities if required
        parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(server, jwt_a, team_a)
            for parent in self.parent_entities:
                if parent.name in parent_entities_dict:
                    parent_ids[f"{parent.name}_id"] = parent_entities_dict[parent.name][
                        "id"
                    ]

        response = server.get(
            self.get_detail_endpoint(nonexistent_id, parent_ids),
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response,
            404,
            "GET nonexistent resource",
            self.get_detail_endpoint(nonexistent_id, parent_ids),
        )

    def test_GET_404_other_user(self, server, jwt_a, team_a, jwt_b):
        """Test that users cannot see or access each other's resources."""
        test_name = "test_GET_404_other_user"
        self.should_skip_test(test_name)

        # First create a resource with user A
        resource_a = self.test_POST_201(server, jwt_a, team_a)

        # Extract parent IDs from created resource
        parent_ids = {}
        for parent in self.parent_entities:
            if parent.key in resource_a:
                parent_ids[f"{parent.name}_id"] = resource_a[parent.key]

        # Try to retrieve the resource with user B
        response = server.get(
            self.get_detail_endpoint(resource_a["id"], parent_ids),
            headers=self._auth_header(jwt_b),
        )

        # This should return 404 Not Found (not 403) since the user shouldn't even know it exists
        self._assert_response_status(
            response,
            404,
            "GET by different user",
            self.get_detail_endpoint(resource_a["id"], parent_ids),
        )

    def test_POST_200_search(self, server, jwt_a, team_a):
        """Test searching for resources using the search endpoint."""
        test_name = "test_POST_200_search"
        self.should_skip_test(test_name)

        if not self.supports_search:
            pytest.skip("Search not supported for this entity")

        # Create resources with known values for search
        resources = []
        search_term = f"Searchable {self.entity_name} {uuid.uuid4()}"

        # Create parent entities if required
        parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(server, jwt_a, team_a)
            parent_ids = {
                parent.key: parent_entities_dict[parent.name]["id"]
                for parent in self.parent_entities
                if parent.name in parent_entities_dict
            }

        # Extract parent IDs for path if needed
        path_parent_ids = {}
        for parent in self.parent_entities:
            if parent.is_path and parent.key in parent_ids:
                path_parent_ids[f"{parent.name}_id"] = parent_ids[parent.key]

        # Create a resource with a name we'll search for
        payload = self.create_payload(search_term, parent_ids, team_a.get("id", None))
        response = server.post(
            self.get_create_endpoint(path_parent_ids),
            json=payload,
            headers=self._auth_header(jwt_a),
        )
        self._assert_response_status(
            response,
            201,
            "POST (for search test)",
            self.get_create_endpoint(path_parent_ids),
            payload,
        )
        resources.append(self._assert_entity_in_response(response))

        # Create a search payload
        search_value = {"contains": search_term[:10]}
        search_payload = self.create_search_payload(
            self.string_field_to_update, search_value
        )

        # Perform the search
        response = server.post(
            self.get_search_endpoint(path_parent_ids),
            json=search_payload,
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response,
            200,
            "POST search",
            self.get_search_endpoint(path_parent_ids),
            search_payload,
        )
        entities = self._assert_entities_in_response(response)

        # Verify the created resource is in the results
        created_id = resources[0]["id"]
        found = False
        for e in entities:
            if e["id"] == created_id:
                found = True
                break

        assert found, (
            f"[{self.entity_name}] Created entity not found in search results\n"
            f"Entity ID: {created_id}\n"
            f"Search results: {entities}"
        )

        return entities

    def test_PUT_200(self, server, jwt_a, team_a, api_key=None):
        """Test updating a resource."""
        test_name = "test_PUT_200"
        self.should_skip_test(test_name)

        # Create an entity to update
        entity = self.test_POST_201(server, jwt_a, team_a, api_key)

        # Extract parent IDs from created entity
        parent_ids = {}
        for parent in self.parent_entities:
            if parent.key in entity:
                parent_ids[f"{parent.name}_id"] = entity[parent.key]

        # Prepare update data
        updated_name = f"Updated {self.entity_name} {uuid.uuid4()}"
        payload = self.nest_payload_in_entity(
            entity={self.string_field_to_update: updated_name}
        )

        # Choose the appropriate authentication header
        headers = self._get_appropriate_headers(jwt_a, api_key)

        # Make the update request
        response = server.put(
            self.get_update_endpoint(entity["id"], parent_ids),
            json=payload,
            headers=headers,
        )

        self._assert_response_status(
            response,
            200,
            "PUT update",
            self.get_update_endpoint(entity["id"], parent_ids),
            payload,
        )
        updated_entity = self._assert_entity_in_response(response)

        # Verify the update by checking the field was changed
        assert updated_entity[self.string_field_to_update] == updated_name, (
            f"[{self.entity_name}] Entity not updated: expected '{updated_name}', "
            f"got '{updated_entity[self.string_field_to_update]}'\n"
            f"Entity: {updated_entity}"
        )

        # Verify the update by retrieving the resource
        get_response = server.get(
            self.get_detail_endpoint(entity["id"], parent_ids),
            headers=headers,
        )
        self._assert_response_status(
            response=get_response,
            expected_status=200,
            operation="GET after update",
            endpoint=self.get_detail_endpoint(entity["id"], parent_ids),
        )

        retrieved_entity = self._assert_entity_in_response(get_response)
        assert retrieved_entity[self.string_field_to_update] == updated_name, (
            f"[{self.entity_name}] Entity update didn't persist: expected '{updated_name}', "
            f"got '{retrieved_entity[self.string_field_to_update]}'\n"
            f"Entity: {retrieved_entity}"
        )

        return updated_entity

    def test_PUT_403_system(self, server, jwt_a, team_a, api_key=None):
        """Test that system entity update fails without API key."""
        test_name = "test_PUT_403_system"
        self.should_skip_test(test_name)

        if not self.system_entity:
            pytest.skip("Not a system entity")

        # First create a resource using API key
        entity = self.test_POST_201(server, jwt_a, team_a, api_key)

        # Extract parent IDs if needed for the path
        path_parent_ids = {}
        for parent in self.parent_entities:
            if parent.is_path and parent.key in entity:
                path_parent_ids[f"{parent.name}_id"] = entity[parent.key]

        # Try to update with JWT instead of API key
        updated_name = f"Updated {self.entity_name} {uuid.uuid4()}"
        payload = self.nest_payload_in_entity(
            entity={self.string_field_to_update: updated_name}
        )

        response = server.put(
            self.get_update_endpoint(entity["id"], path_parent_ids),
            json=payload,
            headers=self._auth_header(jwt_a),
        )

        # Assert it fails with 403
        self._assert_response_status(
            response,
            403,
            "PUT (system entity without API key)",
            self.get_update_endpoint(entity["id"], path_parent_ids),
            payload,
        )

    def test_PUT_422(self, server, jwt_a, team_a):
        """Test updating a resource with invalid data."""
        test_name = "test_PUT_422"
        self.should_skip_test(test_name)

        # First create a resource
        resource = self.test_POST_201(server, jwt_a, team_a)

        # Extract parent IDs from created resource
        parent_ids = {}
        for parent in self.parent_entities:
            if parent.key in resource:
                parent_ids[f"{parent.name}_id"] = resource[parent.key]

        # Invalid update payload (wrong data type)
        invalid_value = 12345  # Number instead of string
        payload = self.nest_payload_in_entity(
            entity={self.string_field_to_update: invalid_value}
        )

        response = server.put(
            self.get_update_endpoint(resource["id"], parent_ids),
            json=payload,
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response,
            422,
            "PUT invalid update",
            self.get_update_endpoint(resource["id"], parent_ids),
            payload,
        )

    def test_DELETE_403_system(self, server, jwt_a, team_a, api_key=None):
        """Test that system entity deletion fails without API key."""
        test_name = "test_DELETE_403_system"
        self.should_skip_test(test_name)

        if not self.system_entity:
            pytest.skip("Not a system entity")

        # First create a resource using API key
        entity = self.test_POST_201(server, jwt_a, team_a, api_key)

        # Extract parent IDs if needed for the path
        path_parent_ids = {}
        for parent in self.parent_entities:
            if parent.is_path and parent.key in entity:
                path_parent_ids[f"{parent.name}_id"] = entity[parent.key]

        # Try to delete with JWT instead of API key
        response = server.delete(
            self.get_delete_endpoint(entity["id"], path_parent_ids),
            headers=self._auth_header(jwt_a),
        )

        # Assert it fails with 403
        self._assert_response_status(
            response,
            403,
            "DELETE (system entity without API key)",
            self.get_delete_endpoint(entity["id"], path_parent_ids),
        )

    def test_DELETE_204(self, server, jwt_a, team_a, api_key=None):
        """Test deleting a resource."""
        test_name = "test_DELETE_204"
        self.should_skip_test(test_name)

        # First create a resource
        resource = self.test_POST_201(server, jwt_a, team_a, api_key)

        # Extract parent IDs from created resource
        parent_ids = {}
        for parent in self.parent_entities:
            if parent.key in resource:
                parent_ids[f"{parent.name}_id"] = resource[parent.key]

        # Choose the appropriate authentication header
        headers = self._get_appropriate_headers(jwt_a, api_key)

        # Delete the resource
        response = server.delete(
            self.get_delete_endpoint(resource["id"], parent_ids),
            headers=headers,
        )

        self._assert_response_status(
            response,
            204,
            "DELETE",
            self.get_delete_endpoint(resource["id"], parent_ids),
        )

        # Verify the resource is deleted by trying to retrieve it
        verify_response = server.get(
            self.get_detail_endpoint(resource["id"], parent_ids),
            headers=headers,
        )

        self._assert_response_status(
            verify_response,
            404,
            "GET after DELETE",
            self.get_detail_endpoint(resource["id"], parent_ids),
        )

    def test_DELETE_404_other_user(self, server, jwt_a, team_a, jwt_b):
        """Test that users cannot delete each other's resources."""
        test_name = "test_DELETE_404_other_user"
        self.should_skip_test(test_name)

        # First create a resource with user A
        resource_a = self.test_POST_201(server, jwt_a, team_a)

        # Extract parent IDs from created resource
        parent_ids = {}
        for parent in self.parent_entities:
            if parent.key in resource_a:
                parent_ids[f"{parent.name}_id"] = resource_a[parent.key]

        # Try to delete the resource with user B
        response = server.delete(
            self.get_delete_endpoint(resource_a["id"], parent_ids),
            headers=self._auth_header(jwt_b),
        )

        # This should return 404 Not Found (not 403)
        self._assert_response_status(
            response,
            404,
            "DELETE by different user",
            self.get_delete_endpoint(resource_a["id"], parent_ids),
        )

        # Verify the resource wasn't deleted by checking with user A
        verify_response = server.get(
            self.get_detail_endpoint(resource_a["id"], parent_ids),
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            verify_response,
            200,
            "GET after DELETE attempt by different user",
            self.get_detail_endpoint(resource_a["id"], parent_ids),
        )

        entity = self._assert_entity_in_response(verify_response)

        # Verify ID matches
        assert entity["id"] == resource_a["id"], (
            f"[{self.entity_name}] Entity incorrectly deleted by different user\n"
            f"Expected ID: {resource_a['id']}\n"
            f"Entity: {entity}"
        )

    def test_POST_422_invalid_data(self, server, jwt_a, team_a):
        """Test that the API returns 422 with invalid data structure."""
        test_name = "test_POST_422_invalid_data"
        self.should_skip_test(test_name)

        # Create parent entities if required
        parent_ids = {}
        path_parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(server, jwt_a, team_a)
            for parent in self.parent_entities:
                if parent.name in parent_entities_dict:
                    parent_ids[parent.key] = parent_entities_dict[parent.name]["id"]
                    if parent.is_path:
                        path_parent_ids[f"{parent.name}_id"] = parent_entities_dict[
                            parent.name
                        ]["id"]

        # Invalid payload (missing required fields)
        payload = self.nest_payload_in_entity(entity={})

        response = server.post(
            self.get_create_endpoint(path_parent_ids),
            json=payload,
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response,
            422,
            "POST invalid data (missing fields)",
            self.get_create_endpoint(path_parent_ids),
            payload,
        )

        # Another invalid payload (wrong data type)
        invalid_value = 12345  # Number instead of string
        payload = self.nest_payload_in_entity(
            entity={self.string_field_to_update: invalid_value}
        )

        response = server.post(
            self.get_create_endpoint(path_parent_ids),
            json=payload,
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response,
            422,
            "POST invalid data (wrong type)",
            self.get_create_endpoint(path_parent_ids),
            payload,
        )

    def test_DELETE_404_nonexistent(self, server, jwt_a, team_a):
        """Test that API returns 404 for nonexistent resource (DELETE)."""
        test_name = "test_DELETE_404_nonexistent"
        self.should_skip_test(test_name)

        nonexistent_id = str(uuid.uuid4())

        # Create parent entities if required
        parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(server, jwt_a, team_a)
            for parent in self.parent_entities:
                if parent.name in parent_entities_dict:
                    parent_ids[f"{parent.name}_id"] = parent_entities_dict[parent.name][
                        "id"
                    ]

        response = server.delete(
            self.get_delete_endpoint(nonexistent_id, parent_ids),
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response,
            404,
            "DELETE nonexistent resource",
            self.get_delete_endpoint(nonexistent_id, parent_ids),
        )

    def test_GET_401(self, server):
        """Test that GET endpoint requires authentication."""
        test_name = "test_GET_401"
        self.should_skip_test(test_name)

        nonexistent_id = str(uuid.uuid4())

        # Use fake parent_ids if required
        parent_ids = {}
        if self.has_parent_entities():
            for parent in self.parent_entities:
                if parent.is_path:
                    parent_ids[f"{parent.name}_id"] = str(uuid.uuid4())

        # Test GET /v1/{endpoint} (list)
        response = server.get(self.get_list_endpoint(parent_ids))
        self._assert_response_status(
            response, 401, "GET list unauthorized", self.get_list_endpoint(parent_ids)
        )

        # Test GET /v1/{endpoint}/{id} (get)
        response = server.get(self.get_detail_endpoint(nonexistent_id, parent_ids))
        self._assert_response_status(
            response,
            401,
            "GET by ID unauthorized",
            self.get_detail_endpoint(nonexistent_id, parent_ids),
        )

    def test_PUT_401(self, server):
        """Test that PUT endpoint requires authentication."""
        test_name = "test_PUT_401"
        self.should_skip_test(test_name)

        nonexistent_id = str(uuid.uuid4())

        # Use fake parent_ids if required
        parent_ids = {}
        if self.has_parent_entities():
            for parent in self.parent_entities:
                if parent.is_path:
                    parent_ids[f"{parent.name}_id"] = str(uuid.uuid4())

        update_payload = self.nest_payload_in_entity(
            entity={self.string_field_to_update: "Updated Name"}
        )
        response = server.put(
            self.get_update_endpoint(nonexistent_id, parent_ids), json=update_payload
        )
        self._assert_response_status(
            response,
            401,
            "PUT unauthorized",
            self.get_update_endpoint(nonexistent_id, parent_ids),
            update_payload,
        )

    def test_PUT_404_other_user(self, server, jwt_a, team_a, jwt_b):
        """Test that users cannot update each other's resources."""
        test_name = "test_PUT_404_other_user"
        self.should_skip_test(test_name)

        # First create a resource with user A
        resource_a = self.test_POST_201(server, jwt_a, team_a)
        resource_name = resource_a[self.string_field_to_update]

        # Extract parent IDs from created resource
        parent_ids = {}
        for parent in self.parent_entities:
            if parent.key in resource_a:
                parent_ids[f"{parent.name}_id"] = resource_a[parent.key]

        # Try to update the resource with user B
        updated_name = f"Updated by B {uuid.uuid4()}"
        update_payload = self.nest_payload_in_entity(
            entity={self.string_field_to_update: updated_name}
        )

        response = server.put(
            self.get_update_endpoint(resource_a["id"], parent_ids),
            json=update_payload,
            headers=self._auth_header(jwt_b),
        )

        # This should return 404 Not Found (not 403)
        self._assert_response_status(
            response,
            404,
            "PUT by different user",
            self.get_update_endpoint(resource_a["id"], parent_ids),
            update_payload,
        )

        # Verify the resource wasn't updated by checking with user A
        verify_response = server.get(
            self.get_detail_endpoint(resource_a["id"], parent_ids),
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            verify_response,
            200,
            "GET after PUT attempt by different user",
            self.get_detail_endpoint(resource_a["id"], parent_ids),
        )

        entity = self._assert_entity_in_response(verify_response)

        # Verify name was not changed
        assert entity[self.string_field_to_update] == resource_name, (
            f"[{self.entity_name}] Entity was incorrectly updated by different user\n"
            f"Expected name: {resource_name}\n"
            f"Actual name: {entity[self.string_field_to_update]}\n"
            f"Entity: {entity}"
        )

    def test_PUT_404_nonexistent(self, server, jwt_a, team_a):
        """Test that API returns 404 for nonexistent resource (PUT)."""
        test_name = "test_PUT_404_nonexistent"
        self.should_skip_test(test_name)

        nonexistent_id = str(uuid.uuid4())

        # Create parent entities if required
        parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(server, jwt_a, team_a)
            for parent in self.parent_entities:
                if parent.name in parent_entities_dict:
                    parent_ids[f"{parent.name}_id"] = parent_entities_dict[parent.name][
                        "id"
                    ]

        payload = self.nest_payload_in_entity(
            entity={self.string_field_to_update: "Updated Name"}
        )
        response = server.put(
            self.get_update_endpoint(nonexistent_id, parent_ids),
            json=payload,
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response,
            404,
            "PUT nonexistent resource",
            self.get_update_endpoint(nonexistent_id, parent_ids),
            payload,
        )

    def test_DELETE_401(self, server):
        """Test that DELETE endpoint requires authentication."""
        test_name = "test_DELETE_401"
        self.should_skip_test(test_name)

        nonexistent_id = str(uuid.uuid4())

        # Use fake parent_ids if required
        parent_ids = {}
        if self.has_parent_entities():
            for parent in self.parent_entities:
                if parent.is_path:
                    parent_ids[f"{parent.name}_id"] = str(uuid.uuid4())

        response = server.delete(self.get_delete_endpoint(nonexistent_id, parent_ids))
        self._assert_response_status(
            response,
            401,
            "DELETE unauthorized",
            self.get_delete_endpoint(nonexistent_id, parent_ids),
        )

    def test_POST_404_nonexistent_parent(self, server, jwt_a, team_a):
        """Test creating a resource with a nonexistent parent."""
        test_name = "test_POST_404_nonexistent_parent"
        self.should_skip_test(test_name)

        if not self.has_parent_entities():
            pytest.skip("No parent entities for this resource")

        # Create a resource with nonexistent parent ID
        resource_name = self.generate_name()

        # Create payload with nonexistent parent IDs
        parent_ids = {}
        path_parent_ids = {}
        for parent in self.parent_entities:
            if not parent.nullable:
                nonexistent_id = str(uuid.uuid4())
                parent_ids[parent.key] = nonexistent_id
                if parent.is_path:
                    path_parent_ids[f"{parent.name}_id"] = nonexistent_id

        # Skip test if no non-nullable parents
        if not parent_ids:
            pytest.skip("No non-nullable parents for this resource")

        payload = self.create_payload(
            resource_name, parent_ids, team_a.get("id", None) if team_a else None
        )

        response = server.post(
            self.get_create_endpoint(path_parent_ids),
            json=payload,
            headers=self._auth_header(jwt_a),
        )

        # Only expect 404 if a non-nullable parent is missing
        self._assert_response_status(
            response,
            404,
            "POST with nonexistent parent",
            self.get_create_endpoint(path_parent_ids),
            payload,
        )

    def test_GET_404_nonexistent_parent(self, server, jwt_a, team_a):
        """Test listing resources for a nonexistent parent."""
        test_name = "test_GET_404_nonexistent_parent"
        self.should_skip_test(test_name)

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
            headers=self._auth_header(jwt_a),
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

    def test_POST_403_role_too_low(self, server, jwt_a, api_key=None):
        """Test creating a resource with insufficient permissions.

        This test is meant to be overridden by resources that require special permissions,
        such as those that can only be created with an API key or by admin users.
        """
        test_name = "test_POST_403_role_too_low"
        self.should_skip_test(test_name)

        # Base implementation is a no-op, child classes should override this
        # test if they have specific permission requirements
        pytest.skip(
            "This test should be overridden by resources with permission requirements"
        )

    # GraphQL testing methods
    def _build_gql_query(
        self,
        query_type,
        id_param=None,
        filter_param=None,
        parent_param=None,
        fields=None,
    ):
        """
        Build a GraphQL query with consistent formatting.

        Args:
            query_type (str): The GraphQL query type (singular or plural entity name)
            id_param (str, optional): ID for retrieving a specific resource
            filter_param (dict, optional): Filter parameters for search queries
            parent_param (dict, optional): Parent ID parameters for related resources
            fields (list, optional): Fields to include in the response, defaults to required_fields

        Returns:
            str: Formatted GraphQL query
        """
        # Use required fields by default
        fields = fields or self.required_fields
        camel_case_fields = [self.to_camel_case(field) for field in fields]
        fields_query = " ".join(camel_case_fields)

        # Build parameters string
        params = []
        if id_param:
            params.append(f'id: "{id_param}"')
        if parent_param:
            for key, value in parent_param.items():
                parent_id_field_camel = self.to_camel_case(key)
                params.append(f'{parent_id_field_camel}: "{value}"')
        if filter_param:
            # Construct filter string based on the filter_param dictionary
            filter_parts = []
            for key, value in filter_param.items():
                if isinstance(value, dict):
                    # Handle nested filters like {contains: "searchTerm"}
                    operation, term = next(iter(value.items()))
                    filter_parts.append(
                        f'{self.to_camel_case(key)}: {{ {operation}: "{term}" }}'
                    )
                else:
                    filter_parts.append(f'{self.to_camel_case(key)}: "{value}"')

            params.append(f'filter: {{ {", ".join(filter_parts)} }}')

        params_str = f'({", ".join(params)})' if params else ""

        return f"""
        query {{
            {query_type}{params_str} {{
                {fields_query}
            }}
        }}
        """

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
            input_data (dict): Input data for the mutation
            parent_param (dict, optional): Parent ID parameters
            fields (list, optional): Fields to include in the response, defaults to required_fields

        Returns:
            str: Formatted GraphQL mutation
        """
        if not fields:
            fields = self.required_fields

        camel_case_fields = [self.to_camel_case(field) for field in fields]
        fields_query = " ".join(camel_case_fields)

        # Build parameters string
        params = []
        if id_param:
            params.append(f'id: "{id_param}"')

        if parent_param:
            for key, value in parent_param.items():
                parent_id_field_camel = self.to_camel_case(key)
                params.append(f'{parent_id_field_camel}: "{value}"')

        if input_data:
            # Convert input data to camelCase and format for GraphQL
            input_parts = []
            for key, value in input_data.items():
                key_camel = self.to_camel_case(key)

                if isinstance(value, str):
                    input_parts.append(f'{key_camel}: "{value}"')
                elif value is None:
                    input_parts.append(f"{key_camel}: null")
                elif isinstance(value, (int, float, bool)):
                    input_parts.append(f"{key_camel}: {str(value).lower()}")
                elif isinstance(value, dict):
                    # For nested objects, serialize to JSON string
                    input_parts.append(f"{key_camel}: {json.dumps(value)}")
                else:
                    input_parts.append(f'{key_camel}: "{value}"')

            params.append(f'input: {{ {", ".join(input_parts)} }}')

        params_str = f'({", ".join(params)})' if params else ""

        return f"""
        mutation {{
            {mutation_type}{params_str} {{
                {fields_query}
            }}
        }}
        """

    def _build_gql_subscription(
        self,
        subscription_type,
        filter_param=None,
        fields=None,
    ):
        """
        Build a GraphQL subscription with consistent formatting.

        Args:
            subscription_type (str): The GraphQL subscription type
            filter_param (dict, optional): Filter parameters
            fields (list, optional): Fields to include in the response

        Returns:
            str: Formatted GraphQL subscription
        """
        if not fields:
            fields = self.required_fields

        camel_case_fields = [self.to_camel_case(field) for field in fields]
        fields_query = " ".join(camel_case_fields)

        # Build parameters string
        params = []
        if filter_param:
            # Construct filter string based on the filter_param dictionary
            filter_parts = []
            for key, value in filter_param.items():
                if isinstance(value, dict):
                    # Handle nested filters like {contains: "searchTerm"}
                    operation, term = next(iter(value.items()))
                    filter_parts.append(
                        f'{self.to_camel_case(key)}: {{ {operation}: "{term}" }}'
                    )
                else:
                    filter_parts.append(f'{self.to_camel_case(key)}: "{value}"')

            params.append(f'filter: {{ {", ".join(filter_parts)} }}')

        params_str = f'({", ".join(params)})' if params else ""

        return f"""
        subscription {{
            {subscription_type}{params_str} {{
                {fields_query}
            }}
        }}
        """

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

    def test_GQL_query_single(self, server, jwt_a, team_a):
        """Test retrieving a single resource using GraphQL."""
        test_name = "test_GQL_query_single"
        self.should_skip_test(test_name)

        # First create a resource
        resource = self.test_POST_201(server, jwt_a, team_a)

        # Determine the GraphQL query based on the resource type
        resource_type = self.entity_name.lower()

        # Prepare parent parameters if needed
        parent_param = {}
        for parent in self.parent_entities:
            if parent.key in resource:
                parent_param[parent.key] = resource[parent.key]

        # Generate query
        query = self._build_gql_query(
            query_type=resource_type, id_param=resource["id"], parent_param=parent_param
        )

        # Execute the GraphQL query
        response = server.post(
            "/graphql", json={"query": query}, headers=self._auth_header(jwt_a)
        )

        # Assert response
        data = self._assert_gql_response(response, "query single")

        # Check entity was returned
        assert resource_type in data, (
            f"[{self.entity_name}] GraphQL query response missing entity: {resource_type}\n"
            f"Response data: {data}"
        )

        gql_entity = data[resource_type]

        # Check ID matches
        assert gql_entity["id"] == resource["id"], (
            f"[{self.entity_name}] GraphQL query returned wrong entity\n"
            f"Expected ID: {resource['id']}\n"
            f"Actual ID: {gql_entity['id']}\n"
            f"Entity: {gql_entity}"
        )

        return gql_entity

    def test_GQL_query_list(self, server, jwt_a, team_a):
        """Test retrieving a list of resources using GraphQL."""
        test_name = "test_GQL_query_list"
        self.should_skip_test(test_name)

        # Create a resource to ensure there's something to list
        resource = self.test_POST_201(server, jwt_a, team_a)

        # Determine the GraphQL query based on the resource type
        resource_type_plural = self.resource_name_plural.lower()

        # Prepare parent parameters if needed
        parent_param = {}
        for parent in self.parent_entities:
            if parent.key in resource:
                parent_param[parent.key] = resource[parent.key]

        # Generate query
        query = self._build_gql_query(
            query_type=resource_type_plural, parent_param=parent_param
        )

        # Execute the GraphQL query
        response = server.post(
            "/graphql", json={"query": query}, headers=self._auth_header(jwt_a)
        )

        # Assert response
        data = self._assert_gql_response(response, "query list")

        # Check entities were returned
        assert resource_type_plural in data, (
            f"[{self.entity_name}] GraphQL query response missing entities: {resource_type_plural}\n"
            f"Response data: {data}"
        )

        gql_entities = data[resource_type_plural]
        assert isinstance(gql_entities, list), (
            f"[{self.entity_name}] GraphQL query should return a list of entities\n"
            f"Entities: {gql_entities}"
        )

        # Check created entity is in results
        found = False
        for entity in gql_entities:
            if entity["id"] == resource["id"]:
                found = True
                break

        assert found, (
            f"[{self.entity_name}] Created entity not found in GraphQL query results\n"
            f"Entity ID: {resource['id']}\n"
            f"Query results: {gql_entities}"
        )

        return gql_entities

    def test_GQL_query_filter(self, server, jwt_a, team_a):
        """Test filtering resources using GraphQL."""
        test_name = "test_GQL_query_filter"
        self.should_skip_test(test_name)

        # Create a resource with a specific name for filtering
        filter_term = f"Filterable {self.entity_name} {uuid.uuid4()}"
        resource = self.test_POST_201(server, jwt_a, team_a)

        # Update the resource to have the filter term
        parent_ids = {}
        for parent in self.parent_entities:
            if parent.key in resource:
                parent_ids[f"{parent.name}_id"] = resource[parent.key]

        update_payload = self.nest_payload_in_entity(
            entity={self.string_field_to_update: filter_term}
        )

        headers = self._get_appropriate_headers(jwt_a)

        update_response = server.put(
            self.get_update_endpoint(resource["id"], parent_ids),
            json=update_payload,
            headers=headers,
        )

        self._assert_response_status(
            update_response,
            200,
            "PUT (for GQL filter test)",
            self.get_update_endpoint(resource["id"], parent_ids),
            update_payload,
        )

        # Determine the GraphQL query based on the resource type
        resource_type_plural = self.resource_name_plural.lower()

        # Prepare filter for GraphQL
        filter_param = {self.string_field_to_update: {"contains": filter_term[:10]}}

        # Prepare parent parameters if needed
        parent_param = {}
        for parent in self.parent_entities:
            if parent.key in resource:
                parent_param[parent.key] = resource[parent.key]

        # Generate query
        query = self._build_gql_query(
            query_type=resource_type_plural,
            filter_param=filter_param,
            parent_param=parent_param,
        )

        # Execute the GraphQL query
        response = server.post(
            "/graphql", json={"query": query}, headers=self._auth_header(jwt_a)
        )

        # Assert response
        data = self._assert_gql_response(response, "query filter")

        # Check entities were returned
        assert resource_type_plural in data, (
            f"[{self.entity_name}] GraphQL filtered query response missing entities: {resource_type_plural}\n"
            f"Response data: {data}"
        )

        gql_entities = data[resource_type_plural]
        assert isinstance(gql_entities, list), (
            f"[{self.entity_name}] GraphQL filtered query should return a list of entities\n"
            f"Entities: {gql_entities}"
        )

        # Check filtered entity is in results
        found = False
        for entity in gql_entities:
            if entity["id"] == resource["id"]:
                found = True
                break

        assert found, (
            f"[{self.entity_name}] Filtered entity not found in GraphQL query results\n"
            f"Entity ID: {resource['id']}\n"
            f"Filter term: {filter_term}\n"
            f"Query results: {gql_entities}"
        )

        return gql_entities

    def test_GQL_mutation_create(self, server, jwt_a, team_a):
        """Test creating a resource using GraphQL mutation."""
        test_name = "test_GQL_mutation_create"
        self.should_skip_test(test_name)

        # Generate a unique name for the test resource
        resource_name = self.generate_name()

        # Create parent entities if required
        parent_ids = {}
        if self.has_parent_entities():
            parent_entities_dict = self.create_parent_entities(server, jwt_a, team_a)
            for parent in self.parent_entities:
                if parent.name in parent_entities_dict:
                    parent_ids[parent.key] = parent_entities_dict[parent.name]["id"]

        # Prepare input data
        input_data = {self.string_field_to_update: resource_name}

        # Add parent IDs to input data
        for parent in self.parent_entities:
            if parent.key in parent_ids:
                input_data[parent.key] = parent_ids[parent.key]

        if team_a and "team_id" in self.required_fields:
            input_data["team_id"] = team_a["id"]

        # Determine mutation type
        mutation_type = f"create{self.entity_name.capitalize()}"

        # Generate mutation
        mutation = self._build_gql_mutation(
            mutation_type=mutation_type, input_data=input_data
        )

        # Execute the GraphQL mutation
        response = server.post(
            "/graphql", json={"query": mutation}, headers=self._auth_header(jwt_a)
        )

        # Assert response
        data = self._assert_gql_response(response, "mutation create")

        # Check entity was created
        assert mutation_type in data, (
            f"[{self.entity_name}] GraphQL create mutation response missing result: {mutation_type}\n"
            f"Response data: {data}"
        )

        gql_entity = data[mutation_type]

        # Check name matches
        name_camel = self.to_camel_case(self.string_field_to_update)
        assert name_camel in gql_entity, (
            f"[{self.entity_name}] GraphQL created entity missing name field\n"
            f"Entity: {gql_entity}"
        )
        assert gql_entity[name_camel] == resource_name, (
            f"[{self.entity_name}] GraphQL created entity has wrong name\n"
            f"Expected: {resource_name}\n"
            f"Actual: {gql_entity[name_camel]}\n"
            f"Entity: {gql_entity}"
        )

        # Verify entity exists via REST API
        entity_id = gql_entity["id"]

        # Extract parent IDs for the path if needed
        path_parent_ids = {}
        for parent in self.parent_entities:
            if parent.is_path and parent.key in input_data:
                path_parent_ids[f"{parent.name}_id"] = input_data[parent.key]

        verify_response = server.get(
            self.get_detail_endpoint(entity_id, path_parent_ids),
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            verify_response,
            200,
            "GET after GQL create",
            self.get_detail_endpoint(entity_id, path_parent_ids),
        )

        return gql_entity

    def test_GQL_mutation_update(self, server, jwt_a, team_a):
        """Test updating a resource using GraphQL mutation."""
        test_name = "test_GQL_mutation_update"
        self.should_skip_test(test_name)

        # First create a resource
        resource = self.test_POST_201(server, jwt_a, team_a)

        # Generate a new name for update
        updated_name = f"Updated via GraphQL {uuid.uuid4()}"

        # Prepare input data
        input_data = {self.string_field_to_update: updated_name}

        # Determine mutation type
        mutation_type = f"update{self.entity_name.capitalize()}"

        # Generate mutation
        mutation = self._build_gql_mutation(
            mutation_type=mutation_type, id_param=resource["id"], input_data=input_data
        )

        # Execute the GraphQL mutation
        response = server.post(
            "/graphql", json={"query": mutation}, headers=self._auth_header(jwt_a)
        )

        # Assert response
        data = self._assert_gql_response(response, "mutation update")

        # Check entity was updated
        assert mutation_type in data, (
            f"[{self.entity_name}] GraphQL update mutation response missing result: {mutation_type}\n"
            f"Response data: {data}"
        )

        gql_entity = data[mutation_type]

        # Check name was updated
        name_camel = self.to_camel_case(self.string_field_to_update)
        assert name_camel in gql_entity, (
            f"[{self.entity_name}] GraphQL updated entity missing name field\n"
            f"Entity: {gql_entity}"
        )
        assert gql_entity[name_camel] == updated_name, (
            f"[{self.entity_name}] GraphQL updated entity has wrong name\n"
            f"Expected: {updated_name}\n"
            f"Actual: {gql_entity[name_camel]}\n"
            f"Entity: {gql_entity}"
        )

        # Verify entity was updated via REST API
        path_parent_ids = {}
        for parent in self.parent_entities:
            if parent.is_path and parent.key in resource:
                path_parent_ids[f"{parent.name}_id"] = resource[parent.key]

        verify_response = server.get(
            self.get_detail_endpoint(resource["id"], path_parent_ids),
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            verify_response,
            200,
            "GET after GQL update",
            self.get_detail_endpoint(resource["id"], path_parent_ids),
        )

        entity = self._assert_entity_in_response(verify_response)
        assert entity[self.string_field_to_update] == updated_name, (
            f"[{self.entity_name}] REST API entity not updated after GraphQL mutation\n"
            f"Expected name: {updated_name}\n"
            f"Actual name: {entity[self.string_field_to_update]}\n"
            f"Entity: {entity}"
        )

        return gql_entity

    def test_GQL_mutation_delete(self, server, jwt_a, team_a):
        """Test deleting a resource using GraphQL mutation."""
        test_name = "test_GQL_mutation_delete"
        self.should_skip_test(test_name)

        # First create a resource
        resource = self.test_POST_201(server, jwt_a, team_a)

        # Determine mutation type
        mutation_type = f"delete{self.entity_name.capitalize()}"

        # Generate mutation
        mutation = self._build_gql_mutation(
            mutation_type=mutation_type,
            id_param=resource["id"],
            fields=["id"],  # Only return ID for deletion
        )

        # Execute the GraphQL mutation
        response = server.post(
            "/graphql", json={"query": mutation}, headers=self._auth_header(jwt_a)
        )

        # Assert response
        data = self._assert_gql_response(response, "mutation delete")

        # Verify entity is deleted via REST API
        path_parent_ids = {}
        for parent in self.parent_entities:
            if parent.is_path and parent.key in resource:
                path_parent_ids[f"{parent.name}_id"] = resource[parent.key]

        verify_response = server.get(
            self.get_detail_endpoint(resource["id"], path_parent_ids),
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            verify_response,
            404,
            "GET after GQL delete",
            self.get_detail_endpoint(resource["id"], path_parent_ids),
        )

        return data[mutation_type]

    def test_GQL_subscription(self, server, jwt_a, team_a):
        """Test GraphQL subscription format (actual WebSocket testing is done elsewhere)."""
        test_name = "test_GQL_subscription"
        self.should_skip_test(test_name)

        # Format a subscription request for testing syntax only
        # Note: Actually testing WebSocket subscriptions requires a different setup

        # Create entity type name
        entity_type = self.entity_name.lower()

        # Create subscription types based on entity name
        created_subscription = f"{entity_type}Created"
        updated_subscription = f"{entity_type}Updated"
        deleted_subscription = f"{entity_type}Deleted"

        # Generate filter for testing
        filter_param = {"team_id": str(uuid.uuid4())}  # Fake team ID for demonstration

        # Generate subscriptions
        created_sub = self._build_gql_subscription(
            subscription_type=created_subscription, filter_param=filter_param
        )

        updated_sub = self._build_gql_subscription(
            subscription_type=updated_subscription,
            filter_param={"id": str(uuid.uuid4())},  # Filter for specific entity
        )

        deleted_sub = self._build_gql_subscription(
            subscription_type=deleted_subscription
        )

        # Simply verify the subscription syntax is valid (actual testing would require WebSockets)
        assert (
            created_sub and updated_sub and deleted_sub
        ), f"[{self.entity_name}] Failed to generate valid GraphQL subscription queries"

        # Return sample subscription queries for reference
        return {
            "created_subscription": created_sub,
            "updated_subscription": updated_sub,
            "deleted_subscription": deleted_sub,
        }

    def create_parent_entities(self, server, jwt_a, team_a):
        """Create parent entities if required for testing this resource.

        This method must be implemented by child classes that require parent entities.

        Args:
            server: Test server
            jwt_a: JWT for authentication
            team_a: Team information

        Returns:
            dict: A dictionary of created parent entities with their IDs
        """
        if not self.has_parent_entities():
            return {}

        raise NotImplementedError(
            f"Child classes requiring parent entities must implement create_parent_entities"
        )
