# GraphQL Integration Pattern

## Overview

The GraphQL integration in this application provides an automatic mapping between Pydantic models and GraphQL types, enabling a fully dynamic GraphQL API without manually defining schemas. This document explains how the system works, best practices, and customization options.

## Key Components

The GraphQL system automatically:

1. Discovers Pydantic models from BLL (Business Logic Layer) modules
2. Maps relationships between models using intelligent inference
3. Generates GraphQL types for models with proper field types
4. Creates resolvers for queries, mutations, and subscriptions
5. Handles authentication and context management
6. Sets up real-time subscriptions via broadcasting

## Core Architecture

### Model Discovery

The system discovers models from BLL modules by:

```python
# Import all BLL modules from logic directory and extensions
bll_modules = import_all_bll_modules()

# Discover model relationships
model_relationships = pydantic_util.discover_model_relationships(bll_modules)

# Get model fields
model_fields_mapping = pydantic_util.collect_model_fields(model_relationships)
```

For each BLL module, the system finds:
- Main model (e.g., `ProjectModel`)
- Reference model (e.g., `ProjectReferenceModel`)
- Network model (e.g., `ProjectNetworkModel`)
- Manager class (e.g., `ProjectManager`)

### Type Generation

GraphQL types are generated dynamically from Pydantic models:

```python
# Create a GraphQL type from a Pydantic model
gql_type = create_strawberry_type(model_class, model_to_type)

# Create an input type for mutations
input_type = create_input_type(model_class.Create, "Input")
```

The system handles:
- Basic scalar fields (strings, numbers, booleans)
- Date/time fields with proper serialization
- Nested objects with proper references
- List fields with proper typing
- Optional fields
- Recursive relationships with depth limiting

### Resolver Generation

Resolvers are created dynamically for:

1. **Queries**:
   - Get by ID: `get_<resource>` (e.g., `get_project`)
   - List all: `<resources>` (e.g., `projects`)

2. **Mutations**:
   - Create: `create_<resource>` (e.g., `create_project`)
   - Update: `update_<resource>` (e.g., `update_project`)
   - Delete: `delete_<resource>` (e.g., `delete_project`)

3. **Subscriptions**:
   - Created: `<resource>_created` (e.g., `project_created`)
   - Updated: `<resource>_updated` (e.g., `project_updated`)
   - Deleted: `<resource>_deleted` (e.g., `project_deleted`)

### Authentication and Context

Authentication is handled through the context:

```python
async def get_context_from_info(info: Info):
    # Extract request from context
    request = info.context["request"]
    auth_header = request.headers.get("Authorization", "")
    session = get_session()
    
    # Verify token and get user
    user = UserManager.auth(auth_header)
    requester_id = user.id
    
    return {
        "requester_id": requester_id,
        "session": session,
        "auth_header": auth_header,
    }
```

This context is passed to all resolvers, providing a consistent authentication mechanism.

## Special Type Handling

### Scalar Types

Custom scalar types are defined for special data:

```python
@strawberry.scalar(
    description="DateTime scalar",
    serialize=lambda v: v.isoformat() if v else None,
    parse_value=lambda v: datetime.fromisoformat(v) if v else None,
)
class DateTimeScalar:
    pass
```

### User Types

User types have special handling:

```python
@strawberry.type
class UserType:
    id: str
    email: str
    display_name: Optional[str] = None
    # ... other fields
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserType":
        # Safe conversion from dict to UserType
        field_annotations = cls.__annotations__
        filtered_data = {
            k: v for k, v in data.items() 
            if k in field_annotations and not k.startswith("_")
        }
        return cls(**filtered_data)
```

## Subscriptions

Real-time subscriptions use the `broadcaster` library:

```python
@strawberry.subscription
async def subscription_method(self, info: Info) -> AsyncGenerator[gql_tp, None]:
    """Subscribe to model events"""
    channel = f"{name}_{event_type}"
    async with broadcast.subscribe(channel=channel) as subscriber:
        async for message in subscriber:
            yield message
```

Events are published from mutation resolvers:

```python
# Publish event when a resource is created/updated/deleted
event_name = f"{name}_created"  # or _updated or _deleted
await broadcast.publish(channel=event_name, message=result)
```

## Customization Options

### Recursion Depth Control

Control how deep the system traverses nested relationships:

```python
# Default is 3, increase for more complex nested structures
Query, Mutation, Subscription = build_dynamic_strawberry_types(max_recursion_depth=4)
```

### Schema Configuration

Configure the Strawberry schema:

```python
from strawberry.schema.config import StrawberryConfig

config = StrawberryConfig(auto_camel_case=True)
Query, Mutation, Subscription = build_dynamic_strawberry_types(strawberry_config=config)
```

## Best Practices

1. **Model Structure**:
   - Use consistent naming for models (`ModelName`, `ModelNameReferenceModel`)
   - Include `Create` and `Update` inner classes in models
   - Define field types explicitly with proper type annotations

2. **Manager Implementation**:
   - Ensure managers implement `get()`, `list()`, `create()`, `update()`, and `delete()`
   - Use proper context with `requester_id` and database session
   - Return complete model instances from operations

3. **Performance Considerations**:
   - Control recursion depth for complex relationships
   - Limit result sets for list operations
   - Be aware of N+1 query problems

4. **Security**:
   - Do not expose sensitive fields in GraphQL types
   - Enforce proper authorization in manager methods
   - Validate input data thoroughly

## Integration with FastAPI

Integrate the GraphQL schema with FastAPI:

```python
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

# Build the dynamic types
Query, Mutation, Subscription = build_dynamic_strawberry_types()

# Create schema
schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)

# Create FastAPI app with GraphQL router
app = FastAPI()
graphql_app = GraphQLRouter(
    schema=schema,
    graphiql=True  # Enable GraphiQL interface for development
)
app.include_router(graphql_app, prefix="/graphql")

# Register lifecycle events
@app.on_event("startup")
async def on_startup():
    await startup()

@app.on_event("shutdown")
async def on_shutdown():
    await shutdown()
```

## Example Queries

### Query Example

```graphql
query GetProject {
  project(id: "project-id") {
    id
    name
    description
    created_at
    updated_at
    tasks {
      id
      name
      status
    }
  }
}
```

### Mutation Example

```graphql
mutation CreateProject($input: ProjectCreateInput!) {
  create_project(input: $input) {
    id
    name
    description
  }
}

# Variables:
{
  "input": {
    "name": "New Project",
    "description": "Project description"
  }
}
```

### Subscription Example

```graphql
subscription ProjectCreated {
  project_created {
    id
    name
    description
  }
}
```

## Debugging Tips

1. **Type Generation Issues**:
   - Check that models have proper type annotations
   - Verify that relationships between models are correctly defined
   - Look for circular references that exceed max recursion depth

2. **Resolver Errors**:
   - Ensure manager methods handle the operations correctly
   - Verify proper context is available in resolvers
   - Check authentication and permission handling

3. **Subscription Problems**:
   - Ensure broadcast channels are correctly named
   - Verify broadcaster connection is properly initialized
   - Check for event publishing in mutation resolvers 