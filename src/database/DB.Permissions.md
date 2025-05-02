# Permission System Documentation

This document details the permission system architecture, design principles, and implementation. The permission system handles authorization across the application with sophisticated access control rules.

## Architecture Overview

The permission system is split into two main components:

1. **`StaticPermissions.py`**: Contains core permission logic and utility functions for checking access rights
2. **`AbstractDatabaseEntity.py`**: Provides database model mixins that integrate with the permission system

This separation was chosen to:
- Avoid circular dependencies between models
- Separate core permission logic from ORM integration
- Allow permission checks at both application and database levels

## Design Principles

The permission system follows these core principles:

1. **Default Deny**: Access is denied unless explicitly granted
2. **Principle of Least Privilege**: Users get minimal access needed for their tasks
3. **Defense in Depth**: Multiple verification layers before access is granted
4. **Performance Optimization**: SQL-level filtering to prevent unauthorized data retrieval
5. **Explicit Permission Inheritance**: Clear paths for how permissions propagate

## System IDs

Three special system IDs are defined with distinct access levels:

| System ID   | Purpose            | Access Level                                                         |
| ----------- | ------------------ | -------------------------------------------------------------------- |
| ROOT_ID     | Highest authority  | Can access everything, including deleted records and system tables   |
| SYSTEM_ID   | System operations  | Users can view but not modify; only ROOT_ID and SYSTEM_ID can modify |
| TEMPLATE_ID | Templates/examples | Users can view, copy, execute, share but not modify                  |

System IDs are retrieved from environment variables:

```python
ROOT_ID = env("ROOT_ID")
SYSTEM_ID = env("SYSTEM_ID") 
TEMPLATE_ID = env("TEMPLATE_ID")
```

The tiered approach provides clear security boundaries and enables template resources that users can use but not modify.

## Permission Types

Permission types are defined as an enum with increasing levels of access:

```python
class PermissionType(PyEnum):
    VIEW = "can_view"
    EXECUTE = "can_execute"
    COPY = "can_copy"
    EDIT = "can_edit"
    DELETE = "can_delete"
    SHARE = "can_share"
```

These map to fields in the Permission table. Role levels map to permission types:

| Minimum Role | Required Permission Type |
| ------------ | ------------------------ |
| "user"       | VIEW                     |
| "admin"      | EDIT                     |
| "superadmin" | SHARE                    |

## Access Control Mechanisms

The system implements multiple access control mechanisms:

### Direct Ownership
Records with `user_id` matching the requesting user ID are accessible.

### Creator Permissions
Records with `created_by_user_id` field follow special rules:
- ROOT_ID created records: only ROOT_ID can access
- SYSTEM_ID created records: all users can view, only ROOT_ID and SYSTEM_ID can modify
- TEMPLATE_ID created records: all users can view/copy/execute/share, only ROOT_ID and SYSTEM_ID can modify

### Team Membership
Users can access records owned by teams they belong to, with access determined by their role within the team. Team hierarchies (up to 5 levels deep) are supported using recursive Common Table Expressions for performance:

```python
def _get_admin_accessible_team_ids_cte(user_id, db, max_depth=5):
    # Optimized SQL query with recursion limit
```

### Deleted Records Protection
Only ROOT_ID can view records with `deleted_at` set.

### System-Flagged Tables
Tables with `system = True` can only be modified by ROOT_ID and SYSTEM_ID.

### Explicit Permissions
The Permission table grants specific permissions to users, teams, or roles:
- User-specific: granted to a specific user
- Team-scoped: granted to all members of a team
- Role-based: granted to all users with a specific role

Permission records specify allowed operations and may have an expiration date.

### Permission References
Entities can inherit permissions from other entities through references:

```python
# User must have access to BOTH provider_instance AND extension
permission_references = ["provider_instance", "extension"]
```

Permission references allow checks during creation (`check_access_to_all_referenced_entities`) to ensure the user has access to all related entities. While the concept allows for permission inheritance, the current SQL-level filtering (`generate_permission_filter`) primarily focuses on direct ownership, team membership, and explicit permissions rather than recursively filtering based on arbitrary `permission_references` chains.

### Create Permission Reference
The `create_permission_reference` attribute specifies which referenced entity determines create permissions:

```python
# Permission to create is determined by extension permissions
create_permission_reference = "extension"
```

Auto-detection rules:
1. Single reference: Automatically used as create reference if none is defined
2. Multiple references: Must explicitly define a create reference
3. No references: Standard permission checks apply

## Permission Check Flow

The central permission check function returns a `PermissionResult` enum:

```python
def check_permission(user_id, record_cls, record_id, db, required_level=None, minimum_role=None):
    # Returns (PermissionResult, error_message)
```

For SQL filtering, the system uses:

```python
def generate_permission_filter(user_id, resource_cls, db, required_permission_level=None):
    # Returns SQLAlchemy filter expression
```

The permission check flow:
1. Check if user is ROOT_ID (always has access)
2. Check if record exists and isn't deleted
3. Check system flags
4. Check direct ownership and creator permissions
5. Check team membership with appropriate role
6. Check explicit permissions
7. Check permissions through references
8. Deny access if no condition grants it

This multilayered approach ensures proper authorization at all levels.

## Using Permission Checks

### Default Methods

Standard permission checking methods are provided in BaseMixin:

```python
user_has_read_access()
user_has_admin_access()
user_has_all_access()
user_can_create()
```

These should rarely be overridden except for special cases like the `User` model.

### Permission Filter Usage

For list operations, use the permission filter. It primarily checks direct ownership, team membership, and explicit permissions.

```python
perm_filter = generate_permission_filter(user_id, cls, db, PermissionType.VIEW)
query = query.filter(perm_filter)
```

### Permission Validation

For CRUD operations, use explicit permission validation:

```python
result, _ = check_permission(user_id, cls, id, db, PermissionType.EDIT)
if result != PermissionResult.GRANTED:
    raise HTTPException(status_code=403, detail="Permission denied")
```

## Security Considerations

1. Permission system bypasses should be extremely rare
2. Never return `True` unconditionally from permission methods
3. Always validate input parameters to prevent injection
4. Don't expose system IDs to end users
5. Remember that deleted records are only visible to ROOT_ID
6. Always check permissions before returning sensitive data
7. Use transactions to prevent partial updates that could break permission integrity