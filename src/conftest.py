import logging
import os
import sys
from pathlib import Path

import pytest

from src.lib.Environment import env

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_setup")

# First, store original environment variables before loading .env
original_env = {}
for key in ["DATABASE_TYPE", "DATABASE_NAME"]:
    if key in os.environ:
        original_env[key] = os.environ[key]


# Add project root and src directories to path
def setup_python_path():
    """Ensure the Python path is set up correctly"""
    # Get the absolute path of the current file
    current_file_path = Path(__file__).resolve()
    # Get the test directory (where this file is)
    test_dir = current_file_path.parent
    # Get project root directory (parent of test)
    project_root = test_dir.parent
    # Get src directory
    src_dir = project_root / "src"

    # Add to Python path if not already there
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    logger.debug(f"Added to sys.path: {src_dir}, {project_root}")
    return project_root, src_dir


project_root, src_dir = setup_python_path()


# IMPORTANT: Configure test environment BEFORE any imports from the application
def configure_test_environment():
    """Configure environment for testing with SQLite database"""
    logger.debug("Configuring test environment")

    # Set environment variables for testing
    os.environ["DATABASE_TYPE"] = "sqlite"

    # Get the original database name if it exists

    original_db_name = env("DATABASE_NAME")
    test_db_name = f"{original_db_name}.test"

    # Forcefully set the test database name
    os.environ["DATABASE_NAME"] = test_db_name
    os.environ["SEED_DATA"] = "true"

    # Delete existing test database if it exists (for clean start)
    db_file = f"{test_db_name}.db"
    for check_path in [
        ".",  # Current directory
        str(project_root),  # Project root
        str(src_dir),  # src directory
        os.path.join(project_root, "instance"),  # Instance folder
    ]:
        test_db_path = os.path.join(check_path, db_file)
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
                logger.debug(f"Deleted existing test database: {test_db_path}")
            except Exception as e:
                logger.error(f"Failed to delete database file {test_db_path}: {e}")

    logger.debug(f"Set DATABASE_TYPE=sqlite, DATABASE_NAME={test_db_name}")
    return test_db_name


# Configure environment BEFORE importing any application code
test_db_name = configure_test_environment()

# Monkey patch database connection handling to ensure test database is used
# This must happen before any other imports that might use the database
import src.database.Base

# Now it's safe to import the application modules

original_get_session = src.database.Base.get_session


def get_test_session(*args, **kwargs):
    """Override to ensure we always use the test database"""
    logger.debug(
        f"Getting test session with DATABASE_NAME={os.environ['DATABASE_NAME']}"
    )
    return original_get_session(*args, **kwargs)


src.database.Base.get_session = get_test_session

# Now import setup functions after the patch
from Server import seed_data, setup_database


@pytest.fixture(scope="session")
def db():
    """
    Session-wide test database fixture.
    Sets up the database once for all tests and tears it down after all tests.
    """
    logger.debug("Running database setup fixture")

    # Verify we're using the test database before proceeding
    current_db_name = env("DATABASE_NAME")
    logger.debug(f"Current DATABASE_NAME: {current_db_name}")

    if not current_db_name.endswith(".test"):
        logger.error(
            f"DATABASE_NAME still doesn't have .test suffix: {current_db_name}"
        )
        raise Exception(
            f"Test environment not properly configured! DATABASE_NAME={current_db_name}"
        )

    # Use the imported setup_database function
    logger.debug("Calling setup_database()...")
    setup_database()

    # Check if the database file was created correctly
    db_file = f"{current_db_name}.db"
    db_paths = []
    for check_path in [
        ".",  # Current directory
        str(project_root),  # Project root
        str(src_dir),  # src directory
        os.path.join(project_root, "instance"),  # Instance folder
    ]:
        test_db_path = os.path.join(check_path, db_file)
        if os.path.exists(test_db_path):
            db_paths.append(test_db_path)
            logger.debug(f"Found database file at: {test_db_path}")

    if not db_paths:
        logger.error(f"No database file was created after setup_database()")

    # Double check we're still using the test database
    logger.debug(f"DATABASE_NAME before seeding: {env('DATABASE_NAME')}")

    # Run the seed_data function
    try:
        logger.debug("Starting data seeding...")
        seed_data()
        logger.debug("Finished seeding data successfully")
    except Exception as e:
        logger.error(f"Error in seeding data: {str(e)}", exc_info=True)
        raise

    logger.debug("Database setup complete")

    # Provide the fixture
    yield

    # Teardown: delete the test database
    cleanup_test_database(test_db_name)


def cleanup_test_database(db_name):
    """Clean up the test database after tests are complete"""
    try:
        logger.debug(f"Starting database cleanup for {db_name}")

        # For SQLite, find and delete the database file
        if env("DATABASE_TYPE") == "sqlite":
            db_file = f"{db_name}.db"
            deleted_count = 0

            # Check multiple possible locations
            for check_path in [
                ".",  # Current directory
                str(project_root),  # Project root
                str(src_dir),  # src directory
                os.path.join(project_root, "instance"),  # Instance folder
            ]:
                test_db_path = os.path.join(check_path, db_file)
                if os.path.exists(test_db_path):
                    try:
                        os.remove(test_db_path)
                        deleted_count += 1
                        logger.debug(f"Removed database file: {test_db_path}")
                    except Exception as e:
                        logger.error(f"Error removing {test_db_path}: {e}")

            if deleted_count == 0:
                logger.warning(f"No database files found to delete for {db_name}")
            else:
                logger.debug(f"Deleted {deleted_count} database files for {db_name}")

        logger.debug("Database cleanup completed")
    except Exception as e:
        logger.error(f"Error during database cleanup: {str(e)}", exc_info=True)


# Restore original environment when the module is unloaded (optional)
def restore_environment():
    """Restore original environment variables when done"""
    for key, value in original_env.items():
        os.environ[key] = value
    logger.debug("Restored original environment variables")


# Uncomment if you want to restore environment after tests
# import atexit
# atexit.register(restore_environment)
