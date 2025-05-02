# Extensible Migration System

This document describes the extensible database migration system for the project. The system allows both core database migrations and extension-specific migrations to be managed independently using Alembic and environment variables.

## Overview

The migration system is built on Alembic and provides the following features:

1. Core migrations for base system tables (defined in `src/database/DB_*.py` files)
2. Extension-specific migrations for extension tables (defined in `src/extensions/<extension_name>/DB_*.py` files)
3. Independent migration histories for each extension
4. Ability to run migrations for the core system, specific extensions, or all at once
5. Auto-generation of migrations with proper isolation between core and extension tables
6. Tools for creating new extensions with migration support
7. Migration regeneration for clean starts
8. Dynamic generation of necessary template files (`script.py.mako`)

> **Note**: Known issues that are being worked on:
> - alembic.ini and env.py are not always cleaned up in extensions after migrating on server start
> - Extensions that extend existing tables may attempt to completely recreate the table

## Directory Structure

```
src/
├── database/
│   ├── DB_*.py                 # Core database model files
│   └── migrations/
│       ├── versions/           # Core migrations
│       ├── Migration.py        # Unified migration script
│       └── env.py              # Alembic environment
├── extensions/
│   ├── extension1/
│   │   ├── DB_*.py            # Extension-specific database models
│   │   └── migrations/
│   │       ├── versions/      # Extension-specific migrations (preserved)
│   │       ├── env.py         # Temporary (auto-cleaned)
│   │       └── script.py.mako # Temporary (auto-cleaned)
│   └── extension2/
│       └── ...
```

Note: The `env.py` and `script.py.mako` files in extension directories are temporary and automatically cleaned up after each command execution. Only the `versions/` directory and its contents are preserved.

## Configuration

Extension configuration is managed exclusively through the `APP_EXTENSIONS` environment variable. This variable should contain a comma-separated list of the extension names that should be included in migration operations.

Example:
```bash
export APP_EXTENSIONS="extension1,my_other_extension,ai_agents"
```

- If `APP_EXTENSIONS` is not set or is empty, no extension migrations will be processed.
- All extensions listed in `APP_EXTENSIONS` will be available for migration operations.

## Extension Table Detection

The system uses two methods to identify which tables belong to which extensions:

1. **Table Info Attribute**: When extension models are loaded, the system tags their tables with an extension name in the table's `info` dictionary.
2. **Naming Convention**: Tables that follow the naming convention `extension_name_*` or `ext_extension_name_*` are associated with that extension.

For extension migrations to work correctly:

- Extension model files must be in the `src/extensions/<extension_name>/` directory
- Table names should ideally follow the convention `extension_name_table_name`
- All extension tables must include `__table_args__ = {"extend_existing": True}` to prevent conflicts

## Usage

The migration system is controlled through the unified `Migration.py` script:

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
python src/database/migrations/Migration.py revision -m "description"
```
*Note: `--auto` (autogenerate) is now the default. Use `--no-autogenerate` to create an empty migration file.*

**Create a new migration for an extension:**
```bash
python src/database/migrations/Migration.py revision --extension extension_name -m "description"
```
*Note: Use `--no-autogenerate` to create an empty migration file.*

**Regenerate migrations (delete all and start fresh):**
```bash
# Uses default message "initial schema"
python src/database/migrations/Migration.py revision --regenerate
# Or provide a custom message
python src/database/migrations/Migration.py revision --regenerate -m "Custom initial message"
```

**Regenerate all migrations (core + all extensions):**
```bash
# Uses default message "initial schema" for all regenerated migrations
python src/database/migrations/Migration.py revision --regenerate --all
# Or provide a custom message
python src/database/migrations/Migration.py revision --regenerate --all -m "Custom initial message"
```

*Autogeneration is used by default for regeneration. Empty migrations resulting from autogeneration (no changes detected) will be automatically deleted.*

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

### Creating New Extensions

**Create a new extension with migrations:**
```bash
# 1. Add the extension name to the APP_EXTENSIONS environment variable
export APP_EXTENSIONS="${APP_EXTENSIONS},new_extension_name"

# 2. Run the create command
python src/database/migrations/Migration.py create new_extension_name
```
*Important: Ensure the new extension name is added to `APP_EXTENSIONS` before running `create` or subsequent migration commands for that extension.* 

Options:
- `--skip-model`: Skip creating sample model file
- `--skip-migrate`: Skip creating and applying initial migration

**Initialize migration structure for an existing extension:**
```bash
# 1. Ensure the extension name is in the APP_EXTENSIONS environment variable
export APP_EXTENSIONS="${APP_EXTENSIONS},existing_extension_name"

# 2. Run the init command
python src/database/migrations/Migration.py init existing_extension_name
```

Options:
- `--skip-model`: Skip creating sample model file
- `--skip-migrate`: Skip creating initial migration

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

### Debugging

**Show detailed environment and configuration information:**
```bash
python src/database/migrations/Migration.py debug
```

This will show:
- Environment variables related to the database (including `APP_EXTENSIONS`)
- Database configuration
- Paths being used
- Alembic configuration
- Extension configuration and discovered extensions

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

1. A unique branch label (`ext_<extension_name>`) - only used for the first migration
2. A dedicated version table (`alembic_version_<extension_name>`)

This ensures that:
- Extension migrations can be applied or removed without affecting core migrations
- Core table migrations are never dependent on extension migrations
- Extensions can evolve independently
- Subsequent extension migrations don't re-create branch labels

### Migration File Generation
The `script.py.mako` template file, required by Alembic for generating new revision files, is created dynamically in the appropriate `migrations` directory (core or extension-specific) when the `revision` command is run. It is automatically removed after the command completes or if an error occurs.

### Database Model Registration

To ensure proper isolation and table ownership:

1. Each DB model file should follow the naming convention: `DB_*.py`
2. Tables should use the `__tablename__` attribute
3. Extension tables should be defined in the extension's directory
4. All tables should include `__table_args__ = {"extend_existing": True}` to prevent conflicts

## Implementation Details

The migration system has been optimized for maintainability and robustness through several architectural improvements:

### Utility Functions

The codebase now includes specialized utility functions to handle common operations:

- **File Operations**: Helper functions for file management (`cleanup_file`, `create_temp_file`, `write_file`)
- **Environment Management**: Functions for managing environment variables (`parse_csv_env_var`, `get_common_env_vars`)
- **Subprocess Execution**: Unified subprocess handling (`run_subprocess`)

### Enhanced Module Imports

The module import system has been enhanced with:

- **Safe Import Functions**: Support for multiple import strategies (`import_module_safely`, `import_module_from_file`)
- **Table Tagging**: Automated tagging of tables with extension ownership (`tag_tables_with_extension`)

### Config Management

Configuration has been streamlined with:

- **Centralized Setup**: Unified configuration setup functions
- **Context Configuration**: Shared configuration for online and offline migration modes
- **Table Ownership Detection**: Improved detection of extension table ownership

### Error Handling

Error handling has been improved throughout:

- **Consistent Cleanup**: All temporary files are reliably cleaned up
- **Graceful Error Recovery**: Better recovery from failed operations
- **Detailed Logging**: More informative and consistent log messages

These architectural improvements maintain all functionality while making the codebase more maintainable and robust.

## Adding a New Extension with Database Models

To add a new extension with database migrations:

1.  **Update Environment:** Add the name of your new extension to the `APP_EXTENSIONS` comma-separated environment variable.
    ```bash
    export APP_EXTENSIONS="${APP_EXTENSIONS},my_new_extension"
    ```
2.  **Run Create Command:** Use the `create` command provided by the migration script.
    ```bash
    python src/database/migrations/Migration.py create my_new_extension
    ```

This will:
1. Create the basic extension directory structure (`src/extensions/my_new_extension/`)
2. Create a sample DB model (`DB_MyNewExtension.py`) with `extend_existing=True`
3. Set up the migration infrastructure within the extension (`migrations/` directory)
4. Create and apply the initial migration revision based on the sample model.

Make sure `APP_EXTENSIONS` includes the new extension name *before* running the `create` command.

## Troubleshooting

### Common Issues

1. **Empty migrations for extensions:**
   - Problem: The system isn't properly detecting tables belonging to an extension
   - Solution: 
     - Ensure extension name is correctly set in `APP_EXTENSIONS` environment variable
     - Make sure extension table names follow the convention `extension_name_tablename`
     - Check that the extension models are properly imported during migration
     - Use the debug command to see which extensions are configured

2. **Branch label already used error:**
   - This was a bug where branch labels were added to every migration
   - Fixed by only adding branch labels to the first migration of an extension

3. **Multiple classes found for path error:**
   - Make sure your model class names are unique across the system
   - Use fully qualified imports to avoid ambiguity

4. **Table already exists error:**
   - Ensure your database models use `extend_existing=True` in `__table_args__`
   - Use the `fix` command to automatically add this to all extension tables

5. **Migration not detecting table changes:**
   - Make sure the table belongs to the correct extension or core
   - Check if the table is properly imported during migration
   - Verify your table has the correct `__tablename__` attribute
   - Ensure the table name follows the naming convention of its extension

6. **Tables being recreated:**
   - Extensions that extend existing tables may attempt to completely recreate the table
   - This is a known issue being worked on

### Debugging

When things go wrong, use the `debug` command:
```bash
python src/database/migrations/Migration.py debug
```

This will show:
- Environment variables related to the database (including `APP_EXTENSIONS`)
- Database configuration
- Paths being used
- Alembic configuration
- Extension configuration and discovered extensions

## Cleanup

The migration system automatically cleans up temporary files from extension directories after each command execution. The following files are removed:

- `alembic.ini` - Temporary configuration file
- `env.py` - Temporary environment script
- `script.py.mako` - Temporary migration template

These files are created dynamically when needed and removed when the command completes to avoid cluttering the extension directories. The cleanup process:

1. Preserves all files in the `versions/` directory
2. Preserves all migration files (`*.py`)  
3. Preserves all other files not explicitly listed for cleanup
4. Only removes the specific temporary files listed above
5. Happens automatically after every command, even on error

This ensures a clean directory structure while maintaining all important migration history and model files.

> **Note**: There is a known issue where `alembic.ini` and `env.py` files might not be properly cleaned up in extensions after migrating on server start.

## Best Practices

1. **Keep extensions independent:** Minimize cross-extension dependencies.
2. **Use mixins for shared functionality:** Create common mixins in the core system.
3. **Run migrations frequently:** Smaller, more frequent migrations are easier to manage.
4. **Always include `extend_existing=True`:** Use this in all table definitions to prevent conflicts.
5. **Follow naming conventions:** Use `DB_*.py` for database model files.
6. **Use extension prefixes for table names:** Prefix tables with the extension name (e.g., `extension_name_table_name`).
7. **Test migrations:** Always test migrations on a copy of production data.
8. **Version control your migrations:** Never modify a migration that has been applied to production.
9. **Run all migrations when deploying:** Make sure to run both core and extension migrations during deployment.
10. **Use descriptive migration messages:** Clearly describe what each migration does.
11. **Use the `debug` command when troubleshooting:** If migrations aren't detecting your tables, use the debug command to see what's configured.
12. **Verify environment variables:** Always ensure `APP_EXTENSIONS` contains all the extensions you want to migrate.
13. **Check table names:** Ensure table names follow the extension naming convention and have `extend_existing=True`.
14. **Be cautious with extensions that extend existing tables:** There's a known issue where they may attempt to completely recreate the table.