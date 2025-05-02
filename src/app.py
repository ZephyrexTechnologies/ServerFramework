"""
Combined application entry point with proper multi-worker support and FastAPI application factory.
Handles virtual environment setup, database migrations, API setup, and server launching.
"""

import glob
import importlib
import logging
import os
import subprocess
import sys
import venv
from contextlib import asynccontextmanager
from pathlib import Path

import inflect
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

from database.migrations.Migration import run_all_migrations
from database.StaticDatabaseManager import DatabaseManager
from lib.Environment import env
from lib.Pydantic2Strawberry import schema

# from lib.Logging import setup_enhanced_logging

# Add instance
p = inflect.engine()


def log_unhandled_exception(exc_type, exc_value, exc_traceback):
    """Log unhandled exceptions with full traceback"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


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


def import_extension_models():
    """Import DB_*.py files from extension directories listed in APP_EXTENSIONS environment variable"""
    logging.info("Importing extension database models...")

    # Get the extensions directory path
    current_file_path = Path(__file__).resolve()
    src_dir = current_file_path.parent
    extensions_dir = src_dir / "extensions"

    if not extensions_dir.exists() or not extensions_dir.is_dir():
        logging.warning(f"Extensions directory not found: {extensions_dir}")
        return

    # Get extension list from APP_EXTENSIONS environment variable
    app_extensions = env("APP_EXTENSIONS")
    if not app_extensions:
        logging.warning("APP_EXTENSIONS environment variable not set or empty")
        return

    extension_list = [ext.strip() for ext in app_extensions.split(",") if ext.strip()]
    if not extension_list:
        logging.warning("No extensions found in APP_EXTENSIONS")
        return

    logging.info(f"Loading models from specified extensions: {extension_list}")

    # Process each extension directory from the specific list
    imported_count = 0
    for extension_name in extension_list:
        ext_dir = extensions_dir / extension_name

        if not ext_dir.exists() or not ext_dir.is_dir():
            logging.warning(f"Specified extension directory not found: {ext_dir}")
            continue

        # Find all DB_*.py files in this specified extension
        db_files_pattern = os.path.join(ext_dir, "DB_*.py")
        db_files = glob.glob(db_files_pattern)

        # Import each file
        for file_path in db_files:
            try:
                # Skip test files
                if file_path.endswith("_test.py"):
                    continue

                # Get the module name without .py extension
                file_name = os.path.basename(file_path)
                module_name = file_name[:-3]  # Remove .py

                # Full module path for import
                full_module_name = f"extensions.{extension_name}.{module_name}"

                # Import the module
                importlib.import_module(full_module_name)
                imported_count += 1
                logging.debug(f"Imported extension model: {full_module_name}")

            except Exception as e:
                logging.error(f"Error importing extension model {file_path}: {e}")

    logging.info(
        f"Successfully imported {imported_count} extension database model files"
    )


def import_extension_endpoints():
    """Import EP_*.py files from extension directories listed in APP_EXTENSIONS environment variable"""
    logging.info("Importing extension endpoints...")

    # Get the extensions directory path
    current_file_path = Path(__file__).resolve()
    src_dir = current_file_path.parent
    extensions_dir = src_dir / "extensions"

    if not extensions_dir.exists() or not extensions_dir.is_dir():
        logging.warning(f"Extensions directory not found: {extensions_dir}")
        return

    # Get extension list from APP_EXTENSIONS environment variable
    app_extensions = env("APP_EXTENSIONS")
    if not app_extensions:
        logging.warning("APP_EXTENSIONS environment variable not set or empty")
        return

    extension_list = [ext.strip() for ext in app_extensions.split(",") if ext.strip()]
    if not extension_list:
        logging.warning("No extensions found in APP_EXTENSIONS")
        return

    logging.info(f"Loading endpoints from specified extensions: {extension_list}")

    # Process each extension directory from the specific list
    imported_count = 0
    for extension_name in extension_list:
        ext_dir = extensions_dir / extension_name

        if not ext_dir.exists() or not ext_dir.is_dir():
            logging.warning(f"Specified extension directory not found: {ext_dir}")
            continue

        # Find all EP_*.py files in this specified extension
        ep_files_pattern = os.path.join(ext_dir, "EP_*.py")
        ep_files = glob.glob(ep_files_pattern)

        # Import each file
        for file_path in ep_files:
            try:
                # Skip test files
                if file_path.endswith("_test.py"):
                    continue

                # Get the module name without .py extension
                file_name = os.path.basename(file_path)
                module_name = file_name[:-3]  # Remove .py

                # Full module path for import
                full_module_name = f"extensions.{extension_name}.{module_name}"

                # Import the module
                importlib.import_module(full_module_name)
                imported_count += 1
                logging.debug(f"Imported extension endpoint: {full_module_name}")

            except Exception as e:
                logging.error(f"Error importing extension endpoint {file_path}: {e}")

    logging.info(f"Successfully imported {imported_count} extension endpoint files")


def setup_database():
    """Initialize database and set up default roles. Runs once in parent process."""
    import logging
    import time

    from sqlalchemy.orm import configure_mappers

    # Set up Python path
    setup_python_path()

    # Import all database models dynamically
    import_all_db_models()

    # Import extension models
    import_extension_models()

    # Get the database manager instance
    db_manager = DatabaseManager.get_instance()

    # Initialize engine configuration in parent process
    db_manager.init_engine_config()

    # Get engine for initial setup
    engine = db_manager.get_setup_engine()

    db_type = env("DATABASE_TYPE")
    db_name = env("DATABASE_NAME")
    # Database setup with retry logic
    if db_type != "sqlite":
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
        # Apply all migrations ('upgrade' command with 'head' target)
        if not run_all_migrations("upgrade", "head"):
            logging.error("Failed to apply migrations.")
            raise Exception("Failed to apply migrations.")
        else:
            logging.info(f"Successfully verified database migrations for {db_name}")
    except ImportError as e:
        logging.error(f"Could not import migration helper: {e}")
    except Exception as e:
        logging.error(f"Error during migration process: {e}", exc_info=True)
    configure_mappers()


def seed_data():
    if str(env("SEED_DATA")).lower() == "true":
        from database.StaticSeedManager import seed

        seed()


# Initialize database configuration in parent process
db_manager = DatabaseManager.get_instance()
db_manager.init_engine_config()


def create_app():
    """
    FastAPI application factory function.
    Returns a configured FastAPI application instance.
    """
    # Configure environment
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    # setup_enhanced_logging()

    # Set up global exception handler
    sys.excepthook = log_unhandled_exception

    # Read version
    this_directory = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(this_directory, "version"), encoding="utf-8") as f:
        version = f.read().strip()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Handles startup and shutdown events for each worker"""
        # Initialize services
        db_manager.init_worker()  # Now the worker can initialize since config exists

        try:
            yield
        finally:
            # Cleanup services
            await db_manager.close_worker()

    # Initialize FastAPI application
    app = FastAPI(
        title=env("APP_NAME"),
        version=env("APP_VERSION"),
        description=f"{env('APP_NAME')} is {p.a(env('APP_DESCRIPTION'))}. Visit the GitHub repo for more information or to report issues. {env('APP_REPOSITORY')}",
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        openapi_version="3.1.0",  # Specify the OpenAPI version
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Automatically discover and include all EP_ routers
    endpoints_dir = os.path.join(this_directory, "endpoints")
    ep_modules = glob.glob(os.path.join(endpoints_dir, "EP_*.py"))

    # Load extension endpoints from APP_EXTENSIONS environment variable
    app_extensions = env("APP_EXTENSIONS")
    if app_extensions:
        try:
            # Parse the comma-separated extensions list
            extension_list = [
                ext.strip() for ext in app_extensions.split(",") if ext.strip()
            ]
            logging.info(
                f"Loading endpoints from extensions specified in APP_EXTENSIONS: {extension_list}"
            )

            extensions_dir = os.path.join(this_directory, "extensions")

            # Process only the specified extensions
            for extension_name in extension_list:
                extension_dir = os.path.join(extensions_dir, extension_name)
                if not os.path.exists(extension_dir) or not os.path.isdir(
                    extension_dir
                ):
                    logging.warning(f"Extension directory not found: {extension_dir}")
                    continue

                # Find all endpoint modules in this specific extension
                extension_ep_pattern = os.path.join(extension_dir, "EP_*.py")
                extension_ep_files = glob.glob(extension_ep_pattern)

                for ep_file in extension_ep_files:
                    # Skip test modules
                    if ep_file.endswith("_test.py"):
                        continue

                    # Get module name
                    relative_path = os.path.relpath(ep_file, this_directory)
                    # Convert path to module notation (replace / with . and remove .py)
                    module_path = relative_path.replace(os.sep, ".")[:-3]

                    try:
                        module = importlib.import_module(module_path)
                        if hasattr(module, "router"):
                            app.include_router(module.router)
                            logging.info(
                                f"Added router from specified extension: {extension_name} - {module_path}"
                            )
                        else:
                            logging.debug(
                                f"Extension module {module_path} has no router attribute"
                            )
                    except Exception as e:
                        logging.error(
                            f"Error importing router from extension {extension_name}: {str(e)}",
                            exc_info=True,
                        )
                        # Don't raise, just log the error to avoid breaking startup for one extension issue
                        logging.debug("Continuing with other extensions...")
        except Exception as e:
            logging.error(
                f"Error loading extensions from APP_EXTENSIONS: {str(e)}",
                exc_info=True,
            )
            # Continue loading the regular endpoints instead of raising an exception

    # Process EP_ modules
    for module_path in ep_modules:
        # Extract the module name without .py extension from the full path
        module_name = os.path.basename(module_path)[:-3]  # Remove .py extension

        # Skip modules with names ending in _test
        if module_name.endswith("_test"):
            logging.debug(f"Skipping test module: {module_name}")
            continue

        # Get base module prefix for proper imports
        base_module_prefix = __name__.rsplit(".", 1)[0] if "." in __name__ else ""
        module_import_path = (
            f"{base_module_prefix}.endpoints.{module_name}"
            if base_module_prefix
            else f"endpoints.{module_name}"
        )

        # Import the module dynamically
        try:
            module = importlib.import_module(module_import_path)

            # Check if the module has a 'router' attribute
            if hasattr(module, "router"):
                # Include the router in our app
                app.include_router(module.router)
                logging.info(f"Added router from {module_name}")
            else:
                logging.debug(f"Module {module_name} does not have a router attribute")
        except Exception as e:
            logging.error(
                f"Error importing router from {module_name}: {str(e)}", exc_info=True
            )
            raise e

    @app.get("/health", tags=["Health"])
    async def health():
        return {"status": "UP"}

    # Set up GraphQL
    graphql_app = GraphQLRouter(schema=schema, debug=True)
    app.include_router(graphql_app, prefix="/graphql")
    logging.debug("==== REGISTERED ROUTES ====")
    for route in app.routes:
        logging.debug(
            f"Route: {route.path}, methods: {route.methods if hasattr(route, 'methods') else 'N/A'}"
        )
    logging.debug("==========================")
    return app


def setup_virtualenv():
    """Create a virtual environment if it doesn't exist and install requirements"""
    # Get paths
    current_file_path = Path(__file__).resolve()
    src_dir = current_file_path.parent
    root_dir = src_dir.parent
    venv_dir = root_dir / "venv"
    requirements_file = root_dir / "requirements.txt"

    # Check if we're already in a virtual environment
    if sys.prefix != sys.base_prefix:
        logging.info("Already running in a virtual environment")
        return True

    # Check if virtual environment exists
    if venv_dir.exists():
        logging.info(f"Virtual environment already exists at {venv_dir}")
    else:
        # Create virtual environment
        logging.info(f"Creating virtual environment at {venv_dir}")
        try:
            venv.create(venv_dir, with_pip=True)
        except Exception as e:
            logging.error(f"Failed to create virtual environment: {e}")
            return False

    # Check if requirements file exists
    if not requirements_file.exists():
        logging.warning(f"Requirements file not found at {requirements_file}")
        return True

    # Install requirements
    logging.info("Installing requirements...")

    # Get path to pip in the virtual environment
    if os.name == "nt":  # Windows
        pip_path = venv_dir / "Scripts" / "pip"
    else:  # Unix/Linux/Mac
        pip_path = venv_dir / "bin" / "pip"

    # Install requirements using the virtual environment's pip
    try:
        subprocess.check_call([str(pip_path), "install", "-r", str(requirements_file)])
        logging.info("Requirements installed successfully")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to install requirements: {e}")
        return False

    # Re-execute this script with the virtual environment's Python
    if os.name == "nt":  # Windows
        python_path = venv_dir / "Scripts" / "python"
    else:  # Unix/Linux/Mac
        python_path = venv_dir / "bin" / "python"

    logging.info(f"Restarting with virtual environment's Python at {python_path}")
    try:
        os.execl(str(python_path), str(python_path), *sys.argv)
    except Exception as e:
        logging.error(f"Failed to restart with virtual environment: {e}")
        return False

    return True  # This line won't be reached if exec succeeds


if __name__ == "__main__":
    # Setup enhanced logging
    # setup_enhanced_logging()

    # Setup virtual environment if needed
    if setup_virtualenv():
        # Run database setup once in parent process
        setup_database()

        # Import extension endpoints
        import_extension_endpoints()

        # Seed data if needed
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
