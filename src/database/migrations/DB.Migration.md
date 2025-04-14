# Extensible Migration System

This document describes the extensible database migration system for the project. The system allows both core database migrations and extension-specific migrations to be managed independently.

## Overview

The migration system is built on Alembic and provides the following features:

1. Core migrations for base system tables (defined in `src/database/DB_*.py` files)
2. Extension-specific migrations for extension tables (defined in `src/extensions/<extension_name>/DB_*.py` files)
3. Independent migration histories for each extension
4. Ability to run migrations for the core system, specific extensions, or all at once
5. Auto-generation of migrations with proper isolation between core and extension tables

## Directory Structure

```
src/
├── database/
│   ├── DB_*.py                 # Core database model files
│   └── migrations/
│       ├── versions/           # Core migrations
│       ├── Migration.py        # Main migration script
│       ├── MigrationHelper.py  # Helper functions
│       ├── env.py              # Alembic environment
│       └── migration_extensions.json  # Extension configuration
├── extensions/
│   ├── extension1/
│   │   ├── DB_*.py            # Extension-specific database models
│   │   └── migrations/
│   │       ├── versions/      # Extension-specific migrations
│   │       ├── env.py         # Symlink to core env.py
│   │       └── script.py.mako # Template for migration scripts
│   └── extension2/
│       └── ...
```

## Configuration

Extension configuration is managed through `migration_extensions.json`:

```json
{
    "extensions": ["extension1", "extension2"],
    "auto_discover": false
}
```

- `extensions`: List of extension names to include in migration operations
- `auto_discover`: If true, automatically discover all extensions with migrations

You can also override the extension list by setting the `OVERRIDE_EXTENSION_LIST` environment variable:

```bash
export OVERRIDE_EXTENSION_LIST='["extension1", "extension2"]'
```

## Usage

The migration system is controlled through the `Migration.py` script:

### Running Migrations

**Upgrade the core database:**
```bash
python src/database/migrations/Migration.py upgrade
```

**Upgrade a specific extension:**
```bash
python src/database/migrations/Migration.py upgrade --extension extension_name
```

**Upgrade all (core + all extensions):**
```bash
python src/database/migrations/Migration.py upgrade --all
```

**Specify a target revision:**
```bash
python src/database/migrations/Migration.py upgrade --target revision_id
```

### Creating Migrations

**Create a new migration for core:**
```bash
python src/database/migrations/Migration.py revision -m "description" --auto
```

**Create a new migration for an extension:**
```bash
python src/database/migrations/Migration.py revision --extension extension_name -m "description" --auto
```

The `--auto` flag generates migration content based on model changes. Omit it to create an empty migration.

### Checking Status

**Show migration history:**
```bash
python src/database/migrations/Migration.py history
python src/database/migrations/Migration.py history --extension extension_name
```

**Show current version:**
```bash
python src/database/migrations/Migration.py current
python src/database/migrations/Migration.py current --extension extension_name
```

### Initializing Extensions

**Initialize migration structure for an extension:**
```bash
python src/database/migrations/Migration.py init --extension extension_name
```

You can also use the helper script for a more complete setup:
```bash
python src/scripts/init_extension_migration.py extension_name
```

This helper script will:
1. Create the extension directory if it doesn't exist
2. Add the extension to the migration_extensions.json configuration
3. Create a sample DB model file
4. Initialize the migration structure
5. Create and apply the initial migration

Add `--skip-model` to skip creating the sample model or `--skip-apply` to skip applying the migration.

### Downgrading

**Downgrade core:**
```bash
python src/database/migrations/Migration.py downgrade --target target_revision
```

**Downgrade extension:**
```bash
python src/database/migrations/Migration.py downgrade --extension extension_name --target target_revision
```

**Downgrade all:**
```bash
python src/database/migrations/Migration.py downgrade --all --target target_revision
```

## How It Works

### Database Model Structure

The system isolates tables based on their source files:

1. Core tables: Defined in `src/database/DB_*.py` files
2. Extension tables: Defined in `src/extensions/<extension_name>/DB_*.py` files

When generating migrations, the system identifies which tables belong to which module, ensuring proper separation:

- Core migrations only include changes to core tables
- Extension migrations only include changes to tables owned by that extension

### Migration History

Each extension maintains its own independent migration history through:

1. A unique branch label (`ext_<extension_name>`)
2. A dedicated version table (`alembic_version_<extension_name>`)

This ensures that:
- Extension migrations can be applied or removed without affecting core migrations
- Core table migrations are never dependent on extension migrations
- Extensions can evolve independently

### Database Model Registration

To ensure proper isolation and table ownership:

1. Each DB model file should follow the naming convention: `DB_*.py`
2. Tables should use the `__tablename__` attribute
3. Extension tables should be defined in the extension's directory
4. All tables should include `__table_args__ = {"extend_existing": True}` to prevent conflicts

## Adding a New Extension with Database Models

### Method 1: Using the Helper Script

The simplest way to add a new extension with database migrations:

```bash
python src/scripts/init_extension_migration.py new_extension
```

This will:
1. Create the extension directory structure
2. Add the extension to the configuration
3. Create a sample DB model
4. Set up the migration structure
5. Create and apply the initial migration

### Method 2: Manual Setup

If you prefer a more manual approach:

1. Create the extension directory: `src/extensions/new_extension/`
2. Create your database model file: `src/extensions/new_extension/DB_NewExtension.py`
3. Add the extension to `migration_extensions.json` if `auto_discover` is false
4. Initialize the migration structure:
   ```bash
   python src/database/migrations/Migration.py init --extension new_extension
   ```
5. Generate the first migration:
   ```bash
   python src/database/migrations/Migration.py revision --extension new_extension -m "Initial migration" --auto
   ```
6. Apply the migration:
   ```bash
   python src/database/migrations/Migration.py upgrade --extension new_extension
   ```

## Troubleshooting

### Common Issues

1. **"Can't locate revision" error:**
   - This usually means the extension migration is trying to find a revision that doesn't exist in its context
   - Ensure the extension has an initial migration that starts from `base`
   - Try re-initializing the extension with the `init` command

2. **Multiple classes found for path error:**
   - Make sure your model class names are unique across the system
   - Use fully qualified imports to avoid ambiguity

3. **Table already exists error:**
   - Ensure your database models use `extend_existing=True` in `__table_args__`
   - Example: `__table_args__ = {'extend_existing': True}`
   - You can use the `src/scripts/fix_extension_tables.py` script to automatically add this to all extension tables

4. **Circular dependencies:**
   - Check your import structure for circular references
   - Consider using late binding or restructuring your models

5. **Migration not detecting table changes:**
   - Make sure the table belongs to the correct extension or core
   - Check if the table is properly imported during migration
   - Verify your table has the correct `__tablename__` attribute

### Debugging

When things go wrong, check:

1. The Python path first entries (printed during migration)
2. The detected core/extension tables (printed during migration)
3. Environment variables like `ALEMBIC_EXTENSION` and `OVERRIDE_EXTENSION_LIST`
4. Log files for detailed error information

You can also use the debug command for detailed information:
```bash
python src/database/migrations/Migration.py debug
```

This will show:
- Environment variables related to the database
- Database configuration
- Paths being used
- Alembic configuration
- Extension configuration and discovered extensions

### Fixing Extension Tables

If you're getting errors related to table conflicts, you can use the `fix_extension_tables.py` script to add `extend_existing=True` to all extension tables:

```bash
python src/scripts/fix_extension_tables.py
```

To fix tables for a specific extension:
```bash
python src/scripts/fix_extension_tables.py --extension extension_name
```

## Best Practices

1. **Keep extensions independent:** Minimize cross-extension dependencies.
2. **Use mixins for shared functionality:** Create common mixins in the core system.
3. **Run migrations frequently:** Smaller, more frequent migrations are easier to manage.
4. **Always include `extend_existing=True`:** Add this to your table definitions to prevent conflicts.
5. **Follow naming conventions:** Use `DB_*.py` for database model files.
6. **Use extension prefixes for table names:** Prefix tables with the extension name (e.g., `extension_name_table_name`).
7. **Test migrations:** Always test migrations on a copy of production data.
8. **Version control your migrations:** Never modify a migration that has been applied to production.
9. **Run all migrations when deploying:** Make sure to run both core and extension migrations during deployment.
10. **Use descriptive migration messages:** Clearly describe what each migration does.