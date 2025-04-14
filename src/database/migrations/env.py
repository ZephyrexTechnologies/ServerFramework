import importlib
import importlib.util
import logging
import os
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
    # Get absolute path of current file (env.py)
    current_file = Path(__file__).resolve()

    # Get parent directories
    migrations_dir = current_file.parent
    database_dir = migrations_dir.parent
    src_dir = database_dir.parent
    project_root = src_dir.parent

    # Add to Python path if not already there
    for path in [str(project_root), str(src_dir)]:
        if path not in sys.path:
            sys.path.insert(0, path)

    logging.info(f"Python path setup complete. First 5 paths: {sys.path[:5]}")

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
    try:
        logging.info("Trying alternative import for Base...")
        from src.database.Base import Base

        logging.info("Base imported from alternative path")
    except ImportError as e:
        logging.error(f"Failed to import Base: {e}")
        raise

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
    db_files_pattern = os.path.join(paths["database_dir"], "DB_*.py")
    db_files = [f for f in Path(paths["database_dir"]).glob("DB_*.py")]

    logging.info(f"Found {len(db_files)} database model files")

    for db_file in db_files:
        module_name = db_file.stem  # Filename without extension
        logging.info(f"Importing {module_name}...")

        try:
            # Try standard import first
            importlib.import_module(f"database.{module_name}")
            logging.info(f"Imported {module_name}")
        except ImportError:
            try:
                # Try with src prefix
                importlib.import_module(f"src.database.{module_name}")
                logging.info(f"Imported {module_name} via src prefix")
            except ImportError as e:
                # Try direct module loading as last resort
                try:
                    spec = importlib.util.spec_from_file_location(
                        module_name, str(db_file)
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    logging.info(f"Imported {module_name} via file loader")
                except Exception as e:
                    logging.error(f"Failed to import {module_name}: {e}")

    # Check for extension-specific imports
    extension_name = env("ALEMBIC_EXTENSION")
    if extension_name:
        logging.info(f"Importing models for extension: {extension_name}")
        ext_path = os.path.join(paths["src_dir"], "extensions", extension_name)

        if os.path.exists(ext_path):
            try:
                # Try to import the main extension module
                try:
                    importlib.import_module(f"extensions.{extension_name}")
                    logging.info(f"Imported extension module: {extension_name}")
                except ImportError:
                    # Try with src prefix
                    importlib.import_module(f"src.extensions.{extension_name}")
                    logging.info(
                        f"Imported extension module via src prefix: {extension_name}"
                    )

                # Look for DB_* files in the extension
                ext_db_files = [f for f in Path(ext_path).glob("DB_*.py")]
                logging.info(
                    f"Found {len(ext_db_files)} DB files in extension {extension_name}"
                )

                for ext_file in ext_db_files:
                    ext_module = ext_file.stem
                    try:
                        # Mark tables from this extension by adding extension info
                        table_module = importlib.import_module(
                            f"extensions.{extension_name}.{ext_module}"
                        )
                        logging.info(f"Imported extension model: {ext_module}")

                        # Tag tables from this extension for filtering in migrations
                        for name, obj in vars(table_module).items():
                            if hasattr(obj, "__tablename__") and hasattr(
                                obj, "__table__"
                            ):
                                if not hasattr(obj.__table__, "info"):
                                    obj.__table__.info = {}
                                obj.__table__.info["extension"] = extension_name
                                logging.info(
                                    f"Tagged table {obj.__tablename__} as part of extension {extension_name}"
                                )

                    except ImportError as e:
                        logging.error(
                            f"Failed to import extension model {ext_module}: {e}"
                        )
            except ImportError as e:
                logging.error(f"Failed to import extension {extension_name}: {e}")

    logging.info("Finished importing models")


# Import all models before configuring Alembic
import_all_models()

# Alembic Config object
config = context.config

# Override the SQLAlchemy URL from environment
db_type, db_name, db_url = get_database_info()
config.set_main_option("sqlalchemy.url", db_url)
logging.info(f"Set sqlalchemy.url in Alembic config to: {db_url}")

# Check for extension-specific version table
extension_name = env("ALEMBIC_EXTENSION")
if extension_name:
    version_table = f"alembic_version_{extension_name}"
    logging.info(f"Using extension-specific version table: {version_table}")
    config.set_main_option("version_table", version_table)

# Also check for direct DATABASE_URL override
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

# Set up Python logging from config
if config.config_file_name:
    fileConfig(config.config_file_name)

# Set the MetaData object for migrations
target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """
    Filter tables based on the current migration context (core or extension)

    This function determines whether a database object should be included
    in the autogeneration process based on ownership.
    """
    if type_ == "table":
        # Get the current extension being processed (if any)
        extension_name = env("ALEMBIC_EXTENSION")

        if extension_name:
            # In extension context, only include tables from this extension
            # Check if the table belongs to this extension based on the info attribute
            should_include = False

            # Look for table info with extension tag
            for table in Base.metadata.tables.values():
                if (
                    hasattr(table, "info")
                    and table.info.get("extension") == extension_name
                ):
                    if table.name == name:
                        should_include = True
                        logging.debug(
                            f"Including table {name} for extension {extension_name} (info match)"
                        )
                        break

            # Alternative detection method based on naming convention
            if not should_include and (
                name.startswith(f"{extension_name}_")
                or name.startswith(f"ext_{extension_name}_")
            ):
                should_include = True
                logging.debug(
                    f"Including table {name} for extension {extension_name} (name prefix match)"
                )

            if not should_include:
                logging.debug(
                    f"Excluding table {name} - not part of extension {extension_name}"
                )

            return should_include
        else:
            # In core context, exclude tables from extensions
            for table in Base.metadata.tables.values():
                if hasattr(table, "info") and "extension" in table.info:
                    if table.name == name:
                        logging.debug(
                            f"Excluding table {name} - belongs to extension {table.info['extension']} (info)"
                        )
                        return False

            # Check for naming convention based exclusion
            extensions_dir = Path(paths["src_dir"]) / "extensions"
            if extensions_dir.exists():
                for module_dir in extensions_dir.glob("*"):
                    if not module_dir.is_dir():
                        continue

                    ext_name = module_dir.name
                    if name.startswith(f"{ext_name}_") or name.startswith(
                        f"ext_{ext_name}_"
                    ):
                        logging.debug(
                            f"Excluding table {name} - belongs to extension {ext_name} (name prefix)"
                        )
                        return False

            logging.debug(f"Including table {name} - part of core")
            return True

    return True


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    logging.info(f"Running offline migrations with URL: {url}")

    # Get the current extension being processed (if any)
    extension_name = env("ALEMBIC_EXTENSION")
    if extension_name:
        version_table = f"alembic_version_{extension_name}"
    else:
        version_table = "alembic_version"

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        version_table=version_table,
    )

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

    # Get the current extension being processed (if any)
    extension_name = env("ALEMBIC_EXTENSION")
    if extension_name:
        version_table = f"alembic_version_{extension_name}"
    else:
        version_table = "alembic_version"

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            version_table=version_table,
            render_as_batch=True,  # Helps with SQLite "table already exists" errors
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
