# Business Logic Layer

## Core Structure

> **Note:** For comprehensive documentation on the core abstractions used in the Business Logic Layer, including AbstractBLLManager, please refer to [BLL.Abstraction.md](BLL.Abstraction.md#business-logic-layer-manager-abstractbllmanager).

The Business Logic Layer in this application follows a standardized pattern to ensure consistency across different domain entities. Comments should not be present unless required for some in a senior engineer position to understand what's happening. There should never be direct database connection queries in the BLL files, all queries must do through the abstract functions in AbstractDatabaseEntity.py. 

## AbstractBLLManager-based Managers

All BLL manager classes inherit from `AbstractBLLManager` and follow these conventions:

### Manager Class Pattern

Each file should be 1:1 with the related "DB_" file of the same name. For example, every entity in DB_Auth_Core should have a related Manager and models in BLL_Auth. Managers should have their relevant models defined immediately above them:

```python
# Previous manager (if there is one) would go here.

# EntityModel definition would go here.
# EntityReferenceModel definition would go here.
# EntityNetworkModel definition would go here.
class EntityManager(AbstractBLLManager):
    Model = EntityModel
    ReferenceModel = EntityReferenceModel
    NetworkModel = EntityNetworkModel
    DBClass = Entity

    def __init__(
        self,
        requester_id: str,
        target_user_id: Optional[str] = None,
        target_team_id: Optional[str] = None,
        db: Optional[Session] = None,
    ):
        super().__init__(
            requester_id=requester_id,
            target_user_id=target_user_id,
            target_team_id=target_team_id,
            db=db,
        )
        self._related_manager = None
```

### Related Manager Access Pattern

Related managers are lazy-loaded through properties to avoid circular imports, they should be named as the plural entity name:

```python
# Example using providers - can use any manager / entity.
    def __init__(
        self,
        requester_id: str,
        target_user_id: Optional[str] = None,
        target_team_id: Optional[str] = None,
        db: Optional[Session] = None,
    ):
        super().__init__(
            requester_id=requester_id,
            target_user_id=target_user_id,
            target_team_id=target_team_id,
            db=db,
        )
        self._providers = None

    @property
    def providers(self):
        if self._providers is None:
            from logic.BLL_Providers import ProviderManager

            self._providers = ProviderManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                target_team_id=self.target_team_id,
                db=self.db,
            )
        return self._providers
```

### Model Definitions

Each manager defines three model types and its database class:

1. **Entity Model**: Inherits from `BaseMixinModel` and defines entity attributes, model validators can also be used in the sub-models. Where possible, the functionality should be encapsulated above for reuse in the Update model. Use Fields where possible. The GQL schema is dynamically generated from these models so consistency is important.
2. **Reference Model**: Used for relationships between entities
3. **Network Model**: Defines request/response schemas for API endpoints

Validators can optionally be used to enforce check-constraint-like behaviour in the business logic layer.

Example structure:

```python
def validate_x(id, fk_1):
    pass # Perform validation. 

class ProviderModel(
    BaseMixinModel,
    NameMixinModel,
    UserReferenceModel,
):
    favourite: bool = Field(
        False, description="Whether this provider is marked as a favorite"
    )

    class ReferenceID:
        provider_id: str = Field(..., description="The ID of the related provider")

        class Optional:
            provider_id: Optional[str] = None

        class Search:
            provider_id: Optional[StringSearchModel] = None

    class Create(
        BaseModel,
        NameMixinModel,
        UserModel.ReferenceID.Optional,
    ):
        favourite: Optional[bool] = Field(
            False, description="Whether this provider is marked as a favorite"
        )
        # Optional validator, if validation logic is required.
        @model_validator(mode="after")
        def validate_entity_create(self):
            return validate_x(
                self.entity_id, self.user_id
            )
    class Update(
        BaseModel,
        NameMixinModel.Optional,
        UserModel.ReferenceID.Optional,
    ):
        favourite: Optional[bool] = Field(
            None, description="Whether this provider is marked as a favorite"
        )
        # Optional validator, if validation logic is required.
        @model_validator(mode="after")
        def validate_entity_update(self):
            return validate_x(
                self.entity_id, self.user_id
            )
    class Search(
        BaseMixinModel.Search,
        NameMixinModel.Search,
        UserModel.ReferenceID.Search,
    ):
        favourite: Optional[bool] = Field(None, description="Filter by favorite status")


class ProviderReferenceModel(ProviderModel.ReferenceID):
    provider: Optional[ProviderModel] = None

    class Optional(ProviderModel.ReferenceID.Optional):
        provider: Optional[ProviderModel] = None


class ProviderNetworkModel:
    class POST(BaseModel):
        provider: ProviderModel.Create

    class PUT(BaseModel):
        provider: ProviderModel.Update

    class SEARCH(BaseModel):
        provider: ProviderModel.Search

    class ResponseSingle(BaseModel):
        provider: ProviderModel

    class ResponsePlural(BaseModel):
        providers: List[ProviderModel]
```

These should be defined **IMMEDIATELY ABOVE THE RELEVANT MANAGER** (not all at the top of the file), and are then linked to the manager for reference by the abstract functions:

```python
Model = EntityModel
ReferenceModel = EntityReferenceModel
NetworkModel = EntityNetworkModel
DBClass = Entity
```
### Model Mixins

Use mixin classes from AbstractBLLManager for common properties:
- `BaseMixinModel`: Adds id, created_at, created_by_user_id and created_by_user reference fields
- `UpdateMixinModel`: Adds updated_at, updated_by_user_id and updated_by_user reference fields
- `NameMixinModel`: Adds name field
- `DescriptionMixinModel`: Adds description field
- `ParentMixinModel`: Adds parent_id field and parent reference field for hierarchical entities
- `ImageMixinModel`: Adds image_url field

Additionally, use `OtherEntityModel.ReferenceID`, `OtherEntityModel.ReferenceID.Optional` or `OtherEntityModel.ReferenceID.Search` as a mixin for a model to automatically add the foreign key fields. You can also use `OtherEntityReferenceModel` or `OtherEntityReferenceModel.Optional` to automatically add BOTH the foriegn key field and object reference field. Foreign key fields should all be populated this way and should not be declared manually. The specific `OtherEntityModel.ReferenceID` and `OtherEntityModel.ReferenceID.Optional` can be used for the `Create`, `Update`, etc models.

It's important to distinguish this from the `ReferenceID` class defined *within* the main entity model (e.g., `ProviderModel.ReferenceID`). The inner `ReferenceID` class defines how *other* models should reference *this* entity, while the mixins (`UserModel.ReferenceID`, `TeamModel.ReferenceID.Optional`, etc.) are used when *this* entity needs to hold a foreign key *to another* entity.

Optional variants are provided to be used for both updates (PUT supports partial entities), and nullable database fields in creates.

### CRUD Operations

Managers inherit standard CRUD operations from AbstractBLLManager:
- `create(**kwargs)`: Create entity with validation
- `get(**kwargs)`: Retrieve entity with optional includes
- `list(**kwargs)`: List entities with filters
- `search(**kwargs)`: Complex search with string/numeric filters
- `update(id, **kwargs)`: Update entity properties
- `delete(**kwargs)`: Delete entity
- `batch_update(items)`: Update multiple entities in a single transaction
- `batch_delete(ids)`: Delete multiple entities in a single transaction

These functions validate `kwargs` against the appropriate child of `EntityModel`, and then pass them into the database functions from `AbstractDatabaseEntity.py`.

Additional data from other tables should not be included automatically nor should methods referencing other tables be included - there is already join functionality in the AbstractBLLManager get/list functions. For example, PromptManager should not have functions working with PromptArguments.

Custom logic is often added by overriding these methods and calling super().

### Batch Processing

Batch operations work with multiple entities in a single request:

```python
# Batch update
def batch_update(self, items: List[Dict[str, Any]]) -> List[Any]:
    """
    Update multiple entities in a batch.
    
    Args:
        items: List of dictionaries containing 'id' and 'data' for each entity to update
    """
    results = []
    errors = []
    
    for item in items:
        try:
            entity_id = item.get('id')
            update_data = item.get('data', {})
            updated_entity = self.update(id=entity_id, **update_data)
            results.append(updated_entity)
        except Exception as e:
            errors.append({"id": item.get('id'), "error": str(e)})
    
    # Report errors when needed
    if errors:
        raise HTTPException(status_code=400, detail={
            "message": "One or more batch operations failed",
            "errors": errors
        })
            
    return results

# Batch delete
def batch_delete(self, ids: List[str]):
    """Delete multiple entities in a batch."""
    # Similar error collection pattern
```

### Validation (Optional)

Use `createValidation` hook to add custom validation before entity creation. It should **not** be used to repeat validation of NOT NULLs, etc that are already enforced by the database, nor validation that is performed by model validators. It should be used only for complex multi-entity logic:

```python
# Optional complex validator, if validation logic is required.
def createValidation(self, entity):
    pass
```

## Common Patterns Across All Files

### Imports and Organization

Standard import order:
1. Python standard libraries
2. Third-party libraries (pydantic, sqlalchemy, etc.)
3. Application-specific imports
4. Globals and utils

### Logging

Logging can be imported globally and should not be reconfigured in each file, it is configured at the app level.

### Error Handling

All exceptions should be HTTPExceptions with appropriate status codes for error handling:

```python
raise HTTPException(status_code=404, detail="Entity not found")
```


### Authentication and Security

- Auth managers handle tokens, passwords, and MFA
- Sensitive operations validate user permissions before execution
- Context is maintained through `requester_id`, `target_user_id` (`target_user`) and `target_team_id` (`target_team`).

## Specialized Manager Patterns

### Authentication Managers

Auth managers implement specialized methods for login, token verification, etc.:

```python
def login(self, login_data, ip_address, req_uri=None):
    # Authentication logic
    return {"token": "..."}
```

### Search and Filtering
The AbstractBLLManager provides a flexible search system with three extension methods:

#### 1. Search Transformers (Optional)
If additional transformers are required, register them:

```python
def _register_search_transformers(self):
    self.register_search_transformer('overdue', self._transform_overdue_search)
    
def _transform_overdue_search(self, value):
    if value:
        now = datetime.now()
        return [
            Task.scheduled == True,
            Task.completed == False,
            Task.due_date <= now,
        ]
    return []
```

#### 2. Post-Processing (Optional)
Override search for complex filters or result enrichment if required:

```python
def search(self, include=None, **search_params):
    label = search_params.pop('label', None)
    tasks = super().search(include=include, **search_params)
    
    # Apply post-filter for many-to-many relationship
    if label:
        tasks = self._filter_by_label(tasks, label)
        
    return tasks
```

#### 3. Standard Search Models
Built-in models for common field types:

- **StringSearchModel**: `inc`, `sw`, `ew`
- **NumericalSearchModel**: `eq`, `neq`, `lt`, `gt`, `lteq`, `gteq`
- **DateSearchModel**: `before`, `after`, `on` 
- **BooleanSearchModel**: `is_true`

Example:
```python
tasks = task_manager.search(
    name=StringSearchModel(inc="project"),
    due_date=DateSearchModel(before=datetime.now()),
    overdue=True  # Custom concept handled by transformer
)
```


### Transaction Handling
Transactions are handled by the passing of the db object. The db parameter to all constructors is optional. If it is not provided, it will spawn its own database connection and transactionalize its operation. If it is provided, it will commit at the end but will not close the transaction. 

Batch operations follow this pattern and collect errors while processing all items. This allows for partial success handling and detailed error reporting.

## Specific Domain Patterns

### OAuth Integration (BLL_Auth_OAuth)

- Provider-specific implementations with standardized interfaces
- Token management and refresh logic

### Conversation and Message Management (BLL_Conversations)

- Hierarchical structure (Project → Conversation → Message → Activity)
- Artifact handling for file and content management

### Task Management (BLL_Tasks)

- Scheduling and execution logic
- Integration with providers for task execution

### Memory Management (BLL_Memories)

- Vector embedding and similarity search
- Chunking strategies for large content

## Utility Functions
Some managers have static functions to get runtime functionality such as `list_runtime_extensions`, `list_runtime_providers`, the UserManager has functions such as `auth` and `verify_token` and the invitation manager has a function for `generate_invitation_link`. Using static functions such as these to extend functionality is encouraged. They CAN be asynchronous / async if required, such as `prompt` and `transcribe` on ProviderManager, because they involve querying other APIs.