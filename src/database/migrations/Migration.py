#!/usr/bin/env python
"""
Unified database migration management tool for core and extension migrations.
Handles initialization, creation, applying, and management of migrations.
"""

# TODO alembic.ini and env.py not cleaned up in extensions after migrating on server start.
# TODO extensions that extend existing tables appear to try to completely recreate the table (ai_agents provider_instances)

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import inspect

# Template content for script.py.mako
SCRIPT_PY_MAKO_TEMPLATE = """\
\"\"\"${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

\"\"\"
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    \"\"\"Upgrade schema.\"\"\"
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    \"\"\"Downgrade schema.\"\"\"
    ${downgrades if downgrades else "pass"}
"""

# Template content for env.py to handle duplicate table exclusion
ENV_PY_TEMPLATE = """from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy import inspect

from alembic import context

import os
import sys
import logging
from pathlib import Path

# Get the current file's directory
current_file_dir = Path(__file__).resolve().parent

# Add the src directory to the Python path to allow importing modules
src_dir = str(current_file_dir.parent.parent.parent)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import the Base class for database models
from database.Base import Base

# This is the Alembic Config object, which provides
# access to the values within the .ini file
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get the extension name from environment variable if this is an extension migration
extension_name = os.environ.get('ALEMBIC_EXTENSION')

# Set a specific version table for this extension
if extension_name:
    version_table = f"alembic_version_{extension_name}"
    config.set_main_option("version_table", version_table)
    print(f"Using extension-specific version table: {version_table}")

# Import all models from the extension if this is an extension migration
if extension_name:
    try:
        extension_module = __import__(f'extensions.{extension_name}', fromlist=['*'])
        # Find and import all DB_*.py modules in the extension
        # Handle case where extension_module.__file__ might be None
        if hasattr(extension_module, '__file__') and extension_module.__file__ is not None:
            extension_dir = Path(extension_module.__file__).parent
            db_files = list(extension_dir.glob('DB_*.py'))
            if not db_files:
                print(f"Warning: No DB_*.py files found in {extension_dir} for extension {extension_name}")
                # No need to proceed with migrations if there are no models
                sys.exit(0)
            
            for db_file in db_files:
                module_name = db_file.stem
                try:
                    __import__(f'extensions.{extension_name}.{module_name}', fromlist=['*'])
                except ImportError as e:
                    print(f"Warning: Could not import DB model {module_name} for {extension_name}: {e}")
        else:
            # Fallback: try to find extension directory in a different way
            print(f"Note: extension_module.__file__ is None for {extension_name}, using fallback path")
            extensions_dir = Path(src_dir) / 'extensions'
            extension_dir = extensions_dir / extension_name
            if extension_dir.exists():
                db_files = list(extension_dir.glob('DB_*.py'))
                if not db_files:
                    print(f"Warning: No DB_*.py files found in {extension_dir} for extension {extension_name}")
                    # No need to proceed with migrations if there are no models
                    sys.exit(0)
                
                for db_file in db_files:
                    module_name = db_file.stem
                    try:
                        __import__(f'extensions.{extension_name}.{module_name}', fromlist=['*'])
                    except ImportError as e:
                        print(f"Warning: Could not import DB model {module_name} for {extension_name}: {e}")
            else:
                print(f"Warning: Could not locate extension directory for {extension_name}")
                sys.exit(0)
    except ImportError as e:
        print(f"Warning: Could not import extension models for {extension_name}: {e}")
        print(f"Skipping migrations for extension {extension_name}")
        sys.exit(0)

# Get metadata from Base
target_metadata = Base.metadata

def include_object(object, name, type_, reflected, compare_to):
    \"\"\"
    Decide whether to include an object in the autogenerate process.
    \"\"\"
    # If we're working with an extension, check if this object already exists in the main schema
    if extension_name and type_ == 'table' and reflected:
        print(f"Excluding table {name} from {extension_name} migration as it already exists")
        return False
    
    return True

def run_migrations_offline() -> None:
    \"\"\"Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    \"\"\"
    url = config.get_main_option("sqlalchemy.url")
    
    # Get version_table from config - this ensures extension migrations use their own version table
    version_table = config.get_main_option("version_table", "alembic_version")
    
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


def run_migrations_online() -> None:
    \"\"\"Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    \"\"\"
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Get version_table from config - this ensures extension migrations use their own version table
    version_table = config.get_main_option("version_table", "alembic_version")
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            include_object=include_object,
            version_table=version_table,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
"""

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def normalize_path(path):
    """Normalize a path to avoid duplicated segments like /path/src/src/..."""
    path_str = str(path)
    components = path_str.split(os.sep)

    result = []
    for i, comp in enumerate(components):
        if not comp:
            continue
        if i > 0 and comp == components[i - 1]:
            continue
        result.append(comp)

    normalized = os.sep.join(result)
    if path_str.startswith(os.sep) and not normalized.startswith(os.sep):
        normalized = os.sep + normalized

    return normalized


def setup_python_path():
    """Setup the Python path to allow importing from the project"""
    current_file_path = Path(__file__).resolve()
    migrations_dir = current_file_path.parent
    database_dir = migrations_dir.parent
    src_dir = database_dir.parent
    root_dir = src_dir.parent

    src_dir_norm = normalize_path(src_dir)
    root_dir_norm = normalize_path(root_dir)

    logging.debug(f"Normalized paths: src={src_dir_norm}, root={root_dir_norm}")

    if root_dir_norm not in sys.path:
        sys.path.insert(0, root_dir_norm)
    if src_dir_norm not in sys.path:
        sys.path.insert(0, src_dir_norm)

    return {
        "migrations_dir": migrations_dir,
        "database_dir": database_dir,
        "src_dir": Path(src_dir_norm),
        "root_dir": Path(root_dir_norm),
    }


paths = setup_python_path()

from lib.Environment import env


def parse_csv_env_var(env_var_name, default=None):
    """Parse a comma-separated environment variable into a list of strings."""
    value = env(env_var_name)
    if not value:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


def get_configured_extensions():
    """Get the list of configured extensions from the environment variable."""
    extension_list = parse_csv_env_var("APP_EXTENSIONS")
    if not extension_list:
        logging.info(
            "No APP_EXTENSIONS environment variable set. No extensions will be processed."
        )
    else:
        logging.info(f"Using extensions from APP_EXTENSIONS: {extension_list}")
    return extension_list


def load_extension_config():
    """Load extension configuration from environment variables"""
    extension_list = []
    auto_discover = True

    # First check for override from environment
    override_extension_list = env("OVERRIDE_EXTENSION_LIST")
    if override_extension_list:
        try:
            extension_list = json.loads(override_extension_list)
            logging.info(f"Using override extension list: {extension_list}")
            auto_discover = False
            return extension_list, auto_discover
        except Exception as e:
            logging.error(f"Error parsing override extension list: {e}")

    # Get extensions from APP_EXTENSIONS environment variable
    extension_list = get_configured_extensions()
    if not extension_list:
        logging.warning(
            "APP_EXTENSIONS environment variable not set, no extensions will be processed"
        )

    return extension_list, auto_discover


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

    if db_type == "sqlite":
        db_url = f"sqlite:///{db_name}.db"
    elif db_type == "postgresql":
        db_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?sslmode={db_ssl}"
    else:
        logging.warning(f"Unsupported database type: {db_type}, falling back to SQLite")
        db_url = f"sqlite:///{db_name}.db"

    logging.info(f"Constructed database URL: {db_url}")
    return db_type, db_name, db_url


def find_alembic_ini():
    """Find the alembic.ini file in various possible locations"""
    potential_paths = [
        paths["root_dir"] / "alembic.ini",
        Path("alembic.ini"),
        Path(f"/{env('APP_NAME').lower()}/alembic.ini"),
        Path("../alembic.ini"),
    ]

    for path in potential_paths:
        if path.exists():
            logging.debug(f"Found alembic.ini at {path}")
            return path

    logging.error("Could not find alembic.ini in any standard location")
    return paths["root_dir"] / "alembic.ini"


def update_alembic_ini_database_url(alembic_ini_path):
    """Update the alembic.ini file with the correct database URL based on environment variables"""
    try:
        if not alembic_ini_path.exists():
            logging.error(
                f"Cannot update non-existent alembic.ini at {alembic_ini_path}"
            )
            return False

        db_type, db_name, db_url = get_database_info()
        logging.info(f"Updating alembic.ini at {alembic_ini_path} with URL: {db_url}")

        with open(alembic_ini_path, "r") as f:
            content = f.readlines()

        updated = False
        for i, line in enumerate(content):
            if line.strip().startswith("sqlalchemy.url = "):
                content[i] = f"sqlalchemy.url = {db_url}\n"
                updated = True
                break

        if not updated:
            for i, line in enumerate(content):
                if line.strip() == "[alembic]":
                    content.insert(i + 1, f"sqlalchemy.url = {db_url}\n")
                    updated = True
                    break

        with open(alembic_ini_path, "w") as f:
            f.writelines(content)

        logging.info(f"Successfully updated alembic.ini with database URL: {db_url}")
        return True
    except Exception as e:
        logging.error(f"Error updating alembic.ini: {e}")
        return False


def cleanup_file(file_path, message=None):
    """Safely remove a file if it exists with optional logging."""
    if file_path and file_path.exists():
        try:
            file_path.unlink()
            if message:
                logging.info(f"{message}: {file_path}")
            else:
                logging.debug(f"Cleaned up file: {file_path}")
            return True
        except Exception as e:
            logging.warning(f"Could not clean up file {file_path}: {e}")
    return False


def create_temp_file(content, suffix=None, delete=False):
    """Create a temporary file with given content and return its path."""
    temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=delete)
    temp_file.write(content.strip().encode("utf-8"))
    temp_file.close()
    return Path(temp_file.name)


def write_file(file_path, content):
    """Write content to a file, creating parent directories if needed."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        logging.error(f"Error writing to file {file_path}: {e}")
        return False


def get_common_env_vars(extension_name=None):
    """Get common environment variables for subprocess execution."""
    env_vars = {}

    # Set PYTHONPATH to ensure imports work correctly
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    env_vars["PYTHONPATH"] = (
        f"{paths['root_dir']}{os.pathsep}{paths['src_dir']}{os.pathsep}{current_pythonpath}"
    )

    if extension_name:
        env_vars["ALEMBIC_EXTENSION"] = extension_name

    return env_vars


def run_subprocess(cmd, env_vars=None, capture_output=False):
    """Run a subprocess command with given environment variables."""
    try:
        # Prepare environment
        combined_env = dict(os.environ)
        if env_vars:
            combined_env.update(env_vars)

        # Log the command
        logging.info(f"Running command: {' '.join(cmd)}")

        # Always capture output for proper error handling
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=combined_env,
            check=False,  # Don't raise exception on non-zero exit
        )

        # Handle result
        if result.returncode == 0:
            logging.info(f"Command {' '.join(cmd)} succeeded")
            # Print stdout if there's any useful output and we want to see it
            if capture_output and result.stdout and len(result.stdout.strip()) > 0:
                logging.info(f"Command output:\n{result.stdout}")
            return result, True
        else:
            # Log the error in detail
            logging.error(
                f"Command {' '.join(cmd)} failed with return code {result.returncode}"
            )

            # Always log stderr for debugging when there's an error
            if result.stderr and len(result.stderr.strip()) > 0:
                logging.error(f"Error output:\n{result.stderr}")

            # Also log stdout if there's anything useful there
            if result.stdout and len(result.stdout.strip()) > 0:
                logging.info(f"Command output before failure:\n{result.stdout}")

            return result, False

    except Exception as e:
        logging.error(f"Error running command {' '.join(cmd)}: {str(e)}")
        import traceback

        logging.error(traceback.format_exc())
        return None, False


def run_alembic_command(command, *args, extra_env=None, extension=None):
    """Run an alembic command and return the result"""
    alembic_ini_path = find_alembic_ini()
    update_alembic_ini_database_url(alembic_ini_path)

    alembic_cmd = ["alembic"]

    if not Path("alembic.ini").exists():
        alembic_cmd.extend(["-c", str(alembic_ini_path)])

    alembic_cmd.append(command)

    if args:
        alembic_cmd.extend(args)

    # Initialize script_template_dst here so it's in scope for the finally block
    script_template_dst = None

    try:
        # Get common environment variables
        env_vars = get_common_env_vars(extension)

        if extra_env:
            env_vars.update(extra_env)

        # Handle temporary script.py.mako for core revisions
        if command == "revision" and not extension:
            # Create script.py.mako directly in the core migrations dir
            script_template_dst = paths["migrations_dir"] / "script.py.mako"
            if not write_file(script_template_dst, SCRIPT_PY_MAKO_TEMPLATE):
                return False  # Cannot create revision without template
            logging.info(
                f"Temporarily created core script.py.mako at {script_template_dst}"
            )

        # Run the command
        _, success = run_subprocess(alembic_cmd, env_vars)
        return success

    except Exception as e:
        logging.error(f"Error running Alembic command: {str(e)}")
        import traceback

        logging.error(traceback.format_exc())
        return False
    finally:
        # Ensure temporary core script template is cleaned up if created
        if script_template_dst and script_template_dst.exists():
            cleanup_file(
                script_template_dst, "Cleaned up temporary core script.py.mako"
            )


def find_extension_migrations_dirs():
    """Find all migration directories for configured extensions."""
    extension_migrations = []
    configured_extensions = get_configured_extensions()

    extensions_base_dir = paths["src_dir"] / "extensions"
    if not extensions_base_dir.exists():
        logging.warning(f"Extensions directory not found at {extensions_base_dir}")
        return extension_migrations

    for extension_name in configured_extensions:
        ext_dir = extensions_base_dir / extension_name
        if not ext_dir.is_dir():
            logging.warning(f"Configured extension directory not found: {ext_dir}")
            continue

        migrations_dir = ext_dir / "migrations"
        if migrations_dir.exists() and migrations_dir.is_dir():
            versions_dir = migrations_dir / "versions"
            if versions_dir.exists() and versions_dir.is_dir():
                extension_migrations.append((extension_name, versions_dir))
                logging.info(
                    f"Found migrations dir for configured extension '{extension_name}': {versions_dir}"
                )
            else:
                # If migrations dir exists but versions doesn't, still consider it for init/create
                logging.info(
                    f"Found migrations dir for '{extension_name}' but no versions dir: {migrations_dir}"
                )
                # We might still want to return this path for commands like 'init' or 'create'
                # Let's return the migrations_dir itself if versions doesn't exist, handle later
                extension_migrations.append(
                    (extension_name, migrations_dir)
                )  # Indicate potential target
        else:
            logging.info(
                f"No migrations directory found for configured extension '{extension_name}' at {migrations_dir}"
            )

    logging.info(
        f"Found {len(extension_migrations)} migration directories for configured extensions."
    )
    return extension_migrations


def ensure_versions_directory():
    """Ensure the versions directory exists"""
    try:
        versions_dir = paths["migrations_dir"] / "versions"

        if not versions_dir.exists():
            logging.info(f"Creating versions directory at {versions_dir}")
            versions_dir.mkdir(parents=True, exist_ok=True)

        return True
    except Exception as e:
        logging.error(f"Error creating versions directory: {str(e)}")
        return False


def ensure_extension_versions_directory(extension_name):
    """Ensure the extension migrations directory and versions directory exist"""
    extension_dir = paths["src_dir"] / "extensions" / extension_name

    if not extension_dir.exists():
        logging.error(f"Extension directory not found at {extension_dir}")
        return False, None

    migrations_dir = extension_dir / "migrations"
    if not migrations_dir.exists():
        migrations_dir.mkdir()
        logging.info(f"Created migrations directory at {migrations_dir}")

    versions_dir = migrations_dir / "versions"
    if not versions_dir.exists():
        versions_dir.mkdir()
        logging.info(f"Created versions directory at {versions_dir}")

    env_file = migrations_dir / "env.py"
    if not env_file.exists():
        try:
            # Create a custom env.py with duplicate table detection
            write_file(env_file, ENV_PY_TEMPLATE)
            logging.info(f"Created env.py with duplicate table detection at {env_file}")
        except Exception as e:
            logging.error(f"Error creating env.py: {e}")
            return False, versions_dir

    # Create alembic.ini if it doesn't exist
    alembic_ini = migrations_dir / "alembic.ini"
    if not alembic_ini.exists():
        db_type, db_name, db_url = get_database_info()

        alembic_content = f"""
# Extension-specific alembic.ini for {extension_name}
[alembic]
script_location = {migrations_dir}
file_template = %%(rev)s_%%(slug)s
sqlalchemy.url = {db_url}
version_table = alembic_version_{extension_name}
branch_label = ext_{extension_name}

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %%(levelname)-5.5s [%%(name)s] %%(message)s
datefmt = %%H:%%M:%%S
"""
        if not write_file(alembic_ini, alembic_content):
            logging.error(f"Error creating alembic.ini at {alembic_ini}")
            return False, versions_dir

        logging.info(f"Created alembic.ini at {alembic_ini}")

    logging.info(f"Extension migration structure created for {extension_name}")
    return True, versions_dir


def create_extension_alembic_ini(extension_name, extension_versions_dir):
    """Create a completely customized alembic.ini for an extension"""
    ext_migrations_dir = extension_versions_dir.parent
    db_type, db_name, db_url = get_database_info()

    config_content = f"""
# Extension-specific alembic.ini for {extension_name}
[alembic]
script_location = {ext_migrations_dir}
file_template = %%(rev)s_%%(slug)s
sqlalchemy.url = {db_url}
# Remove version_locations parameter to avoid looking for migrations in other locations
version_table = alembic_version_{extension_name}
branch_label = ext_{extension_name}

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %%(levelname)-5.5s [%%(name)s] %%(message)s
datefmt = %%H:%%M:%%S
"""

    temp_file_path = create_temp_file(config_content, suffix=".ini")
    logging.info(
        f"Created dedicated extension alembic.ini at {temp_file_path} for {extension_name}"
    )
    return temp_file_path


def run_extension_migration(extension_name, command, target="head"):
    """Run an alembic migration command for a specific extension"""
    success, versions_dir = ensure_extension_versions_directory(extension_name)
    if not success:
        logging.error(f"Failed to ensure migration directory for {extension_name}")
        return False

    temp_ini = create_extension_alembic_ini(extension_name, versions_dir)
    env_py_path = versions_dir.parent / "env.py"

    # For extension migrations, always prefix the branch name to the target
    # Only for upgrade/downgrade commands that specify a target
    branch_label = f"ext_{extension_name}"
    if command in ["upgrade", "downgrade"]:
        if target == "head":
            # Use branch label for head target
            target_arg = f"{branch_label}@{target}"
        elif target == "base":
            # For base target, just use base
            target_arg = "base"
        else:
            # For specific revisions, prefix with branch label
            target_arg = f"{branch_label}@{target}"
    else:
        target_arg = ""

    alembic_cmd = ["alembic", "-c", str(temp_ini), command]
    if target_arg:
        alembic_cmd.append(target_arg)

    logging.info(
        f"Running {command} for extension {extension_name}: {' '.join(alembic_cmd)}"
    )

    try:
        # Get common environment variables
        env_vars = get_common_env_vars(extension_name)

        # Run the command
        result, success = run_subprocess(alembic_cmd, env_vars, capture_output=True)

        # Check for specific error about not finding a revision
        if (
            not success
            and result
            and result.stderr
            and "Can't locate revision" in result.stderr
        ):
            logging.warning(
                f"Extension {extension_name} has a revision reference issue. Attempting to fix by regenerating migrations."
            )

            # If there was a revision issue and we're trying to upgrade, attempt to regenerate migrations
            if command == "upgrade":
                # Attempt to regenerate the migration for this extension
                regenerate_success = regenerate_migrations(
                    extension_name=extension_name,
                    message="Regenerated initial migration",
                )
                if regenerate_success:
                    logging.info(
                        f"Successfully regenerated migrations for extension {extension_name}, retrying upgrade..."
                    )
                    # After regeneration, try to run the upgrade command again
                    _, success = run_subprocess(alembic_cmd, env_vars)
                else:
                    logging.error(
                        f"Failed to regenerate migrations for extension {extension_name}"
                    )

        # Clean up temporary files
        cleanup_file(temp_ini, "Cleaned up temporary alembic.ini")
        cleanup_file(env_py_path, "Cleaned up temporary env.py")

        # Run the complete cleanup function
        cleanup_extension_files()

        if success:
            logging.info(
                f"Migration {command} successful for extension {extension_name}"
            )
            return True
        else:
            logging.error(f"Migration {command} failed for extension {extension_name}")
            return False
    except Exception as e:
        logging.error(f"Error running migration for extension {extension_name}: {e}")
        # Clean up temporary files
        cleanup_file(temp_ini, "Cleaned up temporary alembic.ini after error")
        cleanup_file(env_py_path, "Cleaned up temporary env.py after error")

        # Run the complete cleanup function
        cleanup_extension_files()
        return False


def create_extension_migration(extension_name, message, auto=True):
    """Create a migration for a specific extension"""
    script_template_dst = None
    temp_ini = None
    env_py_dst = None
    try:
        success, versions_dir = ensure_extension_versions_directory(extension_name)
        if not success:
            return False

        migrations_dir = versions_dir.parent

        # Create script.py.mako in the extension's migrations directory
        script_template_dst = migrations_dir / "script.py.mako"
        if not write_file(script_template_dst, SCRIPT_PY_MAKO_TEMPLATE):
            logging.error("Error creating temporary script.py.mako")
            return False
        logging.info(f"Temporarily created script.py.mako at {script_template_dst}")

        # A more reliable check for first migration - looks for actual migration files
        is_first_migration = True
        if versions_dir.exists():
            migration_files = list(versions_dir.glob("*.py"))
            if any(f for f in migration_files if f.name != "__init__.py"):
                is_first_migration = False
                logging.info(
                    f"Found existing migrations for {extension_name} at {versions_dir}"
                )

        temp_ini = create_extension_alembic_ini(extension_name, versions_dir)

        # Track env.py location
        env_py_dst = migrations_dir / "env.py"

        # Prepare revision command
        alembic_cmd = ["alembic", "-c", str(temp_ini), "revision"]
        if auto:
            alembic_cmd.append("--autogenerate")
        alembic_cmd.extend(["-m", message])

        if is_first_migration:
            logging.info(
                f"Detected first migration for extension {extension_name}, adding branch label."
            )
            # For first migration, explicitly set head to base and apply branch label
            alembic_cmd.extend(
                ["--head", "base", "--branch-label", f"ext_{extension_name}"]
            )

        logging.info(
            f"Creating revision for extension {extension_name}: {' '.join(alembic_cmd)}"
        )

        # Get common environment variables
        env_vars = get_common_env_vars(extension_name)

        # Run the revision command
        _, success = run_subprocess(alembic_cmd, env_vars)

        # Clean up all temporary files
        cleanup_file(temp_ini, "Cleaned up temporary alembic.ini")
        cleanup_file(script_template_dst, "Cleaned up temporary script.py.mako")
        cleanup_file(env_py_dst, "Cleaned up temporary env.py")

        # Also run the general cleanup to catch any missed files
        cleanup_extension_files()

        if success:
            logging.info(
                f"Revision created successfully for extension {extension_name}"
            )
            return True
        else:
            logging.error(f"Revision creation failed for extension {extension_name}")
            return False

    except Exception as e:
        logging.error(f"Error creating extension migration: {str(e)}")
        import traceback

        logging.error(traceback.format_exc())

        # Clean up all temporary files
        cleanup_file(temp_ini, "Cleaned up temporary alembic.ini after outer error")
        cleanup_file(
            script_template_dst, "Cleaned up temporary script.py.mako after outer error"
        )
        cleanup_file(env_py_dst, "Cleaned up temporary env.py after outer error")

        # Also run the general cleanup to catch any missed files
        cleanup_extension_files()
        return False


def regenerate_migrations(extension_name=None, all_extensions=False, message=None):
    """Delete existing migrations and regenerate from scratch"""
    regenerate_message = message or "initial schema"

    if all_extensions:
        success = regenerate_migrations(message=regenerate_message)
        if not success:
            return False

        extensions, _ = load_extension_config()
        found_ext_names = {name for name, _ in find_extension_migrations_dirs()}
        all_relevant_extensions = set(extensions) | found_ext_names

        for ext_name in all_relevant_extensions:
            # Check if extension has DB models before regenerating
            extension_dir = paths["src_dir"] / "extensions" / ext_name
            has_models = any(extension_dir.glob("DB_*.py"))

            if not has_models:
                logging.info(
                    f"Skipping regeneration for extension {ext_name}: No DB_*.py files found."
                )
                continue

            # Regenerate each extension
            success = regenerate_migrations(
                extension_name=ext_name, message=regenerate_message
            )
            if not success:
                logging.error(
                    f"Failed to regenerate migrations for extension {ext_name}"
                )
                return False

        # Clean up any temporary files after all regenerations
        cleanup_extension_files()
        return True

    if extension_name:
        extension_dir = paths["src_dir"] / "extensions" / extension_name
        migrations_dir = extension_dir / "migrations"
        versions_dir = migrations_dir / "versions"
    else:
        migrations_dir = paths["migrations_dir"]
        versions_dir = migrations_dir / "versions"

    if versions_dir.exists():
        logging.info(f"Deleting existing migrations in {versions_dir}")
        for file in versions_dir.glob("*.py"):
            if file.name != "__init__.py":
                try:
                    file.unlink()
                    logging.info(f"Deleted {file}")
                except Exception as e:
                    logging.error(f"Failed to delete {file}: {e}")

    # Try to remove version tracking from database
    try:
        if extension_name:
            # For extension, use the extension-specific version table
            version_table = f"alembic_version_{extension_name}"
            db_type, db_name, db_url = get_database_info()

            from sqlalchemy import create_engine, text

            engine = create_engine(db_url)

            with engine.connect() as connection:
                # Check if the version table exists before trying to drop it
                inspector = inspect(engine)
                if version_table in inspector.get_table_names():
                    logging.info(f"Dropping extension version table {version_table}")
                    connection.execute(text(f"DROP TABLE IF EXISTS {version_table}"))
                    connection.commit()

            # Now try to downgrade to base (might fail if table was already gone)
            try:
                run_extension_migration(extension_name, "downgrade", "base")
            except Exception as e:
                logging.warning(f"Could not downgrade {extension_name} to base: {e}")
        else:
            # For core migrations, just use the standard downgrade command
            try:
                run_alembic_command("downgrade", "base")
            except Exception as e:
                logging.warning(f"Could not downgrade core to base: {e}")
    except Exception as e:
        logging.warning(f"Error cleaning up version tables: {e}")

    if extension_name:
        success = create_extension_migration(
            extension_name, regenerate_message, auto=True
        )
    else:
        alembic_cmd = ["revision", "--autogenerate", "-m", regenerate_message]
        success = run_alembic_command(*alembic_cmd)

    # Clean up any temporary files after regeneration
    if extension_name:
        cleanup_extension_files()

    return success


def create_extension_directory(extension_name):
    """Create the extension directory structure"""
    extension_dir = paths["src_dir"] / "extensions" / extension_name

    if extension_dir.exists():
        logging.info(f"Extension directory {extension_dir} already exists")
        return extension_dir

    extension_dir.mkdir(exist_ok=True, parents=True)

    with open(extension_dir / "__init__.py", "w") as f:
        f.write(f'"""Extension: {extension_name}"""\n')

    logging.info(f"Created extension directory: {extension_dir}")
    return extension_dir


def create_db_file(extension_dir, extension_name):
    """Create a sample DB_*.py file with table definitions"""
    db_file_path = extension_dir / f"DB_{extension_name.capitalize()}.py"

    if db_file_path.exists():
        logging.info(f"DB file {db_file_path} already exists, not overwriting")
        return db_file_path

    with open(db_file_path, "w") as f:
        f.write(
            f'''"""
Database models for the {extension_name} extension.
"""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database.Base import Base
from database.Mixins import BaseMixin


class {extension_name.capitalize()}Item(Base, BaseMixin):
    """Example item model for the {extension_name} extension."""
    __tablename__ = "{extension_name}_items"
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    __table_args__ = {{"extend_existing": True}}
'''
        )

    logging.info(f"Created DB file: {db_file_path}")
    return db_file_path


def update_extension_config(extension_name):
    """Update the extension configuration - DEPRECATED

    This function is kept for backward compatibility but doesn't do anything.
    Extensions are now configured via the APP_EXTENSIONS environment variable.
    """
    # Function is kept for backward compatibility
    logging.info(
        f"NOTICE: Extension '{extension_name}' needs to be added to APP_EXTENSIONS environment variable."
    )
    logging.info(
        "Please update your environment variables to include this extension for migrations to work correctly."
    )
    return True


def create_extension(extension_name, skip_model=False, skip_migrate=False):
    """Create a new extension with migrations"""
    # Ensure the extension is listed in the environment variable for subsequent operations
    configured_extensions = get_configured_extensions()
    if extension_name not in configured_extensions:
        logging.warning(
            f"Extension '{extension_name}' not found in APP_EXTENSIONS environment variable."
        )
        logging.warning(
            "Please add it to APP_EXTENSIONS for migrations to work correctly."
        )
        # Proceed with creation, but warn the user.

    extension_dir = create_extension_directory(extension_name)

    if not skip_model:
        create_db_file(extension_dir, extension_name)

    if not skip_migrate:
        success, versions_dir = ensure_extension_versions_directory(extension_name)
        if success:
            if create_extension_migration(
                extension_name, f"Initial {extension_name} migration", auto=True
            ):
                run_extension_migration(extension_name, "upgrade", "head")

    # Make sure to clean up any temporary files
    cleanup_extension_files()

    logging.info(f"Extension {extension_name} setup complete!")
    return True


def debug_environment():
    """Show debug information about the environment"""
    print("\n=== ENVIRONMENT VARIABLES ===")
    for key, value in sorted(os.environ.items()):
        if any(x in key.lower() for x in ["database", "alembic", "sql", "db_"]):
            print(f"{key}={value}")

    print("\n=== DATABASE CONFIGURATION ===")
    db_type, db_name, db_url = get_database_info()
    print(f"DATABASE_TYPE: {db_type}")
    print(f"DATABASE_NAME: {db_name}")
    print(f"DATABASE_URL: {db_url}")

    print("\n=== PATHS ===")
    for key, value in paths.items():
        print(f"{key}: {value}")

    print("\n=== ALEMBIC CONFIG ===")
    alembic_ini = find_alembic_ini()
    print(f"alembic.ini: {alembic_ini}")
    if alembic_ini.exists():
        with open(alembic_ini, "r") as f:
            for line in f:
                if any(
                    x in line.lower() for x in ["sqlalchemy.url", "database", "version"]
                ):
                    print(f"  {line.strip()}")

    print("\n=== EXTENSIONS ===")
    configured_extensions = get_configured_extensions()
    print(f"Configured extensions (from APP_EXTENSIONS): {configured_extensions}")

    extension_dirs = find_extension_migrations_dirs()
    if extension_dirs:
        print("Found extension migrations:")
        for name, path in extension_dirs:
            print(f"  {name}: {path}")
    else:
        print("No extension migrations found")


def cleanup_extension_files():
    """Clean up temporary files from extension directories"""
    extensions_dir = paths["src_dir"] / "extensions"
    if not extensions_dir.exists():
        return

    files_to_clean = ["alembic.ini", "env.py", "script.py.mako"]

    for ext_dir in extensions_dir.iterdir():
        if not ext_dir.is_dir():
            continue

        migrations_dir = ext_dir / "migrations"
        if not migrations_dir.exists():
            continue

        for filename in files_to_clean:
            cleanup_file(migrations_dir / filename)

        # Also check if there's a script.py.mako at the versions directory level
        versions_dir = migrations_dir / "versions"
        if versions_dir.exists():
            for filename in files_to_clean:
                cleanup_file(versions_dir / filename)

    logging.debug("Extension file cleanup completed")


def run_all_migrations(command, target="head"):
    """Run migrations for core and all extensions"""
    db_type, db_name, db_url = get_database_info()
    logging.info(f"Database environment: TYPE={db_type}, NAME={db_name}")

    logging.info(f"Running {command} for core migrations")
    core_result = run_alembic_command(command, target)

    if not core_result:
        logging.error(f"Core migrations {command} failed")
        return False

    extension_migrations = []
    configured_extensions = get_configured_extensions()

    # First, check which extensions actually have DB models
    for ext_name in configured_extensions:
        extension_dir = paths["src_dir"] / "extensions" / ext_name
        db_model_files = list(extension_dir.glob("DB_*.py"))

        if not db_model_files:
            logging.info(f"Skipping extension '{ext_name}' - no DB_*.py files found")
            continue

        logging.info(
            f"Found DB models for extension '{ext_name}': {[f.name for f in db_model_files]}"
        )

        # Check for migrations directory
        migrations_dir = extension_dir / "migrations"
        versions_dir = migrations_dir / "versions"

        if versions_dir.exists():
            extension_migrations.append((ext_name, versions_dir))
        else:
            # Directory structure needs to be created
            success, dir_path = ensure_extension_versions_directory(ext_name)
            if success:
                extension_migrations.append((ext_name, dir_path))

    failed_extensions = []
    for extension_name, versions_dir in extension_migrations:
        logging.info(f"Running migrations for extension: {extension_name}")

        # Check if the versions directory actually exists and has migration files
        needs_initial_migration = False
        if not versions_dir.exists():
            needs_initial_migration = True
            logging.info(
                f"Versions directory does not exist for {extension_name}, will create first migration."
            )
        elif not any(f for f in versions_dir.glob("*.py") if f.name != "__init__.py"):
            needs_initial_migration = True
            logging.info(
                f"No migration files found for {extension_name}, will create first migration."
            )

        # If we need to create the first migration for this extension
        if needs_initial_migration:
            if command == "upgrade":
                # Check if extension has DB models before creating migration (double-check)
                extension_dir = paths["src_dir"] / "extensions" / extension_name
                db_model_files = list(extension_dir.glob("DB_*.py"))

                if db_model_files:
                    logging.info(
                        f"Creating initial migration for extension {extension_name}"
                    )
                    created = create_extension_migration(
                        extension_name, "Initial migration", auto=True
                    )
                    if not created:
                        logging.warning(
                            f"Could not automatically create initial migration for {extension_name}. Skipping upgrade."
                        )
                        failed_extensions.append(extension_name)
                        continue
                else:
                    logging.info(
                        f"Skipping migration for extension {extension_name} as no DB_*.py files found."
                    )
                    continue
            else:
                # For other commands like downgrade/history, skip if no versions exist
                logging.info(
                    f"Skipping '{command}' for extension {extension_name} as no migrations exist."
                )
                continue

        # Re-check if versions dir exists after potential creation attempt
        if not versions_dir.exists():
            logging.warning(
                f"Versions directory {versions_dir} still not found for extension {extension_name}, skipping."
            )
            continue

        success = run_extension_migration(extension_name, command, target)
        if not success:
            failed_extensions.append(extension_name)

    if failed_extensions:
        logging.error(
            f"Migration failed for extensions: {', '.join(failed_extensions)}"
        )
        return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Unified database migration tool")
    subparsers = parser.add_subparsers(dest="command", help="Migration command")

    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade the database")
    upgrade_parser.add_argument(
        "--all", action="store_true", help="Run migrations for core and all extensions"
    )
    upgrade_parser.add_argument(
        "--extension", help="Run migrations for a specific extension"
    )
    upgrade_parser.add_argument(
        "--target", default="head", help="Migration target (default: head)"
    )

    downgrade_parser = subparsers.add_parser("downgrade", help="Downgrade the database")
    downgrade_parser.add_argument(
        "--all", action="store_true", help="Run migrations for core and all extensions"
    )
    downgrade_parser.add_argument(
        "--extension", help="Run migrations for a specific extension"
    )
    downgrade_parser.add_argument(
        "--target", default="-1", help="Migration target (default: -1)"
    )

    revision_parser = subparsers.add_parser("revision", help="Create a new revision")
    revision_parser.add_argument(
        "--extension", help="Create a revision for a specific extension"
    )
    revision_parser.add_argument("--message", "-m", help="Revision message")
    revision_parser.add_argument(
        "--no-autogenerate",
        action="store_false",
        dest="autogenerate",
        help="Create an empty migration file without auto-generating content.",
    )
    revision_parser.set_defaults(autogenerate=True)
    revision_parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Delete all existing migrations and regenerate",
    )
    revision_parser.add_argument(
        "--all",
        action="store_true",
        help="With --regenerate: regenerate all extensions after core",
    )

    history_parser = subparsers.add_parser(
        "history", help="Show migration version history"
    )
    history_parser.add_argument(
        "--extension", help="Show history for a specific extension"
    )

    current_parser = subparsers.add_parser(
        "current", help="Show current migration version"
    )
    current_parser.add_argument(
        "--extension", help="Show current version for a specific extension"
    )

    init_parser = subparsers.add_parser(
        "init", help="Initialize migration structure for an extension"
    )
    init_parser.add_argument("extension", help="Extension to initialize")
    init_parser.add_argument(
        "--skip-model", action="store_true", help="Skip creating sample model"
    )
    init_parser.add_argument(
        "--skip-migrate", action="store_true", help="Skip migration creation"
    )

    create_parser = subparsers.add_parser(
        "create", help="Create a new extension with migrations"
    )
    create_parser.add_argument("extension", help="Name of the extension to create")
    create_parser.add_argument(
        "--skip-model", action="store_true", help="Skip creating sample model"
    )
    create_parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help="Skip migration creation and application",
    )

    debug_parser = subparsers.add_parser(
        "debug", help="Show detailed debug information"
    )

    # Add separate regenerate command
    regenerate_parser = subparsers.add_parser(
        "regenerate", help="Delete all existing migrations and regenerate"
    )
    regenerate_parser.add_argument(
        "--extension", help="Regenerate migrations for a specific extension"
    )
    regenerate_parser.add_argument(
        "--all",
        action="store_true",
        help="Regenerate all extensions after core",
    )
    regenerate_parser.add_argument(
        "--message",
        "-m",
        default="initial schema",
        help="Revision message (default: 'initial schema')",
    )

    args = parser.parse_args()

    success = False
    try:
        if args.command in ["upgrade", "downgrade"]:
            if args.all:
                success = run_all_migrations(args.command, args.target)
            elif args.extension:
                success = run_extension_migration(
                    args.extension, args.command, args.target
                )
            else:
                success = run_alembic_command(args.command, args.target)

        elif args.command == "revision":
            if args.regenerate:
                success = regenerate_migrations(
                    extension_name=args.extension,
                    all_extensions=args.all,
                    message=args.message,
                )
            elif args.extension:
                if not args.message:
                    if args.regenerate:
                        args.message = "initial schema"
                    else:
                        print(
                            "Error: --message is required for new non-regenerated revisions"
                        )
                        sys.exit(1)
                success = create_extension_migration(
                    args.extension, args.message, args.autogenerate
                )
            else:
                if not args.message:
                    if args.regenerate:
                        args.message = "initial schema"
                    else:
                        print(
                            "Error: --message is required for new non-regenerated revisions"
                        )
                        sys.exit(1)
                cmd = ["revision"]
                if args.autogenerate:
                    cmd.append("--autogenerate")
                cmd.extend(["-m", args.message])
                success = run_alembic_command(*cmd)

        elif args.command == "history":
            if args.extension:
                success = run_extension_migration(args.extension, "history")
            else:
                success = run_alembic_command("history")

        elif args.command == "current":
            if args.extension:
                success = run_extension_migration(args.extension, "current")
            else:
                success = run_alembic_command("current")

        elif args.command == "init":
            success = create_extension(
                args.extension,
                skip_model=args.skip_model,
                skip_migrate=args.skip_migrate,
            )

        elif args.command == "create":
            success = create_extension(
                args.extension,
                skip_model=args.skip_model,
                skip_migrate=args.skip_migrate,
            )

        elif args.command == "debug":
            debug_environment()
            success = True

        elif args.command == "regenerate":
            success = regenerate_migrations(
                extension_name=args.extension,
                all_extensions=args.all,
                message=args.message,
            )

        else:
            parser.print_help()
            sys.exit(1)

        sys.exit(0 if success else 1)

    finally:
        # Ensure cleanup runs regardless of success/failure
        try:
            cleanup_extension_files()
            logging.debug("Final cleanup of temporary files completed")
        except Exception as e:
            logging.warning(f"Error during final cleanup: {e}")
            # Don't affect exit code for cleanup errors


if __name__ == "__main__":
    main()
