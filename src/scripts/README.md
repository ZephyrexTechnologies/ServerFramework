# Database Migration Scripts

This directory contains utility scripts related to database migrations, extensions, and fixing common database-related issues.

## fix_extension_tables.py

This script automatically adds `extend_existing=True` to all extension database table definitions. This is required for extensions that define tables, to prevent duplicate table errors when the models are loaded.

### Usage:

```bash
# Fix all extension DB files
python src/scripts/fix_extension_tables.py

# Fix a specific extension
python src/scripts/fix_extension_tables.py --extension my_extension

# Dry run (preview changes without modifying files)
python src/scripts/fix_extension_tables.py --dry-run
```

## create_extension_migration.py

This script helps create a new extension with initial database models and migrations. It sets up the directory structure, creates sample models, and generates/applies the initial migration.

### Usage:

```bash
# Create a new extension with migrations
python src/scripts/create_extension_migration.py my_extension

# Create without running migrations
python src/scripts/create_extension_migration.py my_extension --skip-migrate
```

## Common Issues and Solutions

### Circular Dependencies

If you see circular dependency errors like:

```
WARNING:root:Circular dependency detected involving database.DB_Agents
```

Follow these steps to fix them:

1. Examine your imports in the affected files
2. Look for cases where A imports from B, and B imports from A
3. Use one of these strategies to break the circle:
   - Use lazy imports (inside functions)
   - Use string references instead of direct class imports
   - Move shared functionality to a common base module
   - Use SQLAlchemy's `ForeignKey` with string references instead of direct relationships

### Duplicate Table Definitions

If you see errors like:

```
Table 'users' is already defined for this MetaData instance. Specify 'extend_existing=True' to redefine options and columns on an existing Table object.
```

This can happen when:

1. Core tables are defined multiple times - this should never happen and indicates a circular import issue
2. Extension tables have the same name as core tables - the extension tables need `extend_existing=True`

To fix extension tables, run:

```bash
python src/scripts/fix_extension_tables.py
```

For core tables, fix your imports:

1. Make sure you don't have circular imports in core models
2. Consider running your migrations with only the necessary extensions:
   ```
   python src/database/migrations/Migration.py upgrade --extension my_extension
   ```

### Bad Model Registration

If you see errors like:

```
Multiple classes found for path "User" in the registry of this declarative base. Please use a fully module-qualified path.
```

This happens when there are multiple classes with the same name. To fix:

1. Make your class names unique
2. Use fully qualified imports
3. Use the `name` parameter in relationship definitions
4. Add your classes to a custom registry instead of Base

## Best Practices for Database Models

1. **Never modify** a migration that has been applied to a deployed database
2. Always use **unique class names** for your models
3. Use **string references** in foreign keys and relationships when possible
4. **Core tables** should never use `extend_existing=True`
5. **Extension tables** should always use `extend_existing=True` 
6. **Extensions** should keep their DB files self-contained
7. Add **__table_args__** to all extension tables: `__table_args__ = {"extend_existing": True}`
8. Use **fully qualified imports** instead of wildcard imports
9. Break **circular dependencies** by refactoring shared functionality 