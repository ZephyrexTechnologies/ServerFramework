import importlib
import importlib.util
import logging
import sys
from logging.config import fileConfig
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


# Add robust path handling for imports
def setup_python_path():
    """
    Ensure Python path includes all necessary directories
    for properly resolving imports
    """
    from lib.Environment import env

    # Check if we're in an extension context (set by ALEMBIC_EXTENSION)
    extension_name = env("ALEMBIC_EXTENSION")

    # Get the current file's location and derive paths
    current_file = Path(__file__).resolve()
    migrations_dir = current_file.parent

    if extension_name:
        # In extension context, we need to find the right paths
        logging.info(f"Setting up paths for extension context: {extension_name}")
        # Work backwards to find src_dir and project_root
        database_dir = (
            migrations_dir.parent.parent
        )  # extensions/<ext>/migrations -> src/database
        src_dir = database_dir.parent  # src/database -> src
        project_root = src_dir.parent  # src -> project_root
    else:
        # In core context
        logging.info("Setting up paths for core context")
        database_dir = migrations_dir.parent
        src_dir = database_dir.parent
        project_root = src_dir.parent

    # Add to Python path if not already there
    # Ensure paths are strings for sys.path
    project_root_str = str(project_root)
    src_dir_str = str(src_dir)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
    if src_dir_str not in sys.path:
        sys.path.insert(0, src_dir_str)

    logging.info(
        f"Python path setup complete. Project Root: {project_root_str}, Src Dir: {src_dir_str}. First 5 sys.path: {sys.path[:5]}"
    )

    return {
        "migrations_dir": migrations_dir,
        "database_dir": database_dir,
        "src_dir": src_dir,
        "project_root": project_root,
    }


# Setup paths before importing anything else
paths = setup_python_path()

from alembic import context

# Now we can import SQLAlchemy and Alembic
from sqlalchemy import engine_from_config, pool

from lib.Environment import env


# Get environment variables for database configuration
def get_database_info():
    """Extract database configuration from environment variables"""
    db_type = env("DATABASE_TYPE")
    db_name = env("DATABASE_NAME")
    db_host = env("DATABASE_HOST")
    db_port = env("DATABASE_PORT")
    db_user = env("DATABASE_USER")
    db_pass = env("DATABASE_PASSWORD")
    db_ssl = env("DATABASE_SSL")

    logging.info(f"Database configuration from env: TYPE={db_type}, NAME={db_name}")

    # Construct database URL based on database type
    if db_type == "sqlite":
        # Use the database name to create a proper SQLite URL
        db_url = f"sqlite:///{db_name}.db"
    elif db_type == "postgresql":
        db_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?sslmode={db_ssl}"
    else:
        logging.warning(f"Unsupported database type: {db_type}, falling back to SQLite")
        db_url = f"sqlite:///{db_name}.db"

    logging.info(f"Constructed database URL: {db_url}")
    return db_type, db_name, db_url


def import_module_safely(module_path, error_prefix=""):
    """Try to import a module safely with multiple strategies"""
    try:
        # Try standard import first
        module = importlib.import_module(module_path)
        logging.info(f"Imported {module_path}")
        return module
    except ImportError:
        try:
            # Try with src prefix
            src_module_path = f"src.{module_path}"
            module = importlib.import_module(src_module_path)
            logging.info(f"Imported {module_path} via src prefix")
            return module
        except ImportError as e:
            # Log the error and return None
            if error_prefix:
                logging.error(f"{error_prefix}: {e}")
            else:
                logging.error(f"Failed to import {module_path}: {e}")
            return None


def import_module_from_file(file_path, module_name):
    """Import a module directly from a file path"""
    try:
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        logging.info(f"Imported {module_name} via file loader")
        return module
    except Exception as e:
        logging.error(f"Failed to import {module_name} from file {file_path}: {e}")
        return None


def tag_tables_with_extension(module, extension_name):
    """Tag all tables in a module as belonging to an extension"""
    tables_tagged = 0
    for name, obj in vars(module).items():
        if hasattr(obj, "__tablename__") and hasattr(obj, "__table__"):
            if not hasattr(obj.__table__, "info"):
                obj.__table__.info = {}
            obj.__table__.info["extension"] = extension_name
            logging.info(
                f"env.py: Tagged table {obj.__tablename__} as part of extension {extension_name}"
            )
            tables_tagged += 1
    return tables_tagged


# Import the Base class
try:
    logging.info("Trying to import Base...")
    from database.Base import Base

    logging.info("Base imported successfully")

    # Check if we can connect to the database
    # This helps with troubleshooting when the Base is found but the connection fails
    try:
        db_type, db_name, db_url = get_database_info()
        from sqlalchemy import create_engine

        engine = create_engine(db_url)
        connection = engine.connect()
        connection.close()
        logging.info(f"Successfully connected to database: {db_url}")
    except Exception as e:
        logging.warning(f"Database connection check failed: {e}")

except ImportError:
    # If direct import fails, try with src prefix
    Base = (
        import_module_safely("database.Base", "Failed to import Base").Base
        if import_module_safely("database.Base")
        else None
    )
    if Base is None:
        raise ImportError("Could not import Base after multiple attempts")
    logging.info("Base imported from alternative path")

# Add JSON import (needed for extension config)
try:
    import json
except ImportError:
    # If JSON import fails, define a minimal JSON parser (very unlikely)
    class json:
        @staticmethod
        def load(file):
            return eval(file.read())


# Import all database models
def import_all_models():
    """Import all database model files"""
    logging.info("Importing all database models...")

    # Import all DB_* files from database directory
    db_files = list(Path(paths["database_dir"]).glob("DB_*.py"))
    logging.info(f"Found {len(db_files)} database model files")

    for db_file in db_files:
        module_name = db_file.stem  # Filename without extension
        logging.info(f"Importing {module_name}...")

        # Try standard import
        module = import_module_safely(f"database.{module_name}")
        if module is None:
            # If standard imports fail, try direct file loading
            import_module_from_file(db_file, module_name)

    # Check for extension-specific imports
    extension_name = env("ALEMBIC_EXTENSION")
    if extension_name:
        import_extension_models(extension_name)

    logging.info("Finished importing models")


def import_extension_models(extension_name):
    """Import models for a specific extension"""
    logging.info(f"Importing models for extension: {extension_name}")
    ext_path = paths["src_dir"] / "extensions" / extension_name
    logging.info(f"env.py: Extension path: {ext_path}")

    if not ext_path.exists():
        logging.error(f"env.py: Extension path does not exist: {ext_path}")
        return

    # Try to import the main extension module
    ext_module = import_module_safely(f"extensions.{extension_name}")
    if ext_module:
        logging.info(
            f"env.py: Successfully imported extension base module: {extension_name}"
        )

    # Look for DB_* files in the extension
    ext_db_files = list(Path(ext_path).glob("DB_*.py"))
    logging.info(
        f"env.py: Found {len(ext_db_files)} DB files in extension {extension_name}: {[f.name for f in ext_db_files]}"
    )

    if not ext_db_files:
        logging.warning(
            f"env.py: No DB_*.py files found in {ext_path} for extension {extension_name}"
        )
        return

    for ext_file in ext_db_files:
        ext_module_name = ext_file.stem
        module_import_path = f"extensions.{extension_name}.{ext_module_name}"
        logging.info(
            f"env.py: Attempting to import extension model: {module_import_path}"
        )

        # Try to import the module
        module = import_module_safely(module_import_path)
        if module:
            # Tag tables from this extension for filtering in migrations
            tables_tagged = tag_tables_with_extension(module, extension_name)
            if tables_tagged == 0:
                logging.warning(
                    f"env.py: No SQLAlchemy models with __tablename__ found in {module_import_path}"
                )
        else:
            # If standard imports fail, try direct file loading
            module = import_module_from_file(ext_file, ext_module_name)
            if module:
                tables_tagged = tag_tables_with_extension(module, extension_name)
                if tables_tagged == 0:
                    logging.warning(
                        f"env.py: No SQLAlchemy models with __tablename__ found in {ext_file}"
                    )


# Import all models before configuring Alembic
import_all_models()

# Alembic Config object
config = context.config


def setup_alembic_config():
    """Configure Alembic settings from environment and determine version table"""
    # Override the SQLAlchemy URL from environment
    db_type, db_name, db_url = get_database_info()
    config.set_main_option("sqlalchemy.url", db_url)
    logging.info(f"Set sqlalchemy.url in Alembic config to: {db_url}")

    # Determine version table based on extension context
    extension_name = env("ALEMBIC_EXTENSION")
    version_table = "alembic_version"

    if extension_name:
        version_table = f"alembic_version_{extension_name}"
        logging.info(f"Using extension-specific version table: {version_table}")
        config.set_main_option("version_table", version_table)

    # Check for direct DATABASE_URL override
    sqlalchemy_url = env("DATABASE_URL")
    if sqlalchemy_url:
        logging.info(f"Overriding with DATABASE_URL from environment: {sqlalchemy_url}")
        config.set_main_option("sqlalchemy.url", sqlalchemy_url)

    # Check if we have a URL in the config
    if not config.get_main_option("sqlalchemy.url"):
        # For tests, default to SQLite
        test_url = f"sqlite:///{db_name}.test.db"
        logging.warning(f"No database URL configured, using test URL: {test_url}")
        config.set_main_option("sqlalchemy.url", test_url)

    # Log the final URL being used
    final_url = config.get_main_option("sqlalchemy.url")
    logging.info(f"Final sqlalchemy.url being used: {final_url}")

    return version_table


# Configure Alembic
version_table = setup_alembic_config()

# Set up Python logging from config
if config.config_file_name:
    fileConfig(config.config_file_name)

# Set the MetaData object for migrations
target_metadata = Base.metadata

# Log metadata contents before defining include_object
logging.info(
    f"env.py: Tables known to Base.metadata before filtering: {list(target_metadata.tables.keys())}"
)


def is_table_owned_by_extension(name, extension_name=None):
    """Check if a table is owned by a specific extension based on naming or info.
    If extension_name is None, returns the owner extension name if any, or False."""
    # First, check if the table is defined in Base.metadata
    if name not in Base.metadata.tables:
        logging.info(f"env.py: Table '{name}' not found in Base.metadata")
        return False

    table_info = Base.metadata.tables[name].info
    table_owner = table_info.get("extension")

    # If no extension provided, just return the owner if any
    if extension_name is None:
        return table_owner

    # Check if explicitly owned by this extension
    if table_owner == extension_name:
        logging.info(
            f"env.py: Table '{name}' belongs to extension '{extension_name}' (info match)"
        )
        return True

    # Check naming convention
    if name.startswith(f"{extension_name}_") or name.startswith(
        f"ext_{extension_name}_"
    ):
        # Only include via name if it wasn't explicitly assigned to another extension
        if table_owner is None or table_owner == extension_name:
            logging.info(
                f"env.py: Table '{name}' belongs to extension '{extension_name}' (name prefix match)"
            )
            return True
        else:
            logging.info(
                f"env.py: Table '{name}' has prefix of extension '{extension_name}' but is owned by '{table_owner}'"
            )
            return False

    # If we reach here, the table doesn't belong to the extension
    logging.info(
        f"env.py: Table '{name}' does not belong to extension '{extension_name}'"
    )
    return False


def include_object(object, name, type_, reflected, compare_to):
    """
    Filter tables based on the current migration context (core or extension)

    This function determines whether a database object should be included
    in the autogeneration process based on ownership.
    """
    if type_ == "table":
        # Get the current extension being processed (if any)
        extension_name = env("ALEMBIC_EXTENSION")
        logging.info(
            f"env.py: include_object checking table '{name}' with context extension: '{extension_name}'"
        )

        if extension_name:
            # In extension context, only include tables from this extension
            should_include = is_table_owned_by_extension(name, extension_name)

            # Make a final decision
            if should_include:
                # Check if this table already exists in another extension's schema
                # or in the core schema
                if reflected:
                    logging.info(
                        f"env.py: FINAL: Excluding table '{name}' for extension '{extension_name}' - table already exists in database"
                    )
                    return False

                # Check if the table exists in the core schema but isn't yet reflected (first migration)
                core_tables = []
                for t in Base.metadata.tables.keys():
                    # A table is part of core if it's not owned by any extension
                    table_owner = Base.metadata.tables[t].info.get("extension")
                    if not table_owner and t != name:
                        core_tables.append(t)

                # Also check for naming convention matches in core tables
                if name in core_tables or any(name == t for t in core_tables):
                    logging.info(
                        f"env.py: FINAL: Excluding table '{name}' for extension '{extension_name}' - table already exists in core schema"
                    )
                    return False

                logging.info(
                    f"env.py: FINAL: Including table '{name}' for extension '{extension_name}'"
                )
            else:
                logging.info(
                    f"env.py: FINAL: Excluding table '{name}' - not part of extension '{extension_name}'"
                )

            return should_include
        else:
            # In core context, exclude tables from extensions
            table_owner = is_table_owned_by_extension(name)
            if table_owner:
                logging.info(
                    f"env.py: Excluding table '{name}' - belongs to extension '{table_owner}' (info)"
                )
                return False

            # Check for naming convention based exclusion
            app_extensions = parse_csv_env_var("APP_EXTENSIONS")

            for ext_name in app_extensions:
                if name.startswith(f"{ext_name}_") or name.startswith(
                    f"ext_{ext_name}_"
                ):
                    logging.info(
                        f"env.py: Excluding table '{name}' - belongs to extension '{ext_name}' (name prefix)"
                    )
                    return False

            logging.info(f"env.py: FINAL: Including table '{name}' - part of core")
            return True

    # For non-table objects, include them by default
    logging.info(f"env.py: Including object '{name}' of type '{type_}'")
    return True


def parse_csv_env_var(env_var_name, default=None):
    """Parse a comma-separated environment variable into a list of strings."""
    value = env(env_var_name)
    if not value:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


def get_alembic_context_config(connection=None, url=None):
    """Configure context for either online or offline mode."""
    config_args = {
        "target_metadata": target_metadata,
        "include_object": include_object,
        "version_table": version_table,
        "render_as_batch": True,  # Helps with SQLite "table already exists" errors
    }

    if connection:
        # Online mode with connection
        config_args["connection"] = connection
    else:
        # Offline mode with URL
        config_args.update(
            {"url": url, "literal_binds": True, "dialect_opts": {"paramstyle": "named"}}
        )

    return config_args


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    logging.info(f"Running offline migrations with URL: {url}")

    context_config = get_alembic_context_config(url=url)
    context.configure(**context_config)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    # Log the configuration being used
    db_section = config.get_section(config.config_ini_section)
    logging.info(f"Running online migrations with config: {db_section}")

    connectable = engine_from_config(
        db_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context_config = get_alembic_context_config(connection=connection)
        context.configure(**context_config)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
