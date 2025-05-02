# Database Schema Documentation

This document details the database schema design, table relationships, and how they support the application's domain model.

## Core Design Principles

The database schema follows these design principles:

1. **Composition over Inheritance**: Uses mixins to share common functionality across models
2. **Separation of Concerns**: Tables have clear, focused responsibilities
3. **Soft Deletion**: Records are marked as deleted rather than removed from the database
4. **Audit Trails**: Creation and modification metadata is tracked automatically
5. **Reference-based Permissions**: Entities can inherit permissions through references

## Base Types and Configuration

The database supports both PostgreSQL and SQLite backends:

```python
# Base.py
DATABASE_TYPE = env("DATABASE_TYPE")
PK_TYPE = UUID if DATABASE_TYPE != "sqlite" else String
```

This design allows for development with SQLite and production with PostgreSQL without code changes.

## Core Mixins

Several mixins provide standard functionality to models:

### BaseMixin

Provides fundamental fields and methods:
- `id`: Primary key (UUID or String based on database type)
- `created_at`: Timestamp of record creation
- `created_by_user_id`: User who created the record
- CRUD operations: `create()`, `get()`, `list()`, `exists()`, `count()`
- Permission methods: `user_has_read_access()`, `user_has_admin_access()`, etc.

### UpdateMixin

Adds update and delete capabilities:
- `updated_at`: Timestamp of last update
- `updated_by_user_id`: User who last updated the record
- `deleted_at`: Soft deletion timestamp
- `deleted_by_user_id`: User who deleted the record
- Methods: `update()`, `delete()`

### ParentMixin

Enables self-referential hierarchies:
- `parent_id`: Reference to parent record of same type
- `parent`: Relationship to parent record
- `children`: Relationship to child records

### Reference Mixins

Dynamic mixins for foreign key relationships:
- `UserRefMixin`: Links to User table
- `TeamRefMixin`: Links to Team table
- `RoleRefMixin`: Links to Role table
- Created via `create_reference_mixin()` function

## Authentication Models

### User

Core user identity and authentication:
- Email, username, display name, first/last name
- MFA configuration
- Active status

### Team

Organizational grouping for users:
- Name, description, image
- Hierarchical via ParentMixin
- Encryption key for team resources

### Role

Permission roles for access control:
- Name, friendly name
- Hierarchical via ParentMixin
- MFA requirements, password policies
- Optional team scope

### UserTeam

Junction table linking users to teams:
- User, team, and role references
- `enabled` flag for temporary disabling
- `expires_at` for time-limited memberships

### Permission

Fine-grained permissions for resources:
- Resource type and ID
- User, team, or role scope
- Permission flags (view, execute, copy, edit, delete, share)
- `expires_at` for time-limited permissions

## Provider Models

### Provider

Represents external service providers:
- Name, friendly name
- System-managed (system = True)

### ProviderInstance

Concrete instances of providers with credentials:
- User or team ownership
- API key, model name
- Enabled status

### Rotation

Collection of provider instances for failover/load balancing:
- User or team ownership
- Ordered list of provider instances

## Extension Models

### Extension

Represents available system extensions:
- Name, description
- System-managed (system = True)

### Ability

Functionality provided by extensions:
- Extension reference
- Name
- System-managed (system = True)

### ProviderExtension

Links providers to supported extensions:
- Provider reference
- Extension reference
- System-managed (system = True)

## Table Relationships

Key relationships in the schema:

1. **User-Team-Role**: Many-to-many relationship via UserTeam junction table
2. **Provider Hierarchy**: Providers → ProviderInstances → Rotations
3. **Extension Framework**: Extensions → Abilities → ProviderExtensionAbilities
4. **Permission Scope**: Permissions can apply to users, teams, or roles

## Database IDs and System Records

The schema includes predefined system records:

1. **System Users**:
   - ROOT_ID: Super-administrator
   - SYSTEM_ID: System-level operations
   - TEMPLATE_ID: Template resources

2. **System Teams**:
   - System team (ID: "FFFFFFFF-FFFF-FFFF-0000-FFFFFFFFFFFF")

3. **Core Roles**:
   - user: Basic access (ID: "FFFFFFFF-FFFF-FFFF-0000-FFFFFFFFFFFF")
   - admin: Administrative access (ID: "FFFFFFFF-FFFF-FFFF-AAAA-FFFFFFFFFFFF")
   - superadmin: Complete access (ID: "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF")

These records are seeded automatically and have special significance in the permission system.

## Dynamic Schema Evolution

The schema supports dynamic extensions:

1. **Extension Loading**: Extensions define their own models and are loaded from environment variables
2. **Seeding System**: Models implement `seed_list` or `get_seed_list()` to populate initial data
3. **Hook System**: Models can register hooks for CRUD operations

## Database Constraints and Validation

The schema enforces several constraints:

1. **Foreign Key Relationships**: Maintained through mixins for consistency
2. **Soft Deletion**: Records maintain referential integrity even when deleted
3. **Validation**: Column validation through `validate_columns()` function
4. **System Records Protection**: Special handling for system-flagged tables

## Model-specific Behaviors

Some models implement special behavior:

1. **User**: Overrides permission checks to allow users to always see their own records
2. **Permission**: Special handling for permission management
3. **Extension/Provider**: System-managed with dynamic seeding based on environment