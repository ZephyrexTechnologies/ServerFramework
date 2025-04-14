"""
Main application entry point with proper multi-worker support.
Parent process handles imports and initialization, while workers handle request processing.
"""

import glob
import importlib
import logging
import os
import sys
from pathlib import Path

import uvicorn

from database.Manager import DatabaseManager
from lib.Environment import env
from lib.Logging import setup_enhanced_logging


def setup_python_path():
    """Ensure the Python path is set up correctly"""
    # Get the absolute path of the current file
    current_file_path = Path(__file__).resolve()
    # Get src directory (where this file is)
    src_dir = current_file_path.parent
    # Get root directory (parent of src)
    root_dir = src_dir.parent

    # Add to Python path if not already there - check for exact match to avoid duplication
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    # Debug logging
    logging.debug(f"Python path setup: src_dir={src_dir}, root_dir={root_dir}")
    logging.debug(f"Current sys.path: {sys.path[:3]}")  # Show first 3 paths


def import_all_db_models():
    """Automatically import all database model files starting with DB_"""
    logging.info("Importing database models...")

    # Get the database directory path
    current_file_path = Path(__file__).resolve()
    src_dir = current_file_path.parent
    database_dir = src_dir / "database"

    # Find all Python files starting with DB_
    db_files_pattern = os.path.join(database_dir, "DB_*.py")
    db_files = glob.glob(db_files_pattern)

    # Import each file
    imported_count = 0
    for file_path in db_files:
        try:
            # Get the module name without .py extension
            file_name = os.path.basename(file_path)
            module_name = file_name[:-3]  # Remove .py

            # Full module path for import
            full_module_name = f"database.{module_name}"

            # Import the module
            importlib.import_module(full_module_name)
            imported_count += 1

        except Exception as e:
            logging.error(f"Error importing {file_path}: {e}")

    logging.info(f"Successfully imported {imported_count} database model files")


def setup_database():
    """Initialize database and set up default roles. Runs once in parent process."""
    import logging
    import time

    from sqlalchemy.orm import configure_mappers

    # Set up Python path
    setup_python_path()

    # Import all database models dynamically
    import_all_db_models()

    # Import essential modules
    from database.Base import DATABASE_NAME, DATABASE_TYPE, Base

    # Get the database manager instance
    db_manager = DatabaseManager.get_instance()

    # Initialize engine configuration in parent process
    db_manager.init_engine_config()

    # Get engine for initial setup
    engine = db_manager.get_setup_engine()

    # Database setup with retry logic
    if DATABASE_TYPE != "sqlite":
        logging.info("Connecting to database...")
        max_retries = 5
        retry_count = 0

        while retry_count < max_retries:
            try:
                connection = engine.connect()
                connection.close()
                break
            except Exception as e:
                retry_count += 1
                logging.error(
                    f"Error connecting to database (attempt {retry_count}/{max_retries})",
                    exc_info=True,
                )
                if retry_count == max_retries:
                    raise Exception(
                        "Failed to connect to database after maximum retries"
                    )
                time.sleep(5)

    # Try to import and run migrations
    try:
        # Import migration helper with explicit path handling
        from database.migrations.MigrationHelper import (
            check_alembic_setup,
            check_and_apply_migrations,
        )

        if not check_and_apply_migrations():
            logging.error("Failed to apply migrations.")
            raise Exception("Failed to apply migrations.")
        else:
            logging.info(
                f"Successfully verified database migrations for {DATABASE_NAME}"
            )
    except ImportError as e:
        logging.error(f"Could not import migration helper: {e}")
    except Exception as e:
        logging.error(f"Error during migration process: {e}", exc_info=True)
    configure_mappers()
    # setup_validators(Session)


def seed_data():
    if str(env("SEED_DATA")).lower() == "true":
        from database.Seed import seed

        seed()


repo = env("APP_REPOSITORY")
if __name__ == "__main__":
    # Use spawn method for better cross-platform compatibility
    setup_enhanced_logging()

    # Run database setup once in parent process
    setup_database()
    seed_data()
    # Start Uvicorn with the app as an import string
    logging.info(
        f"Booting {env('APP_NAME')} server, please report any issues to {env('APP_REPOSITORY')}"
    )
    uvicorn.run(
        "app:create_app",
        host="0.0.0.0",
        port=1996,
        workers=int(
            env(
                "UVICORN_WORKERS",
            )
        ),
        log_level=str(env("LOG_LEVEL")).lower(),
        proxy_headers=True,
        reload=str(env("LOG_LEVEL")).lower() == "debug",
        factory=True,
    )
