"""
THIS FILE IS NOT INTENDED TO BE USED IN-PLACE!
IT SHOULD BE COPIED INTO `src/extensions/extension_name/migrations`!
REMEMBER TO ALSO GENERATE AND MODIFY AN `alembic.ini`!
"""

import importlib.util
import os
import sys
from logging.config import fileConfig

from alembic import context

# Setup the Python path
extension_migrations_dir = os.path.abspath(os.path.dirname(__file__))
src_dir = os.path.abspath(os.path.join(extension_migrations_dir, "..", "..", ".."))
database_dir = os.path.abspath(os.path.join(src_dir, "database"))
migrations_dir = os.path.abspath(os.path.join(src_dir, "migrations"))
src_dir = os.path.abspath(os.path.join(database_dir, ".."))
root_dir = os.path.abspath(os.path.join(src_dir, ".."))

# Debug print
print(
    f"Alembic env.py paths: migrations={migrations_dir}, database={database_dir}, src={src_dir}, root={root_dir}"
)


# Check for duplicate path components - prevent adding src/src patterns
def normalize_path(path):
    components = path.split(os.sep)
    result = []
    for i, comp in enumerate(components):
        if i > 0 and comp and comp == components[i - 1]:
            continue  # Skip duplicated component
        result.append(comp)
    return os.sep.join(result)


src_dir = normalize_path(src_dir)
root_dir = normalize_path(root_dir)

# Add root and src to Python path (with deduplication check)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

print(f"Python path first 3 entries: {sys.path[:3]}")

# Check for extension-specific migration mode
target_extension = env("ALEMBIC_EXTENSION")
if target_extension:
    print(f"Extension-specific migration mode for: {target_extension}")
else:
    print("Core migration mode (no specific extension)")

# Import the custom import helpers
try:
    # First try importing directly
    from lib.Import import scoped_import
except ImportError:
    # If that fails, try dynamic import
    import_path = os.path.join(src_dir, "lib", "Import.py")
    if os.path.exists(import_path):
        spec = importlib.util.spec_from_file_location("Import", import_path)
        Import = importlib.util.module_from_spec(spec)
        sys.modules["Import"] = Import
        spec.loader.exec_module(Import)
        scoped_import = Import.scoped_import
    else:
        print(f"Warning: Could not import scoped_import, file not found: {import_path}")

        # Define a fallback function
        def scoped_import(file_type="DB", scopes=None):
            """Fallback implementation if Import.py is not available"""
            return [], []


# Now import models based on the target extension
if target_extension:
    # When targeting a specific extension, only load models from that extension
    imported_modules, import_errors = scoped_import(
        file_type="DB", scopes=[f"extensions.{target_extension}"]
    )

    if import_errors:
        print(f"Errors importing extension models from {target_extension}:")
        for file_path, error in import_errors:
            print(f"  - {file_path}: {error}")
else:
    # For core migrations or when running all migrations, import all DB models
    # First import core database models
    imported_core_modules, core_errors = scoped_import(
        file_type="DB", scopes=["database"]
    )

    # Then import all extension models
    imported_ext_modules, ext_errors = scoped_import(
        file_type="DB", scopes=["extensions"]
    )

    imported_modules = imported_core_modules + imported_ext_modules
    import_errors = core_errors + ext_errors

    if import_errors:
        print("Errors importing models:")
        for file_path, error in import_errors:
            print(f"  - {file_path}: {error}")

# Import database configuration after models are loaded
from Environment import env

from database.Base import DATABASE_URI, Base, engine

# Verify all tables are in metadata
print(f"Tables in metadata: {', '.join(Base.metadata.tables.keys())}")

# Store tables for extension-specific migrations
extension_tables = set()

# Filter tables for extension-specific migrations
if target_extension:
    # Get the original tables
    all_tables = dict(Base.metadata.tables)

    # Find tables that are directly owned by this extension
    extension_prefix = f"ext_{target_extension}_"

    # Identify tables that belong to this extension
    for table_name, table in all_tables.items():
        # Include tables specifically for this extension (using naming convention)
        # or tables that are defined in this extension's DB files
        if table_name.startswith(extension_prefix) or any(
            f"extensions.{target_extension}"
            in getattr(table, "info", {}).get("module_path", "")
            for table in [table]
        ):
            extension_tables.add(table_name)

    print(f"Extension {target_extension} owns tables: {', '.join(extension_tables)}")

    # We'll use the include_object hook to filter objects for autogenerate
    def include_object(object, name, type_, reflected, compare_to):
        try:
            if type_ == "table":
                # Only include tables owned by this extension
                return name in extension_tables
            elif type_ == "column":
                # Include all columns from included tables
                if hasattr(object, "table") and hasattr(object.table, "name"):
                    return object.table.name in extension_tables
                # Safety check for unexpected object structure
                return False
            elif type_ == "index":
                # Only include indexes on tables owned by this extension
                if hasattr(object, "table") and hasattr(object.table, "name"):
                    return object.table.name in extension_tables
                # Safety check for unexpected object structure
                return False
            elif type_ == "foreign_key_constraint":
                # Only include foreign keys defined on tables owned by this extension
                if (
                    hasattr(object, "parent")
                    and hasattr(object.parent, "table")
                    and hasattr(object.parent.table, "name")
                ):
                    return object.parent.table.name in extension_tables
                # Safety check for unexpected object structure
                return False
            else:
                # For other object types, we need to be more careful
                if hasattr(object, "table") and hasattr(object.table, "name"):
                    return object.table.name in extension_tables
                if (
                    hasattr(object, "parent")
                    and hasattr(object.parent, "table")
                    and hasattr(object.parent.table, "name")
                ):
                    return object.parent.table.name in extension_tables
                # If we can't determine ownership, don't include it
                return False
        except Exception as e:
            # If there's any error determining ownership, log it and don't include the object
            print(f"Error in include_object for {type_} {name}: {e}")
            return False

    # Use the full metadata but with a filter
    target_metadata = Base.metadata

else:
    # Use all tables for core migrations - no filtering needed
    target_metadata = Base.metadata
    include_object = None

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override the sqlalchemy.url with your dynamic connection string
config.set_main_option("sqlalchemy.url", DATABASE_URI)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")

    context_options = {
        "url": url,
        "target_metadata": target_metadata,
        "literal_binds": True,
        "dialect_opts": {"paramstyle": "named"},
        "version_table_schema": None,
        "include_schemas": True,
    }

    # Add the include_object hook if we're in extension mode
    if target_extension:
        context_options["include_object"] = include_object
        # For extension migrations, also set the version table
        context_options["version_table"] = f"alembic_version_{target_extension}"

    context.configure(**context_options)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Use the existing engine instead of creating a new one
    connectable = engine

    with connectable.connect() as connection:
        context_options = {
            "connection": connection,
            "target_metadata": target_metadata,
            # This option helps with SQLite "table already exists" errors
            "compare_type": True,
            "compare_server_default": True,
            # Include schemas option if you're using PostgreSQL schemas
            "include_schemas": True,
            # For SQLite, include a hook to handle table already exists errors
            "render_as_batch": True,
        }

        # Add the include_object hook if we're in extension mode
        if target_extension:
            context_options["include_object"] = include_object

            # For extension migrations, also set the version table
            # This ensures each extension has its own alembic_version table
            context_options["version_table"] = f"alembic_version_{target_extension}"

        context.configure(**context_options)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
