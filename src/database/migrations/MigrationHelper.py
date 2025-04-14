import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def normalize_path(path):
    """
    Normalize a path to avoid duplicated segments like /path/src/src/...

    Args:
        path: Path to normalize (string or Path object)

    Returns:
        Normalized path as string
    """
    # Convert to string if it's a Path object
    path_str = str(path)

    # Split into components
    components = path_str.split(os.sep)

    # Remove empty components and duplicates
    result = []
    for i, comp in enumerate(components):
        if not comp:  # Skip empty components
            continue
        if i > 0 and comp == components[i - 1]:  # Skip duplicated components
            continue
        result.append(comp)

    # Join back into a path
    normalized = os.sep.join(result)
    # Make sure it starts with / if original did
    if path_str.startswith(os.sep) and not normalized.startswith(os.sep):
        normalized = os.sep + normalized

    return normalized


# Setup path for imports
def setup_python_path():
    """
    Setup the Python path to allow importing from the project
    """
    # Get the absolute path of the current file
    current_file_path = Path(__file__).resolve()
    # Get migrations directory (where this file is)
    migrations_dir = current_file_path.parent
    # Get database directory (parent of migrations)
    database_dir = migrations_dir.parent
    # Get src directory (parent of database)
    src_dir = database_dir.parent
    # Get root directory (parent of src)
    root_dir = src_dir.parent

    # Normalize paths to prevent duplication
    src_dir_norm = normalize_path(src_dir)
    root_dir_norm = normalize_path(root_dir)

    # Log the paths for debugging
    logging.debug(
        f"Raw paths: migrations={migrations_dir}, db={database_dir}, src={src_dir}, root={root_dir}"
    )
    logging.debug(f"Normalized paths: src={src_dir_norm}, root={root_dir_norm}")

    # Add to Python path if not already there (use normalized paths)
    if root_dir_norm not in sys.path:
        sys.path.insert(0, root_dir_norm)
    if src_dir_norm not in sys.path:
        sys.path.insert(0, src_dir_norm)

    # Use normalized paths for the return value
    return {
        "migrations_dir": migrations_dir,
        "database_dir": database_dir,
        "src_dir": Path(src_dir_norm),
        "root_dir": Path(root_dir_norm),
    }


# Initialize paths before importing
paths = setup_python_path()

# Now import modules that need the path setup
from lib.Environment import env


def load_extension_config():
    """
    Load extension configuration from JSON file

    Returns:
        tuple: (extension_list, auto_discover)
            - extension_list: List of extension names to use
            - auto_discover: Whether to automatically discover extensions
    """
    # Get the migrations directory (where this file is)
    current_file_path = Path(__file__).resolve()
    migrations_dir = current_file_path.parent
    config_path = migrations_dir / "migration_extensions.json"

    # Default values
    extension_list = []
    auto_discover = True

    # Check for override extension list from environment variable
    override_extension_list = env("OVERRIDE_EXTENSION_LIST")
    if override_extension_list:
        try:
            extension_list = json.loads(override_extension_list)
            logging.info(f"Using override extension list: {extension_list}")
            auto_discover = False
            return extension_list, auto_discover
        except Exception as e:
            logging.error(f"Error parsing override extension list: {e}")

    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)

            # Get values from config with defaults
            extension_list = config.get("extensions", [])
            auto_discover = config.get("auto_discover", True)

            logging.info(
                f"Loaded extension config: {len(extension_list)} extensions, auto_discover={auto_discover}"
            )
        except Exception as e:
            logging.error(f"Error loading extension config: {e}")
    else:
        logging.warning(
            f"Extension config file not found at {config_path}, using defaults"
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


def find_alembic_ini():
    """
    Find the alembic.ini file in various possible locations

    Returns:
        Path: The path to alembic.ini or None if not found
    """
    # Try in these locations (in order)
    potential_paths = [
        paths["root_dir"] / "alembic.ini",  # Standard location
        Path("alembic.ini"),  # Current directory
        Path(f"/{env('APP_NAME').lower()}/alembic.ini"),  # Docker location
        Path("../alembic.ini"),  # One level up
    ]

    for path in potential_paths:
        if path.exists():
            logging.debug(f"Found alembic.ini at {path}")
            return path

    logging.error("Could not find alembic.ini in any standard location")
    # Return the default expected path even if it doesn't exist
    return paths["root_dir"] / "alembic.ini"


def update_alembic_ini_database_url(alembic_ini_path):
    """
    Update the alembic.ini file with the correct database URL based on environment variables

    Args:
        alembic_ini_path: Path to the alembic.ini file

    Returns:
        bool: True if updated successfully, False otherwise
    """
    try:
        if not alembic_ini_path.exists():
            logging.error(
                f"Cannot update non-existent alembic.ini at {alembic_ini_path}"
            )
            return False

        # Get database URL from environment
        db_type, db_name, db_url = get_database_info()

        logging.info(f"Updating alembic.ini at {alembic_ini_path} with URL: {db_url}")

        # Read the current content
        with open(alembic_ini_path, "r") as f:
            content = f.readlines()

        # Update the sqlalchemy.url line
        updated = False
        for i, line in enumerate(content):
            if line.strip().startswith("sqlalchemy.url = "):
                content[i] = f"sqlalchemy.url = {db_url}\n"
                updated = True
                break

        # If not found, add it to the [alembic] section
        if not updated:
            for i, line in enumerate(content):
                if line.strip() == "[alembic]":
                    content.insert(i + 1, f"sqlalchemy.url = {db_url}\n")
                    updated = True
                    break

        # Write the updated content back
        with open(alembic_ini_path, "w") as f:
            f.writelines(content)

        logging.info(f"Successfully updated alembic.ini with database URL: {db_url}")
        return True
    except Exception as e:
        logging.error(f"Error updating alembic.ini: {e}")
        return False


def run_alembic_command(command, *args, extra_env=None, extension=None):
    """
    Run an alembic command and return the result

    Args:
        command (str): The alembic command to run
        *args: Additional arguments to pass to the command
        extra_env: Additional environment variables to set
        extension: Extension name if running for a specific extension

    Returns:
        bool: True if the command succeeded, False otherwise
    """
    alembic_ini_path = find_alembic_ini()

    # Update alembic.ini with correct database URL
    update_alembic_ini_database_url(alembic_ini_path)

    alembic_cmd = ["alembic"]

    # Add -c flag to specify config file if it's not in the current directory
    if not Path("alembic.ini").exists():
        alembic_cmd.extend(["-c", str(alembic_ini_path)])

    alembic_cmd.append(command)

    if args:
        alembic_cmd.extend(args)

    try:
        logging.info(f"Running Alembic command: {' '.join(alembic_cmd)}")

        # Get current working directory for context in logs
        cwd = os.getcwd()
        logging.info(f"Working directory: {cwd}")

        # Check if alembic.ini exists in the path we're expecting
        if not alembic_ini_path.exists():
            logging.error(f"alembic.ini not found at {alembic_ini_path}")
            return False

        # Prepare environment with correct PYTHONPATH
        env_vars = dict(os.environ)
        env_vars["PYTHONPATH"] = (
            f"{paths['root_dir']}{os.pathsep}{paths['src_dir']}{os.pathsep}{env_vars.get('PYTHONPATH', '')}"
        )

        # Set extension environment variable if specified
        if extension:
            env_vars["ALEMBIC_EXTENSION"] = extension

        # Add any extra environment variables
        if extra_env:
            env_vars.update(extra_env)

        # Run with full output capture
        result = subprocess.run(
            alembic_cmd, capture_output=True, text=True, env=env_vars
        )

        if result.returncode == 0:
            logging.info(f"Alembic command succeeded: {result.stdout.strip()}")
            return True
        else:
            logging.error(
                f"Alembic command failed with return code {result.returncode}"
            )
            logging.error(f"STDOUT: {result.stdout.strip()}")
            logging.error(f"STDERR: {result.stderr.strip()}")
            return False

    except Exception as e:
        logging.error(f"Error running Alembic command: {str(e)}")
        import traceback

        logging.error(traceback.format_exc())
        return False


def find_extension_migrations_dirs():
    """
    Find all extension migration directories

    Returns:
        list: List of tuples (extension_name, versions_dir)
    """
    extension_migrations = []

    # Get list of extensions we should process
    configured_extensions, auto_discover = load_extension_config()

    # Find all extensions with migrations directories
    extensions_base_dir = paths["src_dir"] / "extensions"
    if not extensions_base_dir.exists():
        logging.warning(f"Extensions directory not found at {extensions_base_dir}")
        return extension_migrations

    # List of extensions we found with migrations
    discovered_extensions = []

    # Find all extension directories
    for ext_dir in extensions_base_dir.iterdir():
        if not ext_dir.is_dir():
            continue

        # Check if this is an extension directory (should have __init__.py)
        if not (ext_dir / "__init__.py").exists():
            continue

        # Get extension name
        extension_name = ext_dir.name

        # Check if it has a migrations directory
        migrations_dir = ext_dir / "migrations"
        if migrations_dir.exists() and migrations_dir.is_dir():
            # Check if it has a versions directory
            versions_dir = migrations_dir / "versions"
            if versions_dir.exists() and versions_dir.is_dir():
                discovered_extensions.append(extension_name)
                extension_migrations.append((extension_name, versions_dir))
                logging.info(f"Found extension migrations dir: {versions_dir}")

    # If auto_discover is False, filter to only configured extensions
    if not auto_discover:
        extension_migrations = [
            (name, dir)
            for name, dir in extension_migrations
            if name in configured_extensions
        ]
        logging.info(f"Using configured extension list: {configured_extensions}")
    else:
        logging.info(f"Discovered extensions with migrations: {discovered_extensions}")

    return extension_migrations


def ensure_versions_directory():
    """
    Ensure the versions directory exists

    Returns:
        bool: True if directory exists or was created, False otherwise
    """
    try:
        versions_dir = paths["migrations_dir"] / "versions"

        if not versions_dir.exists():
            logging.info(f"Creating versions directory at {versions_dir}")
            versions_dir.mkdir(parents=True, exist_ok=True)

            # Create an empty __init__.py file in the versions directory
            init_file = versions_dir / "__init__.py"
            init_file.touch()
            logging.info(f"Created {init_file}")

        return True
    except Exception as e:
        logging.error(f"Error creating versions directory: {str(e)}")
        return False


def ensure_extension_versions_directory(extension_name):
    """
    Ensure the extension migrations directory and versions directory exist

    Args:
        extension_name: Name of the extension

    Returns:
        tuple: (success, versions_dir)
    """
    extension_dir = paths["src_dir"] / "extensions" / extension_name

    if not extension_dir.exists():
        logging.error(f"Extension directory not found at {extension_dir}")
        return False, None

    # Create migrations directory if it doesn't exist
    migrations_dir = extension_dir / "migrations"
    if not migrations_dir.exists():
        migrations_dir.mkdir()
        logging.info(f"Created migrations directory at {migrations_dir}")

    # Create versions directory if it doesn't exist
    versions_dir = migrations_dir / "versions"
    if not versions_dir.exists():
        versions_dir.mkdir()
        logging.info(f"Created versions directory at {versions_dir}")

    # Create __init__.py files to make the directories packages
    (migrations_dir / "__init__.py").touch(exist_ok=True)
    (versions_dir / "__init__.py").touch(exist_ok=True)

    # Create script.py.mako template in migrations directory if it doesn't exist
    script_template = migrations_dir / "script.py.mako"
    if not script_template.exists():
        # Copy from main migrations directory
        main_template = paths["migrations_dir"] / "script.py.mako"
        if main_template.exists():
            with open(main_template, "r") as src, open(script_template, "w") as dst:
                dst.write(src.read())
            logging.info(f"Copied script.py.mako to {script_template}")
        else:
            logging.warning(f"Main script.py.mako not found at {main_template}")
            return False, versions_dir

    # Create env.py file in migrations directory if it doesn't exist
    env_file = migrations_dir / "env.py"
    if not env_file.exists():
        # Create a symlink to the main env.py file
        try:
            # On Windows, we need special permissions for symlinks, so just copy the file
            if os.name == "nt":
                with open(paths["migrations_dir"] / "env.py", "r") as src, open(
                    env_file, "w"
                ) as dst:
                    dst.write(src.read())
            else:
                os.symlink(paths["migrations_dir"] / "env.py", env_file)
            logging.info(f"Created env.py at {env_file}")
        except Exception as e:
            logging.error(f"Error creating env.py symlink: {e}")
            return False, versions_dir

    # Create extension-specific alembic.ini
    alembic_ini = migrations_dir / "alembic.ini"
    if not alembic_ini.exists():
        # Get database URL
        db_type, db_name, db_url = get_database_info()

        # Create an alembic.ini file with extension-specific settings
        try:
            with open(alembic_ini, "w") as f:
                f.write(
                    f"""
# Extension-specific alembic.ini for {extension_name}
[alembic]
# Path to migration scripts
script_location = {migrations_dir}

# Template used to generate migration files
file_template = %%(rev)s_%%(slug)s

# Timestamp format used in migration file names
# Database connection URL - use the environment variable
sqlalchemy.url = {db_url}

# Version table - extension specific
version_table = alembic_version_{extension_name}

# Prepend to the revision identifier with extension prefix
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
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""
                )
            logging.info(f"Created alembic.ini at {alembic_ini}")
        except Exception as e:
            logging.error(f"Error creating alembic.ini: {e}")
            return False, versions_dir

    logging.info(f"Extension migration structure created for {extension_name}")
    return True, versions_dir


def check_alembic_setup():
    """
    Check that the Alembic environment is properly set up

    Returns:
        bool: True if setup is correct, False otherwise
    """
    try:
        # Find alembic.ini
        alembic_ini_path = find_alembic_ini()
        if not alembic_ini_path.exists():
            logging.error(f"alembic.ini not found at {alembic_ini_path}")
            return False
        else:
            logging.info(f"Found alembic.ini at {alembic_ini_path}")

        # Update the database URL in alembic.ini
        update_alembic_ini_database_url(alembic_ini_path)

        # Migrations directory is the directory this script is in
        migrations_dir = paths["migrations_dir"]
        if not migrations_dir.exists():
            logging.error(f"Migrations directory not found at {migrations_dir}")
            return False
        else:
            logging.info(f"Using migrations directory at {migrations_dir}")

        # Check that env.py exists in the migrations directory
        env_py = migrations_dir / "env.py"
        if not env_py.exists():
            logging.error(f"env.py not found at {env_py}")
            return False
        else:
            logging.info(f"Found env.py at {env_py}")

        # Check versions directory
        versions_dir = migrations_dir / "versions"
        if not versions_dir.exists():
            logging.warning(
                f"versions directory not found at {versions_dir}, will create it"
            )
            try:
                versions_dir.mkdir(exist_ok=True)
                (versions_dir / "__init__.py").touch(exist_ok=True)
                logging.info(f"Created versions directory at {versions_dir}")
            except Exception as e:
                logging.error(f"Failed to create versions directory: {e}")
                return False
        else:
            logging.info(f"Found versions directory at {versions_dir}")

        logging.info("Alembic setup looks correct")
        return True

    except Exception as e:
        logging.error(f"Error checking Alembic setup: {str(e)}")
        import traceback

        logging.error(traceback.format_exc())
        return False


def create_extension_alembic_ini(extension_name, extension_versions_dir):
    """
    Create a completely customized alembic.ini for an extension

    Args:
        extension_name: Name of the extension
        extension_versions_dir: Path to the extension's versions directory

    Returns:
        Path to temporary ini file
    """
    # Get the extension migrations directory (parent of versions)
    ext_migrations_dir = extension_versions_dir.parent

    # Get database URL from environment
    db_type, db_name, db_url = get_database_info()

    # Create a new alembic.ini file specifically for this extension
    config_content = f"""
# Extension-specific alembic.ini for {extension_name}
[alembic]
# Path to migration scripts
script_location = {ext_migrations_dir}

# Template used to generate migration files
file_template = %%(rev)s_%%(slug)s

# Timestamp format used in migration file names
# Database URL from environment
sqlalchemy.url = {db_url}

# Version path
version_locations = {extension_versions_dir}

# Version table - extension specific
version_table = alembic_version_{extension_name}

# Branch label - extension specific
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
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
    """

    # Write to temporary file
    temp_file = tempfile.NamedTemporaryFile(suffix=".ini", delete=False)
    temp_file.write(config_content.strip().encode("utf-8"))
    temp_file.close()

    logging.info(
        f"Created dedicated extension alembic.ini at {temp_file.name} for {extension_name}"
    )
    return Path(temp_file.name)


def run_extension_migration(extension_name, command, target="head"):
    """
    Run an alembic migration command for a specific extension

    Args:
        extension_name: Name of the extension
        command: Alembic command to run
        target: Migration target (default: "head")

    Returns:
        bool: True if successful, False otherwise
    """
    success, versions_dir = ensure_extension_versions_directory(extension_name)
    if not success:
        logging.error(f"Failed to ensure migration directory for {extension_name}")
        return False

    # Create a temporary alembic.ini for this extension
    temp_ini = create_extension_alembic_ini(extension_name, versions_dir)

    # Build the target string - for some commands like 'current' we don't need a target
    target_arg = (
        f"ext_{extension_name}@{target}" if command in ["upgrade", "downgrade"] else ""
    )

    # Run the alembic command
    alembic_cmd = ["alembic", "-c", str(temp_ini), command]
    if target_arg:
        alembic_cmd.append(target_arg)

    logging.info(
        f"Running {command} for extension {extension_name}: {' '.join(alembic_cmd)}"
    )

    try:
        # Set environment variable for extension-specific mode
        env_vars = dict(os.environ)
        env_vars["ALEMBIC_EXTENSION"] = extension_name

        # Run the command
        result = subprocess.run(
            alembic_cmd, env=env_vars, capture_output=True, text=True, check=False
        )

        if result.returncode == 0:
            logging.info(
                f"Migration {command} successful for extension {extension_name}"
            )
            # Clean up temporary file
            os.unlink(temp_ini)
            return True
        else:
            logging.error(
                f"Migration {command} failed for extension {extension_name}: {result.stderr}"
            )
            os.unlink(temp_ini)
            return False
    except Exception as e:
        logging.error(f"Error running migration for extension {extension_name}: {e}")
        try:
            os.unlink(temp_ini)
        except:
            pass
        return False


def run_extension_migrations():
    """
    Run migrations for all extensions

    Returns:
        bool: True if all migrations were successful, False otherwise
    """
    # Find all extension migrations
    extension_dirs = find_extension_migrations_dirs()

    # Get configured extensions if none were found
    if not extension_dirs:
        configured_extensions, _ = load_extension_config()
        # Create directories for configured extensions first
        for ext_name in configured_extensions:
            success, versions_dir = ensure_extension_versions_directory(ext_name)
            if success and versions_dir:
                extension_dirs.append((ext_name, versions_dir))

    if not extension_dirs:
        logging.info("No extension migrations found")
        return True

    failed_extensions = []
    for extension_name, versions_dir in extension_dirs:
        logging.info(f"Running migrations for extension: {extension_name}")

        # Check if we need to generate an initial migration
        if not list(versions_dir.glob("*.py")):
            logging.info(
                f"No migrations found for extension {extension_name}, creating initial migration"
            )
            create_extension_migration(extension_name, "Initial migration", auto=True)

        # Run the migration
        success = run_extension_migration(extension_name, "upgrade", "head")
        if not success:
            failed_extensions.append(extension_name)

    if failed_extensions:
        logging.error(
            f"Migration failed for extensions: {', '.join(failed_extensions)}"
        )
        return False

    return True


def create_extension_migration(extension_name, message, auto=True):
    """
    Create a migration for a specific extension

    Args:
        extension_name: Name of the extension
        message: Migration message
        auto: Whether to auto-generate changes based on models

    Returns:
        bool: True if migration was created successfully, False otherwise
    """
    try:
        # Ensure extension directories exist
        success, versions_dir = ensure_extension_versions_directory(extension_name)
        if not success:
            return False

        # Check if this is the first migration for this extension
        is_first_migration = True
        for _ in versions_dir.glob("*.py"):
            is_first_migration = False
            break

        # Create a temporary alembic.ini for this extension
        temp_ini = create_extension_alembic_ini(extension_name, versions_dir)

        # Build the alembic command
        alembic_cmd = ["alembic", "-c", str(temp_ini), "revision"]

        # Add auto-generation flag if requested
        if auto:
            alembic_cmd.append("--autogenerate")

        # Add revision message
        alembic_cmd.extend(["-m", message])

        # Add branch label for the extension
        if is_first_migration:
            alembic_cmd.extend(
                ["--head", "base", "--branch-label", f"ext_{extension_name}"]
            )
        else:
            alembic_cmd.extend(["--branch-label", f"ext_{extension_name}"])

        logging.info(
            f"Creating revision for extension {extension_name}: {' '.join(alembic_cmd)}"
        )

        try:
            # Set environment variable for extension-specific mode
            env_vars = dict(os.environ)
            env_vars["ALEMBIC_EXTENSION"] = extension_name

            # Run the command
            result = subprocess.run(
                alembic_cmd, env=env_vars, capture_output=True, text=True, check=False
            )

            if result.returncode == 0:
                logging.info(
                    f"Revision created successfully for extension {extension_name}: {result.stdout}"
                )
                # Clean up temporary file
                os.unlink(temp_ini)
                return True
            else:
                logging.error(
                    f"Revision creation failed for extension {extension_name}: {result.stderr}"
                )
                os.unlink(temp_ini)
                return False
        except Exception as e:
            logging.error(
                f"Error creating revision for extension {extension_name}: {e}"
            )
            os.unlink(temp_ini)
            return False

    except Exception as e:
        logging.error(f"Error creating extension migration: {str(e)}")
        import traceback

        logging.error(traceback.format_exc())
        return False


def check_and_apply_migrations():
    """
    Check if there are pending migrations and apply them

    Returns:
        bool: True if migrations were applied or none were needed, False if there was an error
    """
    try:
        logging.info("Starting migrations check with enhanced logging...")
        logging.info(f"Python path: {sys.path[:5]}")  # Show first 5 paths

        # Log the database configuration
        db_type, db_name, db_url = get_database_info()
        logging.info(
            f"Database configuration: TYPE={db_type}, NAME={db_name}, URL={db_url}"
        )

        # Make sure alembic is set up properly
        if not check_alembic_setup():
            logging.error("Alembic setup is not correct")

            # Try to fix alembic setup by creating minimal configuration
            logging.info("Attempting to fix Alembic setup...")
            try:
                create_minimal_alembic_config(paths)
            except Exception as setup_error:
                logging.error(f"Failed to create minimal Alembic setup: {setup_error}")
                return False

            # Check again if setup is fixed
            if not check_alembic_setup():
                logging.error("Still could not set up Alembic properly")
                return False
            else:
                logging.info("Successfully fixed Alembic setup")

        # Make sure versions directory exists
        if not ensure_versions_directory():
            return False

        # Check if we have any migration files
        versions_dir = paths["migrations_dir"] / "versions"
        migration_files = list(versions_dir.glob("*.py"))
        logging.info(f"Found {len(migration_files)} migration files in {versions_dir}")

        if not migration_files:
            logging.warning("No migration files found.")

        # Get current revision
        alembic_ini_path = find_alembic_ini()
        logging.info(f"Using alembic.ini at: {alembic_ini_path}")

        alembic_cmd = ["alembic"]

        if not Path("alembic.ini").exists():
            alembic_cmd.extend(["-c", str(alembic_ini_path)])

        alembic_cmd.append("current")

        # Prepare environment with correct PYTHONPATH
        env_vars = dict(os.environ)
        env_vars["PYTHONPATH"] = (
            f"{paths['root_dir']}{os.pathsep}{paths['src_dir']}{os.pathsep}{env_vars.get('PYTHONPATH', '')}"
        )

        logging.info(f"Running Alembic command: {' '.join(alembic_cmd)}")
        logging.info(f"With PYTHONPATH: {env_vars['PYTHONPATH']}")

        result = subprocess.run(
            alembic_cmd,
            capture_output=True,
            text=True,
            env=env_vars,
        )

        current_output = result.stdout.strip() or result.stderr.strip()
        logging.info(f"Current migration status: {current_output}")

        if result.returncode != 0:
            logging.error(
                f"Alembic current command failed with exit code {result.returncode}"
            )
            logging.error(f"Stdout: {result.stdout}")
            logging.error(f"Stderr: {result.stderr}")
            return False

        # Check if we need to apply migrations
        if "No such revision" in current_output or "(head)" not in current_output:
            logging.info("Database needs migration, upgrading to head")
            core_success = run_alembic_command("upgrade", "head")
            if not core_success:
                logging.error("Core database migration failed")
                return False
            else:
                logging.info("Core database migration successful")

            # After core migrations, run extension migrations
            ext_success = run_extension_migrations()
            return ext_success
        else:
            logging.info("Database is up to date, no migrations needed")

            # Always run extension migrations check even if core is up to date
            ext_success = run_extension_migrations()
            return ext_success

    except Exception as e:
        logging.error(f"Error checking or applying migrations: {str(e)}")
        logging.error(f"Exception type: {type(e).__name__}")
        import traceback

        logging.error(traceback.format_exc())
        return False


# New helper function to create a minimal alembic configuration
def create_minimal_alembic_config(paths):
    """Create a minimal working alembic.ini configuration"""
    logging.info("Creating minimal alembic.ini configuration")

    alembic_ini_path = paths["root_dir"] / "alembic.ini"
    migrations_dir = paths["migrations_dir"]
    versions_dir = migrations_dir / "versions"

    # Get database info from environment
    db_type, db_name, db_url = get_database_info()

    # Ensure versions directory exists
    if not versions_dir.exists():
        versions_dir.mkdir(parents=True, exist_ok=True)
        (versions_dir / "__init__.py").touch(exist_ok=True)
        logging.info(f"Created versions directory at {versions_dir}")

    # Create a minimal alembic.ini file
    with open(alembic_ini_path, "w") as f:
        f.write(
            f"""
[alembic]
script_location = {migrations_dir}
file_template = %%(rev)s_%%(slug)s
prepend_date = true
sqlalchemy.url = {db_url}
version_locations = {versions_dir}

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = INFO
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers = console
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""
        )

    logging.info(f"Created alembic.ini at {alembic_ini_path}")
    return alembic_ini_path
