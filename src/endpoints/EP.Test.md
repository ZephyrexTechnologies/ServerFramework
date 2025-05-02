# API Endpoint Testing Framework (`AbstractEPTest`)

This document outlines the patterns and best practices for testing API endpoints using the `AbstractEndpointTest` class, located in `src/endpoints/AbstractEPTest.py`. This framework provides a comprehensive approach to testing RESTful and GraphQL endpoints with minimal boilerplate code for new resources.

## Core Testing Philosophy

The endpoint testing framework follows several key principles:

1.  **Completeness**: Tests cover the full API surface, including all standard CRUD operations, batch operations, search, and GraphQL equivalents.
2.  **Consistency**: Tests ensure consistent behavior, request/response formats, and error handling across resources and endpoints.
3.  **Efficiency**: The framework reduces duplicated test code through abstraction and helper methods.
4.  **Maintainability**: Common patterns and assertion logic are centralized for easier updates.
5.  **Coverage**: Tests verify positive scenarios, error handling (auth, validation, not found, permissions), pagination, field selection, includes, and edge cases like parent entity handling.

## AbstractEndpointTest Class

The `AbstractEndpointTest` class serves as the foundation for testing all API endpoints. It provides:

- Standard REST CRUD operation tests (create, read, update, delete)
- Batch operations support
- Nested resource handling (path parameters, parent ID checks)
- Authentication testing (JWT and API Key)
- Parent-child relationship testing (including null parents)
- GraphQL integration (queries, mutations, subscriptions)
- Data validation testing (422 errors)
- Multi-user permission testing (preventing access to other users' resources)
- Helper methods for generating data, formatting payloads, building URLs, and making assertions
- Intelligent test data generation using `faker`

## Base Class (`AbstractTest`)

`AbstractEPTest` inherits from `AbstractTest`, gaining access to test categorization, configuration, lifecycle hooks, common assertions, and test skipping functionality. See `Framework.Test.md` for details.

## Class Configuration

When creating a test class for a specific resource endpoint, you must configure the following class attributes:

```python
from endpoints.AbstractEPTest import AbstractEndpointTest, ParentEntity
from AbstractTest import TestCategory, TestClassConfig, SkippedTest

class ConversationEndpointTest(AbstractEndpointTest):
    # Base endpoint path (e.g., "conversation", not "/v1/conversation")
    base_endpoint = "conversation"

    # Entity name in singular form (used for payload nesting, e.g., {"conversation": {...}})
    entity_name = "conversation"

    # Field name (string type) to use for basic update tests
    string_field_to_update = "name"

    # List of field names expected in a standard GET response for this entity
    required_fields = ["id", "name", "created_at", "project_id"]

    # Set to True if the endpoint uses API Key auth instead of JWT (e.g., system entities)
    system_entity = False

    # Configure parent entities for nested resources or foreign key checks
    parent_entities = [
        ParentEntity(name="project", key="project_id", is_path=True)
    ]

    # GraphQL: Additional required parameters for GQL operations beyond parent entities
    required_graphql_params: Dict[str, Any] = {}

    # Search: Set to False if the resource doesn't support POST /search
    supports_search: bool = True
    # Search: List of fields usable in search tests
    searchable_fields: List[str] = ["name"]
    # Search: Example value to use when testing search
    search_example_value: str = "Test Search Query"
    
    # Optional test configuration - inherited from AbstractTest
    test_config = TestClassConfig(
        categories=[TestCategory.INTEGRATION],  # Test categories
        timeout=60,                            # Timeout in seconds
        cleanup_after_each=True                # Clean up resources after each test
    )

    # Optionally skip tests (inherited from AbstractTest)
    skip_tests = [
        # SkippedTest(name="test_GET_200_fields", reason="Fields parameter not implemented", jira_ticket="AGI-123")
    ]

    # IMPORTANT: Implement if parent_entities is not empty
    def create_parent_entities(self, server, admin_a_jwt, team_a):
        """Create parent entities required for testing this resource."""
        # Use the `server` (TestClient) and `admin_a_jwt` to make API calls
        # to create the necessary parent(s) defined in `parent_entities`.
        # Must return a dictionary mapping parent entity names to their created dicts.
        # Example:
        project_payload = {"project": {"name": f"Test Project {uuid.uuid4()}`"}} 
        response = server.post("/v1/project", json=project_payload, headers=self._auth_header(admin_a_jwt))
        assert response.status_code == 201
        project = response.json()["project"]
        return {"project": project}
```

## Provided Fixtures

`AbstractEPTest` relies heavily on fixtures provided by `conftest.py`:

- `server`: The FastAPI `TestClient` instance.
- `admin_a`, `user_b`: Dictionary representations of created user records.
- `admin_a_jwt`, `jwt_b`: JWT tokens corresponding to `admin_a` and `user_b`.
- `team_a`, `team_b`: Dictionary representations of created team records.
- `api_key`: (Implicitly used via environment for system entity tests).
- `db_session`, `requester_id`: Available but less commonly used directly in EP tests.

## Included Test Methods

`AbstractEPTest` provides a wide array of tests covering REST and GraphQL interactions:

#### Basic CRUD & Batch (REST)
- `test_POST_201`: Create resource, validating response structure and audit fields.
- `test_POST_201_null_parents`: Create resource with nullable parents set to null.
- `test_POST_201_batch`: Create multiple resources.
- `test_GET_200_list`: List resources.
- `test_GET_200_id`: Get a specific resource.
- `test_PUT_200`: Update a resource.
- `test_PUT_200_batch`: Update multiple resources.
- `test_DELETE_204`: Delete a resource.
- `test_DELETE_204_batch`: Delete multiple resources.

#### Advanced Features & Error Cases (REST)
- `test_GET_200_pagination`: Test `limit` and `offset`.
- `test_GET_200_fields`: Test `fields` parameter (currently xfailed).
- `test_GET_200_includes`: Test `include` parameter (currently xfailed).
- `test_POST_200_search`: Test the `/search` endpoint (currently xfailed).
- `test_POST_401`/`test_GET_401`/`test_PUT_401`/`test_DELETE_401`: Test operations without authentication.
- `test_POST_403_system`/`test_PUT_403_system`/`test_DELETE_403_system`: Test modifying system entities without API key.
- `test_POST_422_invalid_data`: Test creating with invalid data.
- `test_POST_422_batch`: Test batch creating with invalid data (currently xfailed).
- `test_PUT_422`: Test updating with invalid data.
- `test_GET_404_nonexistent`/`test_PUT_404_nonexistent`/`test_DELETE_404_nonexistent`: Test operations on non-existent IDs.
- `test_GET_404_other_user`/`test_PUT_404_other_user`/`test_DELETE_404_other_user`: Test accessing another user's resource.
- `test_POST_404_nonexistent_parent`/`test_GET_404_nonexistent_parent`: Test operations with an invalid parent ID.
- `test_POST_403_role_too_low`: Test permission denied based on role (if applicable).

#### GraphQL Tests
- `test_GQL_query_single`: Test single resource query.
- `test_GQL_query_list`: Test list resource query.
- `test_GQL_query_filter`: Test filtering in list query (currently xfailed).
- `test_GQL_mutation_create`: Test create mutation (currently xfailed).
- `test_GQL_mutation_update`: Test update mutation (currently xfailed).
- `test_GQL_mutation_delete`: Test delete mutation (currently xfailed).
- `test_GQL_subscription`: Verify GraphQL subscription format/structure.

*(Note: Several GraphQL and advanced REST tests are marked as `xfail` due to potential pending implementation or known issues like #37, #38, #39, #40, #41, #59. These should be addressed as features are completed.)*

## Test Data Generation

The `generate_test_data` method makes intelligent decisions about what data to generate based on field types and naming conventions. For example:
- Name fields receive randomized names
- Email fields receive valid email addresses
- Boolean fields receive True/False values

## Skipping Tests

Use the `skip_tests` class attribute (inherited from `AbstractTest`) to skip tests that are not applicable to the specific endpoint being tested.

```python
# In ResourceEndpointTest class
skip_tests = [
    SkippedTest(name="test_POST_200_search", reason="Search not implemented for Resource", jira_ticket="AGI-123"),
    SkippedTest(name="test_GQL_query_list", reason="GraphQL not enabled for Resource")
]
```

## Handling Nested Resources

1.  Define parent(s) in the `parent_entities` list.
2.  Set `is_path=True` for the parent whose ID is part of the URL path.
3.  Implement the `create_parent_entities` method to create the necessary parent resource(s) using the `server` test client.
4.  The framework automatically constructs nested URLs and includes parent IDs in payloads and assertions where appropriate.

## Test Execution Flow

Most tests follow this pattern:

1.  **Check Skip**: Call `self.reason_to_skip_test(test_name)`.
2.  **Setup**: Call `create_parent_entities` if needed. Create initial test resource(s) using the `server` fixture and helper methods (`_setup_test_resources`, `create_payload`).
3.  **Execute**: Make the target API request (POST, GET, PUT, DELETE, GraphQL) using the `server` fixture and appropriate headers (`_auth_header`, `_api_key_header`).
4.  **Assert Status**: Verify the HTTP status code using `_assert_response_status`.
5.  **Assert Response Body**: Verify the structure and content of the JSON response using helpers like `_assert_entity_in_response`, `_assert_entities_in_response`.
6.  **Assert Side Effects**: Verify database state changes or relationships (e.g., `_assert_parent_ids_match`, `_assert_has_created_by_user_id`).

## Helper Methods

`AbstractEPTest` provides numerous internal helper methods (`_` prefix) for common tasks:

- URL construction (`get_list_endpoint`, `get_detail_endpoint`, etc.)
- Payload generation and nesting (`generate_test_data`, `create_payload`, `nest_payload_in_entity`)
- Authentication header generation (`_auth_header`, `_api_key_header`)
- Response assertion (`_assert_response_status`, `_assert_entity_in_response`, etc.)
- GraphQL query/mutation building (`_build_gql_query`, `_build_gql_mutation`)
- Data extraction (`_extract_parent_ids`)

## Best Practices

1.  **Configure Accurately**: Ensure `base_endpoint`, `entity_name`, `required_fields`, and `parent_entities` accurately reflect the endpoint being tested.
2.  **Implement `create_parent_entities`**: If testing a nested resource, provide a correct implementation.
3.  **Use Helpers**: Leverage the built-in test methods and helper functions.
4.  **Skip Appropriately**: Skip tests for features explicitly not supported by the endpoint.
5.  **Add Custom Tests**: Add new test methods for custom routes or complex logic not covered by the standard tests.
6.  **Use TestCategory**: Categorize your tests appropriately to enable selective test execution.
7.  **Leverage Common Assertions**: Use the common assertion methods from AbstractTest for entity validation.