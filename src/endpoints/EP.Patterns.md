# Endpoint Layer Patterns & Best Practices

## Core Structure

The Endpoint Layer in this application follows a standardized pattern to ensure consistency, maintainability, and efficiency across different resource types. This document outlines the general patterns and best practices for creating endpoint routers.

## Authentication Patterns

Endpoints use one of these authentication patterns:

- **JWT Authentication**: For protected resources requiring a valid token
- **API Key Authentication**: For protected resources using scoped access keys
- **Basic Authentication**: Using username/password credentials (only for authentication)
- **No Authentication**: For public endpoints like registration and health checks

## Using AbstractEPRouter

Most endpoints inherit from `AbstractEPRouter` which provides a standardized implementation of CRUD operations according to the patterns in EP.schema.md.

> **Note**: For detailed documentation on AbstractEPRouter, AbstractEPTest, and related components, please refer to [EP.Abstraction.md](EP.Abstraction.md).

### Router Creation Pattern

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

### Customizing Examples

Examples are automatically generated using the `ExampleGenerator` class. You can customize these examples:

> **Note**: For detailed documentation on the Example Factory and example generation, please refer to [EP.ExampleFactory.md](EP.ExampleFactory.md).

```python
# Create custom examples
resource_examples = {
    "get": {
        "resource": {
            "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "name": "Production API Resource",
            "description": "This is a customized example for documentation"
        }
    }
}

# Create the router with customized examples
resource_router = AbstractEPRouter(
    prefix="/v1/resource",
    tags=["Resource Management"],
    manager_factory=get_resource_manager,
    network_model_cls=ResourceNetworkModel,
    resource_name="resource",
    example_overrides=resource_examples,
)
```

### Manager Factory Pattern

Manager factory functions provide dependency injection for resource managers:

```python
def get_resource_manager(
    user: User = Depends(UserManager.auth),
    target_user_id: Optional[str] = Query(
        None, description="Target user ID for admin operations"
    ),
    target_team_id: Optional[str] = Query(
        None, description="Target team ID for admin operations"
    ),
):
    """Get an initialized ResourceManager instance."""
    return ResourceManager(
        requester_id=user.id,
        target_user_id=target_user_id or user.id,
        target_team_id=target_team_id,
    )
```

## Standard Auto-Generated CRUD Operations

AbstractEPRouter automatically generates these endpoints:

- `POST /v1/resource`: Create new resource(s)
- `GET /v1/resource/{id}`: Retrieve resource by ID
- `GET /v1/resource`: List resources with optional filters
- `POST /v1/resource/search`: Complex search with filters
- `PUT /v1/resource/{id}`: Update resource by ID
- `PUT /v1/resource`: Batch update resources
- `DELETE /v1/resource/{id}`: Delete resource by ID
- `DELETE /v1/resource`: Batch delete resources

## Working with Nested Resources

Nested resources represent parent-child relationships and are created with:

```python
# Create base router
project_router = AbstractEPRouter(
    prefix="/v1/project",
    tags=["Project Management"],
    manager_factory=get_project_manager,
    network_model_cls=ProjectNetworkModel,
    resource_name="project",
)

# Create nested router for conversations
conversation_router = project_router.create_nested_router(
    parent_prefix="/v1/project",
    parent_param_name="project_id",
    child_resource_name="conversation",
    manager_property="conversations",
    tags=["Conversation Management"],
)

# Create a standalone mirror router
mirror_router = conversation_router.create_mirror_router(
    new_prefix="/v1/conversation"
)
```

This generates standard nested routes:
- `POST /v1/project/{project_id}/conversation`: Create conversation under project
- `GET /v1/project/{project_id}/conversation`: List conversations under project
- `GET /v1/project/{project_id}/conversation/{id}`: Get specific conversation
- ...and so on

## Creating Router Trees

For more complex resource hierarchies, use the `create_router_tree` helper:

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
            "manager_property": "conversations",
            "tags": ["Conversation Management"],
            "create_mirror": True  # Creates standalone /v1/conversation routes
        },
        {
            "name": "artifact",
            "manager_property": "artifacts",
            "create_mirror": False
        }
    ],
    auth_type=AuthType.JWT,
)

# Access individual routers
project_router = routers["project"]
conversation_router = routers["project_conversation"]
mirror_conversation_router = routers["conversation"]
```

## Request Body Formats

Endpoints support these request body formats:

### Single Resource Create/Update

```json
{
    "resource_name": {
        "field1": "value1",
        "field2": "value2"
    }
}
```

Where `resource_name` is the singular name of your resource (e.g., "project", "conversation", "message").

### Batch Create

```json
{
    "resource_name_plural": [
        { "field1": "value1", "field2": "value2" },
        { "field1": "value3", "field2": "value4" }
    ]
}
```

Where `resource_name_plural` is the plural name of your resource (e.g., "projects", "conversations", "messages").

### Batch Update

```json
{
    "resource_name": { 
        "field1": "new_value" 
    },
    "target_ids": ["id1", "id2", "id3"]
}
```

Where `resource_name` is the singular name of your resource.

### Batch Delete

`?target_ids=id1,id2,id3`


### Search Criteria

```json
{
    "resource_name": {
        "name": "search_term",
        "created_after": "2023-01-01",
        "status": ["active", "pending"]
    }
}
```

Where `resource_name` is the singular name of your resource.

## Adding Custom Routes

For operations that don't fit the standard CRUD pattern, use the `with_custom_route` helper method:

```python
# Define a custom endpoint function
async def activate_resource(
    id: str = Path(..., description="Resource ID"),
    activation_data: ActivationRequest = Body(...),
    manager = Depends(get_resource_manager),
):
    """Activate a resource with the provided data."""
    return await manager.activate(id, activation_data)

# Add the custom route to the router
resource_router.with_custom_route(
    method="post",
    path="/{id}/activate",
    endpoint=activate_resource,
    summary="Activate a resource",
    description="Activates a resource and performs related operations",
    response_model=ActivationResponse,
    status_code=status.HTTP_200_OK,
)
```

## Error Handling

The `AbstractEPRouter` provides consistent error handling through custom exception classes:

```python
# In your manager class
def update_resource(self, resource_id: str, **data):
    """Update a resource."""
    resource = self.get_resource(resource_id)
    
    if not resource:
        raise ResourceNotFoundError(
            resource_name="resource", 
            resource_id=resource_id
        )
    
    if "name" in data and self.name_exists(data["name"], exclude_id=resource_id):
        raise ResourceConflictError(
            resource_name="resource",
            conflict_type="name already exists"
        )
    
    if not self.validate_data(data):
        raise InvalidRequestError(
            message="Invalid resource data",
            details={"errors": self.validation_errors}
        )
        
    # Proceed with update
    return self.perform_update(resource, data)
```

The router automatically converts these exceptions to appropriate HTTP responses with detailed information.

## Logging

For effective debugging, the router includes comprehensive logging:

```python
# Log is automatically included
logger = logging.getLogger(__name__)

def get_resource_manager(user: User = Depends(UserManager.auth)):
    """Get an initialized ResourceManager instance."""
    logger.debug(f"Creating ResourceManager for user {user.id}")
    return ResourceManager(requester_id=user.id)
```

## Router Organization

Organize your routers by domain and function:

```python
# Main application router
app_router = APIRouter()

# User and authentication domain
app_router.include_router(user_router)
app_router.include_router(team_router)
app_router.include_router(auth_router)

# Projects domain
app_router.include_router(project_router)
app_router.include_router(artifact_router)

# Conversations domain
app_router.include_router(conversation_router)
app_router.include_router(message_router)

# Agents domain
app_router.include_router(agent_router)
app_router.include_router(provider_router)

# Finally, include in FastAPI app
app.include_router(app_router)
```

## Network Models Pattern

Create a dedicated `NetworkModel` class for each resource:

```python
class ResourceNetworkModel:
    """Network models for Resource API."""
    
    class ResourceBase(BaseModel):
        """Base model with common fields."""
        name: str
        description: Optional[str] = None
    
    class ResourceCreate(ResourceBase):
        """Fields for creating a resource."""
        # Add creation-specific fields
        type: str
    
    class ResourceUpdate(BaseModel):
        """Fields for updating a resource."""
        name: Optional[str] = None
        description: Optional[str] = None
        # Add update-specific fields
    
    class ResourceSearch(BaseModel):
        """Fields for searching resources."""
        name: Optional[str] = None
        type: Optional[str] = None
        created_after: Optional[datetime] = None
    
    class ResourceResponse(ResourceBase):
        """Response model with all fields."""
        id: str
        created_at: datetime
        updated_at: datetime
        # Add additional read-only fields
    
    # Router model definitions - these MUST be named exactly as below
    class POST(BaseModel):
        resource: ResourceCreate  # Field name must match resource_name
    
    class PUT(BaseModel):
        resource: ResourceUpdate  # Field name must match resource_name
    
    class SEARCH(BaseModel):
        resource: ResourceSearch  # Field name must match resource_name
    
    class ResponseSingle(BaseModel):
        resource: ResourceResponse  # Field name must match resource_name
    
    class ResponsePlural(BaseModel):
        resources: List[ResourceResponse]  # Field name must match resource_name_plural
```

## Best Practices

1. **Dynamic Resource Naming**: Always use the `resource_name` parameter when creating routers to ensure consistent naming throughout endpoints and documentation
   
2. **Resource-Specific Classes**: Ensure your network models use the correct resource name as field names

3. **Consistent Error Handling**: Use the provided exception classes (`ResourceNotFoundError`, `ResourceConflictError`, etc.) for clean error handling

4. **Comprehensive Documentation**: Include detailed descriptions and examples for each endpoint

5. **Manager Independence**: Keep router code separate from business logic by delegating to manager classes

6. **Testing Strategy**:
   - Test each endpoint with valid inputs
   - Test error handling with invalid inputs
   - Test batch operations with various payload sizes
   - Test response format compliance

7. **Security Considerations**:
   - Apply proper authentication using the `auth_type` parameter
   - Implement authorization checks in manager classes
   - Validate input data thoroughly
   - Use HTTPS for all production endpoints

8. **Performance Awareness**:
   - Implement pagination for list operations
   - Use appropriate caching strategies
   - Optimize database queries in manager classes

9. **Extensibility**:
   - Use the `with_custom_route` method for special cases
   - Create custom response models for complex operations
   - Extend base router classes for specialized behavior

10. **Maintenance and Monitoring**:
    - Use the built-in logging for traceability
    - Monitor endpoint performance
    - Document any deviations from standard patterns