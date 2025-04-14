# Permission System Documentation

This document explains the enhanced permission system used across the application. The permission system is designed to be flexible, secure, and maintainable, with support for role-based access control, team membership, ownership, and permission inheritance through entity references.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [System IDs](#system-ids)
3. [Access Control Mechanisms](#access-control-mechanisms)
   - [Direct Ownership](#direct-ownership)
   - [Team Membership](#team-membership)
   - [Permission References](#permission-references)
   - [Create Permission Reference](#create-permission-reference)
4. [Role Hierarchy](#role-hierarchy)
5. [Permission Check Flow](#permission-check-flow)
   - [Read Access](#read-access)
   - [Admin Access](#admin-access)
   - [Create Permission](#create-permission)
6. [Setting Up Permissions](#setting-up-permissions)
   - [Model Definition](#model-definition)
   - [Permission References](#setting-permission-references)
   - [Create Permission References](#setting-create-permission-references)
7. [Common Patterns](#common-patterns)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

## System Architecture

The permission system is split into two main components:

1. **`Permissions.py`**: Contains core permission logic and utility functions for checking access rights.
2. **`Mixins.py`**: Provides database model mixins that integrate with the permission system.

The system uses a combination of:
- **User ownership**: Entities can be owned by users (via `user_id` field)
- **Team membership**: Users can belong to teams with different roles
- **Reference-based permissions**: Permissions can be inherited through referenced entities
- **Role-based access control**: Different operations require different roles

## System IDs

Three special system IDs are defined with distinct access levels:

1. **`ROOT_ID`**: The highest authority system ID. Has access to everything, including other system entities. Used for core infrastructure elements, like the system email provider.

2. **`SYSTEM_ID`**: Used for system-wide entities that any user can access but not modify. For example, system providers that users can connect to but not edit directly.

3. **`TEMPLATE_ID`**: Used for template/example entities that users can copy and run but not modify. For example, template prompts and example chains.

System IDs are defined in `Permissions.py` and are retrieved from environment variables with fallback defaults.

```python
ROOT_ID = env("ROOT_ID", "00000000-0000-0000-0000-000000000000")
SYSTEM_ID = env("SYSTEM_ID", "00000000-0000-0000-0000-000000000001") 
TEMPLATE_ID = env("TEMPLATE_ID", "00000000-0000-0000-0000-000000000002")
```

## Access Control Mechanisms

### Direct Ownership

The simplest form of access control is through direct ownership. If a user is the owner of a record (the `user_id` field matches the user's ID), they have full access to that record.

```python
# Example of a user-owned entity
class UserDocument(Base, BaseMixin, UpdateMixin, UserRefMixin):
    __tablename__ = "user_documents"
    name = Column(String, nullable=False)
    content = Column(Text, nullable=True)
```

### Team Membership

Users can be organized into teams with different roles. Access to team-scoped entities is determined by team membership and the user's role.

```python
# Example of a team-scoped entity
class TeamResource(Base, BaseMixin, UpdateMixin, TeamRefMixin):
    __tablename__ = "team_resources"
    name = Column(String, nullable=False)
    data = Column(Text, nullable=True)
```

### Direct Permissions

The system also supports explicit permissions through the `Permission` table. This allows granting specific permissions to users, teams, or roles for any resource in the system.

Permissions can be:
- **User-specific**: Granted directly to a specific user
- **Team-scoped**: Granted to all members of a team
- **Role-based**: Granted to all users with a specific role or higher

Each permission record specifies what operations are allowed (view, execute, copy, edit, delete, share) and can optionally have an expiration date.

```python
# Example of direct permission assignment
permission = Permission(
    resource_type="documents",
    resource_id="abc123",
    user_id="user456",
    can_view=True,
    can_edit=True,
    expires_at=datetime(2023, 12, 31)
)
```

### Permission References

Entities can inherit permissions from other entities through references. The `permission_references` attribute is a list of relationship attribute names that should be checked for permissions.

Access is granted only if the user has access to ALL entities in the reference chain.

```python
# Example with permission_references
class ProviderInstanceAgent(Base, BaseMixin, UpdateMixin):
    __tablename__ = "provider_instance_agents"
    
    @declared_attr
    def provider_instance_id(cls):
        return cls.create_foreign_key(ProviderInstance)
        
    @declared_attr
    def agent_id(cls):
        return cls.create_foreign_key(Agent)
    
    # User must have access to BOTH provider_instance AND agent
    permission_references = ["provider_instance", "agent"]
    
    provider_instance = relationship(ProviderInstance.__name__, backref="agents")
    agent = relationship(Agent.__name__, backref="provider_instances")
```

### Create Permission Reference

The `create_permission_reference` attribute specifies which referenced entity determines create permissions. This is separate from the regular permission references and is only used for create operations.

```python
# Example with create_permission_reference
class AgentMessage(Base, BaseMixin, UpdateMixin):
    __tablename__ = "agent_messages"
    
    @declared_attr
    def agent_id(cls):
        return cls.create_foreign_key(Agent)
        
    @declared_attr
    def conversation_id(cls):
        return cls.create_foreign_key(Conversation)
    
    # Permission to create is determined by agent permissions
    permission_references = ["agent", "conversation"]
    create_permission_reference = "agent"
    
    content = Column(Text, nullable=False)
```

## Role Hierarchy

The system uses a hierarchical role system, where higher-level roles inherit permissions from lower-level roles. The base role hierarchy is:

1. `user` - Basic user role
2. `admin` - Administrator role (includes user permissions)
3. `superadmin` - Super Administrator role (includes admin permissions)

Roles are stored in the database and can be customized or extended per your application's needs.

## Permission Check Flow

The permission system now uses granular permission functions that match the Permission table fields. Each of these functions follows a similar flow with slight variations based on the permission type:

### General Permission Check Flow

For each permission type (view, execute, copy, edit, delete, share):

1. Check if the user is `ROOT_ID` (always has access)
2. Check if the record exists
3. Check for direct permission in the Permission table
4. If no direct permission, check system-owned records with special rules:
   - For view/execute/copy: TEMPLATE_ID records are accessible to everyone
   - For edit/delete/share: Special restrictions apply (ROOT_ID for system entities)
5. Check permissions through referenced entities (ANY reference can grant permission)
6. Check direct ownership
7. Check team membership with appropriate role (excluding expired memberships)
8. Fall back to general permission check (ownership + team membership)

### Specific Permission Role Requirements

Permission functions have different role requirements when no direct permission exists:

| Permission | Required Role | Special Handling |
|------------|---------------|------------------|
| view       | user          | TEMPLATE_ID accessible to all |
| execute    | user          | TEMPLATE_ID accessible to all |
| copy       | user          | TEMPLATE_ID accessible to all |
| edit       | admin         | Stricter system entity controls |
| delete     | admin         | Stricter system entity controls |
| share      | admin         | Stricter system entity controls |

### Permission Reference Handling

For permission references, the system now uses an "ANY can grant" model:

```python
# Check permissions through referenced entities
if hasattr(record, "permission_references") and record.permission_references:
    # We need to check ALL references, and ANY can grant permission
    for ref_name in record.permission_references:
        ref_attr = getattr(record, ref_name, None)
        if ref_attr is not None:
            # Get ID of the referenced record
            ref_id = getattr(ref_attr, "id", None)
            if ref_id:
                # Get class of the referenced record
                ref_class = type(ref_attr)
                # Check permissions on the referenced record
                if user_can_view(user_id, ref_class, ref_id, db):
                    return True
    
    # If no reference granted permission, return False
    return False
```

This means that if a user has permission to any of the referenced entities, they have permission to the referencing entity. This is different from the previous "ALL must grant" model.

### Create Permission Flow

For creation permissions:

1. Check for system users (`ROOT_ID` can create anything)
2. For Permission table, check if user can manage permissions for the target resource
3. Check `create_permission_reference` if defined
4. Check access to all referenced entities (must have access to all)
5. For user-scoped records, users can always create their own records
6. For team-scoped records, check team membership with sufficient role

### Update and Delete Operations

These operations now use the granular permission functions:

```python
# For update operations
if user_can_edit(requester_id, cls, record.id, db):
    # Allow update
    
# For delete operations  
if user_can_delete(requester_id, cls, record.id, db):
    # Allow delete
```

## Time-Limited Permissions

Both `UserTeam` memberships and `Permission` assignments can be time-limited using the `expires_at` field. This allows for temporary access that automatically expires after a certain date.

### Team Membership Expiration

Team memberships can be set to expire, which is useful for temporary contractors, limited-time collaborations, or trial periods:

```python
user_team = UserTeam(
    user_id="user123",
    team_id="team456",
    role_id="role789",
    enabled=True,
    expires_at=datetime.now() + timedelta(days=30)  # Expires in 30 days
)
```

### Permission Expiration

Direct permissions can also expire, which is useful for granting temporary access to resources:

```python
permission = Permission(
    resource_type="documents",
    resource_id="doc123",
    user_id="user456",
    can_view=True,
    can_edit=True,
    expires_at=datetime.now() + timedelta(hours=24)  # Expires in 24 hours
)
```

### Expiration Checks

The system includes dedicated functions to check for expiration:

```python
def is_team_membership_expired(user_team):
    """
    Check if a user's team membership has expired.
    """
    if not hasattr(user_team, "expires_at") or user_team.expires_at is None:
        return False
    return user_team.expires_at < datetime.now()

def is_permission_expired(permission):
    """
    Check if a permission has expired.
    """
    if not hasattr(permission, "expires_at") or permission.expires_at is None:
        return False
    return permission.expires_at < datetime.now()
```

These expiration checks are integrated into all permission functions:

```python
# When checking team-based permissions
if is_team_membership_expired(user_team):
    continue  # Skip expired memberships

# When checking direct permissions
if is_permission_expired(permission):
    continue  # Skip expired permissions
```

By checking expiration dates at every level, the system ensures that temporary access is properly enforced without needing to run background jobs to clean up expired permissions.

## Permission Delegation

The system supports permission delegation, allowing users to grant permissions to others if they have the appropriate rights. Users can delegate permissions if:

1. They have the `SHARE` permission on the resource
2. They have admin access to the resource

This creates a secure permission delegation chain:

```
Resource Owner -> Administrators -> Users with SHARE permission -> End Users
```

### Delegation Controls

To maintain security, several controls are in place for permission delegation:

1. Users can only delegate permissions they themselves have
2. Only system users can create global permissions (applying to all users)
3. Permission grants can be time-limited with expiration dates
4. Users cannot modify permissions they did not create unless they have admin access to the resource

## Setting Up Permissions

### Model Definition

To use the permission system, your models should extend the appropriate mixins:

```python
class MyEntity(Base, BaseMixin, UpdateMixin, UserRefMixin, TeamRefMixin):
    __tablename__ = "my_entities"
    
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
```

### Setting Permission References

Define `permission_references` as a class attribute listing relationship attributes that determine permissions:

```python
class MyDependentEntity(Base, BaseMixin, UpdateMixin):
    __tablename__ = "my_dependent_entities"
    
    @declared_attr
    def parent_entity_id(cls):
        return cls.create_foreign_key(MyEntity)
        
    parent_entity = relationship(MyEntity.__name__, backref="dependents")
    
    # User must have access to parent_entity to access this entity
    permission_references = ["parent_entity"]
    
    name = Column(String, nullable=False)
```

### Setting Create Permission References

Define `create_permission_reference` to specify which entity determines create permissions:

```python
class CompositeEntity(Base, BaseMixin, UpdateMixin):
    __tablename__ = "composite_entities"
    
    @declared_attr
    def entity_a_id(cls):
        return cls.create_foreign_key(EntityA)
        
    @declared_attr
    def entity_b_id(cls):
        return cls.create_foreign_key(EntityB)
        
    entity_a = relationship(EntityA.__name__, backref="composites")
    entity_b = relationship(EntityB.__name__, backref="composites")
    
    # User must have access to both entity_a and entity_b
    permission_references = ["entity_a", "entity_b"]
    
    # But create permission is determined only by entity_a
    create_permission_reference = "entity_a"
```

## Using Granular Permissions in Application Code

The granular permission functions can be used directly in application code to control access to resources and UI elements.

### Basic Permission Checks

```python
from database.Permissions import user_can_view, user_can_edit, user_can_delete

# Check if user can view a resource
if user_can_view(current_user.id, Document, document_id, db):
    # Show the document
else:
    # Show access denied message

# Check if user can edit a resource
if user_can_edit(current_user.id, Document, document_id, db):
    # Show edit button
else:
    # Hide edit button or disable it

# Check if user can delete a resource
if user_can_delete(current_user.id, Document, document_id, db):
    # Show delete button
else:
    # Hide delete button
```

### Permission-Aware API Endpoints

```python
@router.get("/documents/{document_id}")
def get_document(document_id: str, current_user: User = Depends(get_current_user)):
    from database.Permissions import user_can_view
    
    if not user_can_view(current_user.id, Document, document_id, db):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to view this document"
        )
        
    # Retrieve and return the document
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return document
```

### Permission-Based UI Rendering

```python
# In a template or frontend component
def DocumentActions(props):
    const [permissions, setPermissions] = useState({
        canView: false,
        canEdit: false,
        canDelete: false,
        canShare: false
    });
    
    useEffect(() => {
        // Fetch permissions from backend
        fetchPermissions(props.documentId).then(perms => {
            setPermissions(perms);
        });
    }, [props.documentId]);
    
    return (
        <div className="document-actions">
            {permissions.canView && <button onClick={viewDocument}>View</button>}
            {permissions.canEdit && <button onClick={editDocument}>Edit</button>}
            {permissions.canDelete && <button onClick={deleteDocument}>Delete</button>}
            {permissions.canShare && <button onClick={shareDocument}>Share</button>}
        </div>
    );
}
```

### Permission Endpoint for UI

```python
@router.get("/documents/{document_id}/permissions")
def get_document_permissions(document_id: str, current_user: User = Depends(get_current_user)):
    from database.Permissions import (
        user_can_view, user_can_execute, user_can_copy,
        user_can_edit, user_can_delete, user_can_share
    )
    
    # Check if document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # Return all permissions for this user and document
    return {
        "canView": user_can_view(current_user.id, Document, document_id, db),
        "canExecute": user_can_execute(current_user.id, Document, document_id, db),
        "canCopy": user_can_copy(current_user.id, Document, document_id, db),
        "canEdit": user_can_edit(current_user.id, Document, document_id, db),
        "canDelete": user_can_delete(current_user.id, Document, document_id, db),
        "canShare": user_can_share(current_user.id, Document, document_id, db)
    }
```

## Common Patterns

### User-Owned Resources

For resources owned by a single user:

```python
class UserResource(Base, BaseMixin, UpdateMixin, UserRefMixin):
    __tablename__ = "user_resources"
    name = Column(String, nullable=False)
```

### Team-Scoped Resources

For resources shared within a team:

```python
class TeamResource(Base, BaseMixin, UpdateMixin, TeamRefMixin):
    __tablename__ = "team_resources"
    name = Column(String, nullable=False)
```

### Dual-Scoped Resources (User or Team)

For resources that can be owned by either a user or a team:

```python
class DualScopedResource(Base, BaseMixin, UpdateMixin, UserRefMixin.Optional, TeamRefMixin.Optional):
    __tablename__ = "dual_scoped_resources"
    name = Column(String, nullable=False)
```

### Dependent Resources

For resources that depend on other resources for permissions:

```python
class DependentResource(Base, BaseMixin, UpdateMixin):
    __tablename__ = "dependent_resources"
    
    @declared_attr
    def parent_resource_id(cls):
        return cls.create_foreign_key(Resource)
        
    parent_resource = relationship(Resource.__name__, backref="children")
    
    permission_references = ["parent_resource"]
    create_permission_reference = "parent_resource"
    
    name = Column(String, nullable=False)
```

## Best Practices

1. **Be explicit about permission requirements**: Document which roles can perform which operations.

2. **Use the most specific permission model**: Use direct ownership when appropriate, team-based permissions for shared resources, and reference-based permissions for complex dependencies.

3. **Keep permission references minimal**: Only include relationships that are necessary for permission decisions.

4. **Validate foreign keys**: Ensure that users have appropriate access to referenced entities before creating or updating records.

5. **Use the appropriate system ID**: Choose the most restrictive system ID for system-provided entities.

6. **Override permission methods when needed**: You can override `user_has_read_access`, `user_has_admin_access`, and `user_can_create` for custom permission logic.

7. **Use hooks for advanced permission logic**: Add before/after hooks for create, update, and delete operations to implement complex permission rules.

## Permission Table Overrides

The `Permission` table has special overrides for its permission methods to implement proper delegation controls.

### Read Access Override

```python
@classmethod
def user_has_read_access(cls, user_id, id, db, minimum_role=None, referred=False):
    """
    Users can read a permission if:
    1. They are a system user
    2. They created the permission
    3. They have admin access to the resource the permission is for
    4. They are the target user of the permission
    5. They are a member of the target team of the permission
    6. They have a role that is the target role of the permission or higher
    """
```

### Admin Access Override

```python
@classmethod
def user_has_admin_access(cls, user_id, id, db):
    """
    Users can administer a permission if:
    1. They are a system user
    2. They created the permission
    3. They have admin access to the resource the permission is for
    """
```

### Create Permission Override

```python
@classmethod
def user_can_create(cls, user_id, db, **kwargs):
    """
    Users can create a permission if:
    1. They are a system user
    2. They have SHARE permission or admin access to the resource
    """
```

### Pre-Create Validation Hook

```python
@classmethod
def before_create_hook(cls, record, requester_id, db, return_type, override_dto, **kwargs):
    """
    Validates the permission setup and ensures proper configuration:
    1. Only system users can create global permissions
    2. Validates that referenced resources, users, teams, and roles exist
    3. Ensures the requester has appropriate rights to delegate permissions
    """
```

## Troubleshooting

### Permission Denied Errors

If users are unexpectedly denied access:

1. Check direct user ownership (`user_id`)
2. Check team membership and roles
3. Check for expired team memberships or permissions
4. Verify permission reference chains
5. Check for circular references
6. Look for direct permission assignments in the Permission table
7. Ensure system entities use the correct system ID

### Database Errors

If you're getting database errors related to permissions:

1. Verify all referenced entities exist
2. Check that foreign keys are correctly set up
3. Make sure `permission_references` and `create_permission_reference` point to valid relationship attributes
4. Verify that Permission records reference valid resource types and IDs

### Performance Issues

If permission checks are causing performance issues:

1. Optimize your queries to include necessary joins
2. Consider caching role hierarchies and team memberships
3. Minimize the depth of permission reference chains
4. Use the appropriate permission check (e.g., `check_permissions=False` for internal operations)

### Security Concerns

To ensure your permission system is secure:

1. Always validate input and check permissions on all operations
2. Never expose system IDs to end users
3. Implement proper handling for system-owned records
4. Use the principle of least privilege when assigning roles
5. Regularly audit permission checks in your codebase