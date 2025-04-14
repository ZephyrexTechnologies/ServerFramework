import argparse
import importlib.util
import logging
import os
import sys
import tempfile
from pathlib import Path

from MigrationHelper import (
    create_extension_migration,
    find_extension_migrations_dirs,
    get_database_info,
    load_extension_config,
    normalize_path,
    run_alembic_command,
    run_extension_migration,
)

from lib.Environment import env


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


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
    database_dir_norm = normalize_path(database_dir)
    migrations_dir_norm = normalize_path(migrations_dir)

    # Log the paths for debugging
    logging.debug(
        f"Raw paths: migrations={migrations_dir}, db={database_dir}, src={src_dir}, root={root_dir}"
    )
    logging.debug(
        f"Normalized paths: migrations={migrations_dir_norm}, db={database_dir_norm}, src={src_dir_norm}, root={root_dir_norm}"
    )

    # Add to Python path if not already there (use normalized paths)
    if root_dir_norm not in sys.path:
        sys.path.insert(0, root_dir_norm)
    if src_dir_norm not in sys.path:
        sys.path.insert(0, src_dir_norm)

    return {
        "migrations_dir": Path(migrations_dir_norm),
        "database_dir": Path(database_dir_norm),
        "src_dir": Path(src_dir_norm),
        "root_dir": Path(root_dir_norm),
    }


def find_alembic_ini():
    """
    Find the alembic.ini file in various possible locations

    Returns:
        Path: The path to alembic.ini or None if not found
    """
    paths = setup_python_path()

    # Try in these locations (in order)
    potential_paths = [
        paths["root_dir"] / "alembic.ini",  # Standard location
        Path("alembic.ini"),  # Current directory
        Path("/zephyrex/alembic.ini"),  # Docker location
        Path("../alembic.ini"),  # One level up
    ]

    for path in potential_paths:
        if path.exists():
            logging.debug(f"Found alembic.ini at {path}")
            return path

    logging.error("Could not find alembic.ini in any standard location")
    # Return the default expected path even if it doesn't exist
    return paths["root_dir"] / "alembic.ini"


def create_temp_alembic_ini(
    original_ini_path, extension_version_path=None, extension_name=None
):
    """
    Create a temporary alembic.ini file with updated version_locations
    to include the extension path

    Args:
        original_ini_path: Path to the original alembic.ini
        extension_version_path: Path to the extension's versions directory
        extension_name: Name of the extension (used for script_location)

    Returns:
        Path to temporary ini file
    """
    if not original_ini_path.exists():
        logging.error(f"Original alembic.ini not found at {original_ini_path}")
        return None

    paths = setup_python_path()
    core_versions_dir = paths["migrations_dir"] / "versions"
    core_migrations_dir = paths["migrations_dir"]

    # Get database info from environment
    db_type, db_name, db_url = get_database_info()
    logging.info(f"Creating temp alembic.ini with database URL: {db_url}")

    # Read original file
    with open(original_ini_path, "r") as f:
        content = f.read()

    # Always add or replace the version_locations property
    lines = content.splitlines()
    updated_content = []
    version_locations_added = False
    script_location_added = False
    version_table_added = False
    branch_label_added = False
    database_url_added = False

    for line in lines:
        if line.strip().startswith("version_locations ="):
            # Skip existing version_locations line
            continue
        elif line.strip().startswith("version_table ="):
            # Skip existing version_table line
            continue
        elif line.strip().startswith("branch_label ="):
            # Skip existing branch_label line
            continue
        elif line.strip().startswith("sqlalchemy.url ="):
            # Replace with our environment-based URL
            updated_content.append(f"sqlalchemy.url = {db_url}")
            database_url_added = True
            continue
        elif line.strip().startswith("script_location ="):
            # For extension operations, use the extension's migrations directory
            if extension_name and extension_version_path:
                ext_migrations_dir = extension_version_path.parent
                updated_content.append(f"script_location = {ext_migrations_dir}")
                script_location_added = True
            else:
                updated_content.append(line)

            # Add version_locations after script_location
            if extension_version_path:
                # For extension operations, ONLY include the extension path
                version_locations = f"version_locations = {extension_version_path}"
                # Add custom version table for extension
                version_table = f"version_table = alembic_version_{extension_name}"
                # Add branch label for extension
                branch_label = f"branch_label = ext_{extension_name}"
            else:
                # For core operations, ONLY include the core path
                version_locations = f"version_locations = {core_versions_dir}"
                version_table = "version_table = alembic_version"
                branch_label = ""  # No branch label for core

            updated_content.append(version_locations)
            updated_content.append(version_table)
            if branch_label:
                updated_content.append(branch_label)
                branch_label_added = True

            version_locations_added = True
            version_table_added = True
        else:
            updated_content.append(line)

    # If we didn't find a script_location line, add it and version_locations to the end
    if not script_location_added and extension_name and extension_version_path:
        ext_migrations_dir = extension_version_path.parent
        updated_content.append(f"script_location = {ext_migrations_dir}")

    # If we didn't find or add version_locations yet, add it
    if not version_locations_added:
        if extension_version_path:
            version_locations = f"version_locations = {extension_version_path}"
        else:
            version_locations = f"version_locations = {core_versions_dir}"

        updated_content.append(version_locations)

    # If we didn't add a version table yet, add it
    if not version_table_added:
        if extension_name:
            version_table = f"version_table = alembic_version_{extension_name}"
        else:
            version_table = "version_table = alembic_version"

        updated_content.append(version_table)

    # If we didn't add branch label for extension, add it
    if extension_name and not branch_label_added:
        branch_label = f"branch_label = ext_{extension_name}"
        updated_content.append(branch_label)

    # If we didn't add the database URL, add it
    if not database_url_added:
        updated_content.append(f"sqlalchemy.url = {db_url}")

    # Write to temporary file
    temp_file = tempfile.NamedTemporaryFile(suffix=".ini", delete=False)
    temp_file.write("\n".join(updated_content).encode("utf-8"))
    temp_file.close()

    logging.info(
        f"Created temporary alembic.ini at {temp_file.name} with version_locations updated and DB URL: {db_url}"
    )
    return Path(temp_file.name)


def import_database_info():
    """
    Import database information from Base.py
    """
    paths = setup_python_path()

    try:
        # First try importing the module
        from database.Base import DATABASE_NAME, DATABASE_TYPE

        logging.info(
            f"Imported database info from Base.py: TYPE={DATABASE_TYPE}, NAME={DATABASE_NAME}"
        )
        return DATABASE_NAME, DATABASE_TYPE
    except ImportError:
        # If that fails, try direct import
        base_path = os.path.join(paths["database_dir"], "Base.py")
        if not os.path.exists(base_path):
            logging.error(f"Base.py not found at {base_path}")
            return None, None

        # Import the module dynamically
        try:
            spec = importlib.util.spec_from_file_location("database.Base", base_path)
            Base = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(Base)

            db_name = getattr(Base, "DATABASE_NAME", None)
            db_type = getattr(Base, "DATABASE_TYPE", None)
            logging.info(
                f"Imported database info dynamically: TYPE={db_type}, NAME={db_name}"
            )
            return db_name, db_type
        except Exception as e:
            logging.error(f"Error importing Base.py dynamically: {e}")
            return None, None


def ensure_extension_migrations_dir(extension_name):
    """
    Ensure the migrations directory exists for an extension

    Args:
        extension_name: Name of the extension

    Returns:
        tuple: (migrations_dir, versions_dir)
    """
    paths = setup_python_path()
    extension_dir = paths["src_dir"] / "extensions" / extension_name

    # Check if extension directory exists
    if not extension_dir.exists():
        logging.error(f"Extension directory not found at {extension_dir}")
        return None, None

    logging.info(f"Setting up migration directory for extension: {extension_name}")

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

    # Create __init__.py file in migrations directory if it doesn't exist
    init_file = migrations_dir / "__init__.py"
    if not init_file.exists():
        with open(init_file, "w") as f:
            f.write("# Migrations package for extension\n")
        logging.info(f"Created __init__.py at {init_file}")

    # Create __init__.py file in versions directory if it doesn't exist
    versions_init = versions_dir / "__init__.py"
    if not versions_init.exists():
        versions_init.touch(exist_ok=True)
        logging.info(f"Created __init__.py at {versions_init}")

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

    # Create extension-specific alembic.ini
    alembic_ini = migrations_dir / "alembic.ini"
    if not alembic_ini.exists():
        # Get database URL from environment
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

# Database URL
sqlalchemy.url = {db_url}

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
                )
            logging.info(f"Created alembic.ini at {alembic_ini}")
        except Exception as e:
            logging.error(f"Error creating alembic.ini: {e}")

    logging.info(f"Extension migration structure created at {migrations_dir}")
    return migrations_dir, versions_dir


def run_all_migrations(command, target="head"):
    """
    Run migrations for core and all extensions

    Args:
        command: Alembic command to run (e.g. "upgrade", "downgrade")
        target: Migration target (default: "head")

    Returns:
        bool: True if all migrations were successful, False otherwise
    """
    # Log environment variables related to database
    db_type = env("DATABASE_TYPE")
    db_name = env("DATABASE_NAME")
    logging.info(f"Database environment: TYPE={db_type}, NAME={db_name}")

    # First run core migrations
    logging.info(f"Running {command} for core migrations")

    # Find the main alembic.ini file
    alembic_ini = find_alembic_ini()

    # Run the command on the core migrations
    core_result = run_alembic_command(command, target)

    if not core_result:
        logging.error(f"Core migrations {command} failed")
        return False

    # Get the list of extension migrations to run
    extension_migrations = find_extension_migrations_dirs()

    # If no extensions found with migrations, check configured extensions and initialize them
    if not extension_migrations:
        configured_extensions, _ = load_extension_config()
        logging.info(
            f"No extensions with migrations found, checking configured extensions: {configured_extensions}"
        )
        for ext_name in configured_extensions:
            migrations_dir, versions_dir = ensure_extension_migrations_dir(ext_name)
            if migrations_dir and versions_dir:
                extension_migrations.append((ext_name, versions_dir))
                logging.info(f"Added extension {ext_name} to migration list")

    # Track failures
    failures = []

    # Run migrations for each extension
    for extension_name, versions_dir in extension_migrations:
        logging.info(f"Running migrations for extension: {extension_name}")

        # Check if there are any migration files
        migration_files = list(versions_dir.glob("*.py"))
        if not migration_files:
            logging.info(
                f"No migration files found for {extension_name}, creating initial migration"
            )
            # Create initial migration if none exist
            initial_result = create_revision_for_extension(
                extension_name, "Initial migration", True
            )
            if not initial_result:
                logging.error(
                    f"Failed to create initial migration for extension {extension_name}"
                )
                failures.append(extension_name)
                continue

        # Run the migration
        ext_result = run_extension_migration(extension_name, command, target)
        if not ext_result:
            failures.append(extension_name)

    # Report results
    if failures:
        logging.error(f"Migrations failed for extensions: {', '.join(failures)}")
        return False
    else:
        logging.info(f"All migrations {command} successfully")
        return True


def create_revision_for_extension(extension_name, message, auto=False):
    """
    Create a new migration revision for a specific extension

    Args:
        extension_name: Name of the extension
        message: Revision message
        auto: Whether to auto-generate the migration (True) or create empty (False)

    Returns:
        bool: True if successful, False otherwise
    """
    # Ensure the extension migration directory exists
    migrations_dir, versions_dir = ensure_extension_migrations_dir(extension_name)
    if not migrations_dir:
        logging.error(f"Failed to ensure migration directory for {extension_name}")
        return False

    # Log the database configuration
    db_type, db_name, db_url = get_database_info()
    logging.info(
        f"Creating revision with database config: TYPE={db_type}, NAME={db_name}, URL={db_url}"
    )

    # Use the helper function from MigrationHelper to create the migration
    result = create_extension_migration(extension_name, message, auto)

    if result:
        logging.info(f"Successfully created migration for extension {extension_name}")
    else:
        logging.error(f"Failed to create migration for extension {extension_name}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Database migration tool")
    subparsers = parser.add_subparsers(dest="command", help="Migration command")

    # Upgrade command
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

    # Downgrade command
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

    # Revision command
    revision_parser = subparsers.add_parser("revision", help="Create a new revision")
    revision_parser.add_argument(
        "--extension", help="Create a revision for a specific extension"
    )
    revision_parser.add_argument(
        "--message", "-m", required=True, help="Revision message"
    )
    revision_parser.add_argument(
        "--auto", action="store_true", help="Auto-generate migration"
    )

    # History command
    history_parser = subparsers.add_parser(
        "history", help="Show migration version history"
    )
    history_parser.add_argument(
        "--extension", help="Show history for a specific extension"
    )

    # Current command
    current_parser = subparsers.add_parser(
        "current", help="Show current migration version"
    )
    current_parser.add_argument(
        "--extension", help="Show current version for a specific extension"
    )

    # New init command to initialize extension migrations
    init_parser = subparsers.add_parser(
        "init", help="Initialize migration structure for an extension"
    )
    init_parser.add_argument(
        "--extension", required=True, help="Extension to initialize"
    )

    # Debug command to show environment and configuration
    debug_parser = subparsers.add_parser(
        "debug", help="Show detailed debug information"
    )

    args = parser.parse_args()

    # Set up logging
    setup_logging()

    if args.command in ["upgrade", "downgrade"]:
        # Log database environment at the start
        db_type, db_name, db_url = get_database_info()
        logging.info(
            f"Starting {args.command} with database: TYPE={db_type}, NAME={db_name}, URL={db_url}"
        )

        if args.all:
            # Run migrations for core and all extensions
            success = run_all_migrations(args.command, args.target)
            sys.exit(0 if success else 1)
        elif args.extension:
            # Run migrations for a specific extension
            success = run_extension_migration(args.extension, args.command, args.target)
            sys.exit(0 if success else 1)
        else:
            # Run migrations for core only
            logging.info(f"Running {args.command} for core migrations")
            success = run_alembic_command(args.command, args.target)
            sys.exit(0 if success else 1)
    elif args.command == "revision":
        # Log database environment at the start
        db_type, db_name, db_url = get_database_info()
        logging.info(
            f"Creating revision with database: TYPE={db_type}, NAME={db_name}, URL={db_url}"
        )

        if args.extension:
            # Create a revision for a specific extension
            success = create_revision_for_extension(
                args.extension, args.message, args.auto
            )
            sys.exit(0 if success else 1)
        else:
            # Create a revision for core
            cmd = ["revision"]
            if args.auto:
                cmd.append("--autogenerate")
            cmd.extend(["-m", args.message])
            success = run_alembic_command(*cmd)
            sys.exit(0 if success else 1)
    elif args.command == "history":
        if args.extension:
            # Show history for a specific extension
            success = run_extension_migration(args.extension, "history")
            sys.exit(0 if success else 1)
        else:
            # Show history for core
            success = run_alembic_command("history")
            sys.exit(0 if success else 1)
    elif args.command == "current":
        if args.extension:
            # Show current version for a specific extension
            success = run_extension_migration(args.extension, "current")
            sys.exit(0 if success else 1)
        else:
            # Show current version for core
            success = run_alembic_command("current")
            sys.exit(0 if success else 1)
    elif args.command == "init":
        # Initialize migration structure for an extension
        migrations_dir, versions_dir = ensure_extension_migrations_dir(args.extension)
        success = migrations_dir is not None and versions_dir is not None
        sys.exit(0 if success else 1)
    elif args.command == "debug":
        # Print detailed debug information
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
        paths = setup_python_path()
        for key, value in paths.items():
            print(f"{key}: {value}")

        print("\n=== ALEMBIC CONFIG ===")
        alembic_ini = find_alembic_ini()
        print(f"alembic.ini: {alembic_ini}")
        if alembic_ini.exists():
            with open(alembic_ini, "r") as f:
                for line in f:
                    if any(
                        x in line.lower()
                        for x in ["sqlalchemy.url", "database", "version"]
                    ):
                        print(f"  {line.strip()}")

        print("\n=== EXTENSIONS ===")
        extensions, auto_discover = load_extension_config()
        print(f"Configured extensions: {extensions}")
        print(f"Auto-discover: {auto_discover}")

        extension_dirs = find_extension_migrations_dirs()
        if extension_dirs:
            print("Found extension migrations:")
            for name, path in extension_dirs:
                print(f"  {name}: {path}")
        else:
            print("No extension migrations found")

        sys.exit(0)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
