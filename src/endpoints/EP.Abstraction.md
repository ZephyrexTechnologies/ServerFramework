# Endpoint Layer Abstraction

This document covers the abstractions used in the Endpoint Layer of the application, including the AbstractEndpointRouter and AbstractEPTest components.

## AbstractEndpointRouter

The `AbstractEndpointRouter` provides a standardized implementation of RESTful endpoints following established patterns for resource operations. It handles common CRUD operations, nested resources, error handling, and documentation.

### Core Functionality

The AbstractEndpointRouter:

1. Creates standardized CRUD endpoints for resources
2. Supports batch operations for create, update, and delete
3. Manages request/response formats consistently
4. Provides error handling across all endpoints
5. Generates documentation with examples
6. Supports various authentication methods
7. Enables parent-child relationship modeling through nested resources

### Key Components

#### AbstractEPRouter Class

```python
class AbstractEPRouter(APIRouter, Generic[T]):
    """
    Abstract endpoint router that implements standard CRUD operations following the patterns
    outlined in EP.schema.md and EP.patterns.md.

    This class provides a reusable implementation of standard API endpoints
    to reduce code duplication across resource-based routers. It follows
    RESTful patterns and provides consistent behavior across different resources.
    """
```

#### Authentication Types

```python
class AuthType(Enum):
    """Authentication types supported by the API."""
    NONE = "none"
    JWT = "jwt"
    API_KEY = "api_key"
    BASIC = "basic"
```

#### Error Handling

```python
class ResourceOperationError(Exception):
    """Base exception for resource operation errors."""

class ResourceNotFoundError(ResourceOperationError):
    """Exception raised when a resource is not found."""

class ResourceConflictError(ResourceOperationError):
    """Exception raised when a resource conflict occurs."""

class InvalidRequestError(ResourceOperationError):
    """Exception raised when a request is invalid."""
```

### Usage

#### Basic Router Creation

```python
def get_resource_manager(user: User = Depends(UserManager.auth)):
    """Get an initialized ResourceManager instance."""
    return ResourceManager(requester_id=user.id)

# Create the router using AbstractEPRouter
resource_router = AbstractEPRouter(
    prefix="/v1/resource",
    tags=["Resource Management"],
    manager_factory=get_resource_manager,
    network_model_cls=ResourceNetworkModel,
    resource_name="resource",
)
```

#### Nested Resources

```python
# Create nested router for child resources
child_router = resource_router.create_nested_router(
    parent_prefix="/v1/resource",
    parent_param_name="resource_id",
    child_resource_name="child",
    manager_property="children",
    child_network_model_cls=ChildNetworkModel,
    tags=["Child Management"],
)
```

#### Mirror Routers

```python
# Create a standalone mirror of a nested router
mirror_router = child_router.create_mirror_router(
    new_prefix="/v1/child"
)
```

#### Router Trees

```python
routers = create_router_tree(
    base_prefix="/v1/project",
    resource_name="project",
    tags=["Project Management"],
    manager_factory=get_project_manager,
    network_model_cls=ProjectNetworkModel,
    nested_resources=[
        {
            "name": "conversation",
            "network_model_cls": ConversationNetworkModel,
            "create_mirror": True,
        }
    ],
)
```

#### Custom Routes

```python
resource_router.with_custom_route(
    method="post",
    path="/{id}/activate",
    endpoint=activate_resource,
    summary="Activate a resource",
    description="Activates a resource and performs related operations",
    response_model=ActivationResponse,
)
```

### Generated Endpoints

For a resource named `resource`, the AbstractEPRouter creates these endpoints:

| Method | Endpoint                          | Description                                |
| ------ | --------------------------------- | ------------------------------------------ |
| POST   | `/v1/resource`                    | Create a new resource                      |
| GET    | `/v1/resource/{id}`               | Get a specific resource by ID              |
| GET    | `/v1/resource`                    | List resources with optional filtering     |
| PUT    | `/v1/resource/{id}`               | Update a specific resource                 |
| DELETE | `/v1/resource/{id}`               | Delete a specific resource                 |
| POST   | `/v1/resource/search`             | Search for resources with complex criteria |
| PUT    | `/v1/resource`                    | Batch update multiple resources            |
| DELETE | `/v1/resource?target_ids=id1,id2` | Batch delete multiple resources            |

### Implementation Details

#### Network Model Structure

The AbstractEPRouter expects a network model class with these components:

```python
class ResourceNetworkModel:
    class POST(BaseModel):
        resource: ResourceCreateModel
    
    class PUT(BaseModel):
        resource: ResourceUpdateModel
    
    class SEARCH(BaseModel):
        resource: ResourceSearchModel
    
    class ResponseSingle(BaseModel):
        resource: ResourceResponseModel
    
    class ResponsePlural(BaseModel):
        resources: List[ResourceResponseModel]
```

#### Manager Interface

The manager factory should return an object that implements:

```python
class ResourceManager:
    def create(self, **kwargs): ...
    def get(self, id, **kwargs): ...
    def list(self, **kwargs): ...
    def search(self, **kwargs): ...
    def update(self, id, **kwargs): ...
    def delete(self, id): ...
    def batch_update(self, items): ...
    def batch_delete(self, ids): ...
```

## AbstractEPTest

The `AbstractEPTest` provides a standardized way to test endpoints created with AbstractEPRouter.

### Core Functionality

The AbstractEPTest:

1. Tests all standard CRUD operations
2. Tests batch operations
3. Tests error cases (not found, validation errors, etc.)
4. Tests authentication and authorization
5. Tests nested resources
6. Tests GraphQL integration

### Key Components

#### AbstractEPTest Class

```python
class AbstractEndpointTest(AbstractTest):
    """Base class for testing REST API endpoints with support for dependent entities.

    This abstract class provides a comprehensive set of tests for REST API endpoints
    following the patterns described in EP.schema.md and EP.patterns.md.
    """
```

#### ParentEntity Model

```python
class ParentEntity(BaseModel):
    """Model for parent entity configuration"""
    name: str
    key: str
    nullable: bool = False
    system: bool = False
    path_level: Optional[int] = None  # 1 for first level nesting, 2 for second level
```

### Usage

To create tests for a specific resource:

```python
class TestProjectEndpoint(AbstractEndpointTest):
    base_endpoint = "/v1/project"
    entity_name = "project"
    required_fields = ["name", "description"]
    string_field_to_update = "name"
    
    # If the resource has parent entities
    parent_entities = [
        ParentEntity(name="team", key="team_id", nullable=False)
    ]
    
    # If this is a system entity (requires API keys)
    system_entity = True
    
    # Search configuration
    supports_search = True
    searchable_fields = ["name", "status", "type"]
    search_example_value = "Test Project"
```

### Tests Provided

The AbstractEPTest provides these tests automatically:

1. **Basic CRUD Operations**
   - test_POST_201: Create a resource
   - test_GET_200_id: Get a resource by ID
   - test_GET_200_list: List resources
   - test_PUT_200: Update a resource
   - test_DELETE_204: Delete a resource

2. **Batch Operations**
   - test_POST_201_batch: Create multiple resources
   - test_PUT_200_batch: Update multiple resources
   - test_DELETE_204_batch: Delete multiple resources

3. **Error Cases**
   - test_GET_404_nonexistent: Get nonexistent resource
   - test_PUT_404_nonexistent: Update nonexistent resource
   - test_DELETE_404_nonexistent: Delete nonexistent resource
   - test_POST_422_batch: Test validation errors in batch creation

4. **Authentication & Authorization**
   - test_POST_401: Create without authentication
   - test_GET_401: Get without authentication
   - test_PUT_401: Update without authentication
   - test_DELETE_401: Delete without authentication
   - test_POST_403_system: Create system entity without API key
   - test_DELETE_403_system: Delete system entity without API key

5. **Parent Entity Tests**
   - test_POST_404_nonexistent_parent: Create with nonexistent parent
   - test_GET_404_nonexistent_parent: Get with nonexistent parent
   - test_POST_201_null_parents: Create with nullable parent set to null

6. **Team-Based Tests**
   - test_GET_200_list_via_parent_team: List resources via parent team
   - test_GET_404_list_no_parent_team: List resources with nonexistent parent team
   - test_GET_200_id_via_parent_team: Get resource via parent team
   - test_GET_404_id_no_parent_team: Get resource with nonexistent parent team

7. **Advanced Features**
   - test_GET_200_pagination: Test pagination
   - test_GET_200_fields: Test field selection
   - test_GET_200_includes: Test relationship includes
   - test_POST_403_role_too_low: Test role-based access control

8. **GraphQL Tests**
   - test_GQL_query_single: Test GraphQL query for single resource
   - test_GQL_query_list: Test GraphQL query for resource list
   - test_GQL_query_fields: Test GraphQL field selection
   - test_GQL_query_pagination: Test GraphQL pagination
   - test_GQL_mutation_validation: Test GraphQL validation
   - test_GQL_subscription: Test GraphQL subscriptions

### Implementation Details

#### Test Configuration

The AbstractEPTest uses these configuration properties:

```python
# Core configuration
base_endpoint: str = None  # Base URL for the resource (e.g., "/v1/project")
entity_name: str = None  # Name of the entity (e.g., "project")
required_fields: List[str] = None  # Required fields for creation
string_field_to_update: str = "name"  # Field to update in tests

# Entity relationships
parent_entities: List[ParentEntity] = []  # Parent entity configuration
system_entity: bool = False  # Whether this is a system entity

# Search configuration
supports_search: bool = True
searchable_fields: List[str] = ["name"]
search_example_value: str = None
```

#### Endpoint Templates

The AbstractEPTest uses template properties to determine endpoint paths:

```python
@property
def list_endpoint_template(self) -> str: ...

@property
def create_endpoint_template(self) -> str: ...

@property
def get_endpoint_template(self) -> str: ...

@property
def update_endpoint_template(self) -> str: ...

@property
def delete_endpoint_template(self) -> str: ...

@property
def search_endpoint_template(self) -> str: ...
```

## Best Practices

### For AbstractEndpointRouter

1. **Consistent Naming**: Use consistent resource names across your application
2. **Manager Logic**: Keep business logic in manager classes, not in route handlers
3. **Custom Routes**: Use with_custom_route for non-standard operations
4. **Error Handling**: Use the provided exception classes for consistent error responses
5. **Testing**: Test all endpoints with AbstractEPTest

### For AbstractEPTest

1. **Required Fields**: Specify all required fields to ensure valid test data
2. **Parent Entities**: Configure parent entities correctly for nested resources
3. **Custom Assertions**: Add custom assertions for resource-specific validations
4. **System Entities**: Set system_entity=True for resources requiring API keys
5. **Search Testing**: Configure searchable_fields and search_example_value for search tests 