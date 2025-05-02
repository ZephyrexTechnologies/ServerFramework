# Database Patterns Documentation

This document details the design patterns used throughout the database system that are not covered in the permission system or database management documentation.

## Composition through Mixins

Rather than relying on complex inheritance hierarchies, the system uses composition through mixins to share functionality between models.

### Why Mixins?

1. **Granular Feature Selection**: Models only include needed functionality
2. **Reduced Code Duplication**: Common behaviors defined once
3. **Easier Maintenance**: Changes to a feature affect only the relevant mixin
4. **Better Testability**: Mixins can be tested in isolation

Common mixins include:

```python
class BaseMixin:  # Core functionality all models need
class UpdateMixin:  # For models that can be updated/deleted
class ParentMixin:  # For hierarchical models
class ImageMixin:  # For models with image URLs
class UserRefMixin:  # For models linked to users
class TeamRefMixin:  # For models linked to teams
```

## Session Management with Decorators

The `with_session` decorator centralizes session management logic:

```python
def with_session(func):
    @functools.wraps(func)
    def wrapper(cls, requester_id: String, db: Optional[Session] = None, *args, **kwargs):
        session = db if db else get_session()
        try:
            result = func(cls, requester_id, session, *args, **kwargs)
            return result
        except Exception as e:
            session.rollback()
            raise e
        finally:
            if db is None:
                session.close()
    return wrapper
```

This pattern:
1. Creates a session if none is provided
2. Automatically handles transactions
3. Ensures proper cleanup with finally block
4. Allows session reuse across operations

## Dynamic Reference Mixins

The system uses a factory function to create reference mixins dynamically:

```python
def create_reference_mixin(target_entity, **kwargs):
    # Creates a mixin with foreign key and relationship to target_entity
```

Benefits of this approach:
1. **Consistent References**: All foreign keys follow the same pattern
2. **Optional Variants**: Each mixin includes `.Optional` variant for nullable references
3. **Constraint Naming**: Automatic constraint naming for better migrations
4. **Relationship Customization**: Backref names and other options can be customized

## Hooks Registry

A hooks registry pattern allows extending model behavior:

```python
# Global hooks registry to properly handle inheritance
_hooks_registry = {}
hook_types = ["create", "update", "delete", "get", "list"]

def get_hooks_for_class(cls):
    """Get or create hooks for a class"""
```

Models access hooks through a descriptor:

```python
class HooksDescriptor:
    def __get__(self, obj, objtype=None):
        if objtype is None:
            objtype = type(obj)
        return get_hooks_for_class(objtype)

# Usage in BaseMixin
hooks = HooksDescriptor()
```

Hook execution:

```python
# Before hooks
if "create" in hooks and "before" in hooks["create"]:
    before_hooks = hooks["create"]["before"]
    if before_hooks:
        hook_dict = HookDict(data)
        for hook in before_hooks:
            hook(hook_dict, db)
```

This approach:
1. **Separates Core Logic from Extensions**: Base code remains clean
2. **Preserves Inheritance**: Hooks follow class inheritance patterns
3. **Avoids Metaclass Complexity**: Uses simpler descriptors
4. **Thread-Safety**: Registry pattern is thread-safe

## DTO Conversion System

The system converts between database entities and DTOs with a flexible approach:

```python
def db_to_return_type(
    entity: Union[T, List[T]],
    return_type: Literal["db", "dict", "dto", "model"] = "dict",
    dto_type: Optional[Type[DtoT]] = None,
    fields: List[str] = [],
) -> Union[T, DtoT, ModelT, List[Union[T, DtoT, ModelT]]]:
```

Benefits:
1. **Return Type Flexibility**: Same code handles different return formats
2. **Field Selection**: Clients can request only needed fields
3. **Nested Object Handling**: Automatically processes nested relationships
4. **Batch Processing**: Works with both single entities and lists

## Validation Patterns

Field validation is centralized:

```python
# In StaticPermissions.py - used for general query validation
def validate_columns(cls, updated=None, **kwargs):
    """Validate that the provided column names exist in the model."""

# In AbstractDatabaseEntity.py - used for DTO conversion field validation
def validate_fields(cls, fields):
    """Validate that the fields exist on the model class."""
```

This ensures:
1. **Early Validation**: Invalid columns/fields are caught before database operations or DTO conversion
2. **Consistent Error Messages**: Standard format for validation errors
3. **Security**: Prevents potential issues via invalid column/field names

## System Initialization

The system uses a seeding pattern to initialize data:

```python
def seed():
    """Generic seeding function that populates the database based on seed_list attributes."""
```

Models declare seed data:
```python
class Role(Base, BaseMixin, UpdateMixin, TeamRefMixin.Optional, ParentMixin):
    seed_list = [
        {"name": "user", "friendly_name": "User", "parent_id": None},
        {"name": "admin", "friendly_name": "Admin", "parent_id": "user-id"},
        # ...
    ]
```

Or provide dynamic seed data:
```python
@classmethod
def get_seed_list(cls):
    """Dynamically get the seed list to avoid circular imports"""
```

Benefits:
1. **Declarative Initialization**: Models define their own seed data
2. **Dependency Ordering**: Automatically handles dependencies
3. **Environment Awareness**: Seeds can adapt to environment variables
4. **Idempotence**: Seed operations check for existing records

## Query Building Pattern

Query construction is standardized:

```python
def build_query(
    session, cls, joins=[], options=[], filters=[], order_by=None, limit=None, offset=None, **kwargs
):
```

This provides:
1. **Consistent Query Building**: All queries follow same pattern
2. **Composable Filters**: Multiple filters can be combined
3. **Pagination Support**: Built-in limit/offset handling
4. **Relationship Loading**: Supports eager loading through joins/options

## Soft Deletion

The system implements soft deletion:

```python
@declared_attr
def deleted_at(cls):
    return Column(DateTime, default=None)

@declared_attr
def deleted_by_user_id(cls):
    return Column(PK_TYPE, nullable=True)
```

Automatic filtering:
```python
if hasattr(cls, "deleted_at"):
    filters = filters + [cls.deleted_at == None]
```

Benefits:
1. **Data Preservation**: Historical data is maintained
2. **Audit Trail**: Records who deleted what and when
3. **Recoverability**: Deleted records can be restored
4. **Permission Control**: Only ROOT_ID can see deleted records

## Dynamic Extension Loading

Extensions are loaded dynamically:

```python
def get_extensions_from_env():
    """Get extensions from the APP_EXTENSIONS environment variable"""
```

This pattern:
1. **Configurable Functionality**: Features can be enabled/disabled without code changes
2. **Plugin Architecture**: Extensions follow consistent patterns
3. **Environment-Based Configuration**: Different environments can enable different features
4. **Runtime Discovery**: System adapts to available extensions

## Circular Dependency Management

The system handles circular dependencies with local imports:

```python
def _get_role_hierarchy_map(db: Session) -> dict:
    # Local import to break cycle
    from database.DB_Auth import Role
```

This approach:
1. **Prevents Import Cycles**: Models can reference each other
2. **Minimizes Import Time**: Only imports what's needed when needed
3. **Supports Cross-Module Functionality**: Core functions can work with multiple models
4. **Maintains Type Safety**: Type hints still work properly

## HookDict for Property Access

The system uses a special dictionary class for hook data:

```python
class HookDict(dict):
    """Dictionary subclass that allows attribute access to dictionary items"""
    def __getattr__(self, name):
        if name in self:
            value = self[name]
            if isinstance(value, dict):
                return HookDict(value)
            return value
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
```

This allows:
1. **Attribute-Style Access**: `hook_dict.name` instead of `hook_dict["name"]`
2. **Recursive Conversion**: Nested dictionaries are also converted
3. **Natural Programming Style**: More readable hook code
4. **Type Compatibility**: Functions similar to an object with attributes