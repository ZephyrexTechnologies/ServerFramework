# API Endpoint Testing Framework

This document outlines the patterns and best practices for testing API endpoints using the `AbstractEndpointTest` class. This framework provides a comprehensive approach to testing RESTful and GraphQL endpoints with minimal boilerplate code for new resources.

## Core Testing Philosophy

The endpoint testing framework follows several key principles:

1. **Completeness**: Tests cover the full API surface, including all standard CRUD operations
2. **Consistency**: Tests ensure consistent behavior across resources and endpoints
3. **Efficiency**: The framework reduces duplicated test code through abstraction
4. **Maintainability**: Common patterns are centralized for easier updates
5. **Coverage**: Tests verify positive scenarios, error handling, validation, and edge cases

## AbstractEndpointTest Class

The `AbstractEndpointTest` class serves as the foundation for testing all API endpoints. It provides:

- Standard CRUD operation tests (create, read, update, delete)
- Batch operations support
- Nested resource handling
- Authentication testing
- Parent-child relationship testing
- GraphQL integration
- Data validation testing

### Class Configuration

When creating a test class for a specific resource, you must configure the following class attributes:

```python
class ConversationEndpointTest(AbstractEndpointTest):
    # Base endpoint path (without /v1 prefix)
    base_endpoint = "conversation"
    
    # Entity name in singular form
    entity_name = "conversation"
    
    # Field to use for update operations
    string_field_to_update = "name"
    
    # Required fields to verify in responses
    required_fields = ["id", "name", "created_at", "project_id"]
    
    # True if entity requires API Key authentication instead of JWT
    system_entity = False
    
    # Parent entity configurations
    parent_entities = [
        ParentEntity(name="project", key="project_id", is_path=True)
    ]
    
    # Tests to skip if needed
    skip_tests = [
        SkippedTest(name="test_GET_200_fields", reason="Fields parameter not implemented")
    ]
    
    # Implement create_parent_entities method for nested resources
    def create_parent_entities(self, server, jwt_a, team_a):
        """Create parent entities required for testing this resource."""
        # Create a project to use for conversation testing
        project_payload = {"name": f"Test Project {uuid.uuid4()}"}
        
        if team_a and "team_id" in project_payload:
            project_payload["team_id"] = team_a.get("id", None)
            
        nested_payload = {"project": project_payload}
        
        response = server.post(
            "/v1/project", 
            json=nested_payload,
            headers=self._auth_header(jwt_a)
        )
        
        assert response.status_code == 201
        project = response.json()["project"]
        
        return {"project": project}
```

### Included Test Methods

The `AbstractEndpointTest` class provides these standard test methods:

#### Basic CRUD Tests
- `test_POST_201`: Create resource successfully
- `test_GET_200_list`: List resources successfully
- `test_GET_200_id`: Get a specific resource successfully
- `test_PUT_200`: Update a resource successfully
- `test_DELETE_204`: Delete a resource successfully

#### Error Cases
- `test_POST_401`: Create without authentication
- `test_POST_422_invalid_data`: Create with invalid data
- `test_PUT_422`: Update with invalid data
- `test_PUT_404_nonexistent`: Update nonexistent resource
- `test_GET_404_nonexistent`: Get nonexistent resource
- `test_DELETE_404_nonexistent`: Delete nonexistent resource

#### Parent Resource Tests
- `test_POST_404_nonexistent_parent`: Create with nonexistent parent
- `test_GET_404_nonexistent_parent`: List resources with nonexistent parent

#### Bulk Operations
- `test_POST_201_batch`: Create multiple resources in batch
- `test_PUT_200_batch`: Update multiple resources in batch
- `test_DELETE_204_batch`: Delete multiple resources in batch
- `test_POST_422_batch`: Create batch with invalid resources

#### Advanced Features
- `test_POST_201_null_parents`: Create with nullable parent fields
- `test_GET_200_includes`: Get resources with included related entities
- `test_GET_200_fields`: Get resources with specific fields
- `test_GET_200_pagination`: Test pagination for list endpoints
- `test_POST_200_search`: Search for resources

#### Multi-user Testing
- `test_GET_404_other_user`: Get another user's resource
- `test_PUT_404_other_user`: Update another user's resource
- `test_DELETE_404_other_user`: Delete another user's resource

#### System Entity Tests
- `test_POST_403_system`: Create system entity without API key
- `test_PUT_403_system`: Update system entity without API key
- `test_DELETE_403_system`: Delete system entity without API key

#### GraphQL Integration
- `test_GQL_query_single`: Test GraphQL single resource query
- `test_GQL_query_list`: Test GraphQL list resources query
- `test_GQL_query_filter`: Test GraphQL filtered query
- `test_GQL_mutation_create`: Test GraphQL resource creation
- `test_GQL_mutation_update`: Test GraphQL resource update
- `test_GQL_mutation_delete`: Test GraphQL resource deletion
- `test_GQL_subscription`: Verify GraphQL subscription format

### Skipping Tests

Tests can be skipped by adding them to the `skip_tests` class attribute:

```python
skip_tests = [
    SkippedTest(name="test_GET_200_fields", reason="Fields parameter not supported"),
    SkippedTest(name="test_POST_200_search", reason="Search not implemented")
]
```

### Handling Nested Resources

For testing nested resources, proper configuration of the `parent_entities` attribute is essential. Each parent entity must be defined using the `ParentEntity` class:

```python
ParentEntity(
    name="project",      # Name of the parent entity
    key="project_id",    # Field name in this entity for the parent ID
    nullable=False,      # True if the parent can be null
    system=False,        # True if parent is a system entity
    is_path=True         # True if parent ID is included in URL path
)
```

The `is_path` parameter is especially important as it determines whether the parent ID is included in the URL path for nested resources.

For resources with parent entities, you must implement the `create_parent_entities` method to create the necessary parent resources for testing.

## Test Execution Flow

Each test in the `AbstractEndpointTest` class follows this general flow:

1. **Setup**: Create any prerequisite resources (e.g., parent entities)
2. **Test Data Generation**: Generate test data using `ExampleGenerator` or custom logic
3. **Request Execution**: Make API request with appropriate authentication
4. **Assertion**: Verify response status, structure, and content
5. **Verification**: For operations that modify data, verify the changes with additional requests

## Customization Points

Child classes can customize testing behavior through:

1. **Class Attributes**: Configure basic resource information
2. **Helper Methods**: Implement methods like `create_parent_entities`
3. **Test Skip List**: Skip specific tests that don't apply to a resource
4. **Method Overrides**: Override test methods if necessary

## Authentication Patterns

Tests handle different authentication types automatically:

- **JWT Authentication**: Used by default
- **API Key Authentication**: Used for system entities (when `system_entity = True`)

## URL Path Resolution

The framework automatically handles the construction of endpoint URLs based on the resource configuration:

1. **Standard Resources**: `/v1/resource` and `/v1/resource/{id}`
2. **Nested Resources**: `/v1/parent/{parent_id}/resource` and `/v1/parent/{parent_id}/resource/{id}`

## Payload Formatting

The `nest_payload_in_entity` method ensures that request payloads follow the required format as defined in EP.schema.md:

- Single resource creation: `{resource_name: {...}}`
- Batch creation: `{resource_name_plural: [{...}, {...}]}`
- Batch update: `{resource_name: {...}, target_ids: ["id1", "id2"]}`
- Batch delete: `{target_ids: ["id1", "id2"]}`

## Response Validation

Each test validates that responses follow the expected patterns:

1. **Status Codes**: Verifies appropriate status codes for operations
2. **Response Format**: Confirms response structure matches expected format
3. **Required Fields**: Ensures all required fields are present in responses
4. **Entity Relationships**: Verifies correct parent/child relationships

## Test Data Generation

The framework uses `ExampleGenerator` to create realistic test data with:

- Unique identifiers for test resources
- Meaningful field values based on field names
- Appropriate data types for each field

## Integration with GraphQL

For GraphQL testing, the framework provides methods to:

1. Build properly formatted GraphQL queries and mutations
2. Convert field names between snake_case (REST) and camelCase (GraphQL)
3. Verify GraphQL response structures

## Examples

### Basic Resource Test

```python
class ProjectEndpointTest(AbstractEndpointTest):
    base_endpoint = "project"
    entity_name = "project"
    string_field_to_update = "name"
    required_fields = ["id", "name", "created_at"]
```

### Nested Resource Test

```python
class MessageEndpointTest(AbstractEndpointTest):
    base_endpoint = "message"
    entity_name = "message"
    string_field_to_update = "content"
    required_fields = ["id", "content", "created_at", "conversation_id"]
    
    parent_entities = [
        ParentEntity(name="conversation", key="conversation_id", is_path=True)
    ]
    
    def create_parent_entities(self, server, jwt_a, team_a):
        # Create a project first
        project_response = server.post(
            "/v1/project",
            json={"project": {"name": f"Test Project {uuid.uuid4()}"}},
            headers=self._auth_header(jwt_a)
        )
        assert project_response.status_code == 201
        project = project_response.json()["project"]
        
        # Then create a conversation under the project
        conversation_response = server.post(
            f"/v1/project/{project['id']}/conversation",
            json={"conversation": {"name": f"Test Conversation {uuid.uuid4()}"}},
            headers=self._auth_header(jwt_a)
        )
        assert conversation_response.status_code == 201
        conversation = conversation_response.json()["conversation"]
        
        return {"conversation": conversation}
```

### System Entity Test

```python
class ProviderEndpointTest(AbstractEndpointTest):
    base_endpoint = "provider"
    entity_name = "provider"
    string_field_to_update = "name"
    required_fields = ["id", "name", "created_at"]
    system_entity = True  # Uses API key auth instead of JWT
```

## Best Practices

1. **Complete Test Coverage**: Create test classes for all resources in EP.schema.md
2. **Proper Parent Entity Configuration**: Correctly define all parent-child relationships
3. **Generate Quality Test Data**: Use meaningful data that exercises validations
4. **Efficient Test Setup**: Minimize database operations in test setup
5. **Consistent Assertions**: Use the assertion helpers provided by the framework
6. **Resource Cleanup**: Properly clean up resources after tests
7. **Skip Appropriately**: Skip tests only when they truly don't apply
8. **Document Customizations**: Comment any overridden methods or unusual configurations

## Implementation Notes

1. **Test Independence**: Tests are designed to be independent; each creates its own resources
2. **Error Clarity**: Error messages include detailed context for easier debugging
3. **Flexibility**: The framework supports all endpoint patterns in EP.schema.md and EP.patterns.md
4. **Path Validation**: Endpoint URLs are verified against patterns in EP.schema.md