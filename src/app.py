"""
FastAPI application factory and configuration.
"""

import glob
import importlib
import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

from database.Manager import DatabaseManager
from endpoints.GQL import schema

# from extensions.folder.EXT_Folder import WorkspaceManager
from lib.Environment import env
from lib.Logging import setup_enhanced_logging


def log_unhandled_exception(exc_type, exc_value, exc_traceback):
    """Log unhandled exceptions with full traceback"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


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
    setup_enhanced_logging()

    # Set up global exception handler
    sys.excepthook = log_unhandled_exception

    # Initialize managers
    # workspace_manager = WorkspaceManager()
    # task_monitor = TaskMonitorService()

    # Read version
    this_directory = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(this_directory, "version"), encoding="utf-8") as f:
        version = f.read().strip()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Handles startup and shutdown events for each worker"""
        # Initialize services
        # workspace_manager.start_file_watcher()
        db_manager.init_worker()  # Now the worker can initialize since config exists
        # await task_monitor.start()

        try:
            yield
        finally:
            # Cleanup services
            await db_manager.close_worker()
            # workspace_manager.stop_file_watcher()
            # await task_monitor.stop()

    # Initialize FastAPI application
    app = FastAPI(
        title=env("APP_NAME"),
        # TODO Fix the grammar for APP_DESCRIPTION's that don't start with a vowel.
        description=f"{env('APP_NAME')} is an {env('APP_DESCRIPTION')}. Visit the GitHub repo for more information or to report issues. {env('APP_REPOSITORY')}",
        version=version,
        docs_url="/",
        lifespan=lifespan,
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
    # Automatically discover and include all EP_ routers
    endpoints_dir = os.path.join(this_directory, "endpoints")
    ep_modules = glob.glob(os.path.join(endpoints_dir, "EP_*.py"))
    # TODO Replace this with scoped_import from lib/Imports
    for module_path in ep_modules:
        # Extract the module name without .py extension from the full path
        module_name = os.path.basename(module_path)[:-3]  # Remove .py extension

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
                logging.warning(
                    f"Module {module_name} does not have a router attribute"
                )
        except Exception as e:
            logging.error(
                f"Error importing router from {module_name}: {str(e)}", exc_info=True
            )

    @app.get("/health", tags=["Health"])
    async def health():
        return {"status": "UP"}

    # Set up GraphQL
    graphql_app = GraphQLRouter(
        schema=schema,
        subscription_protocols=["graphql-ws", "graphql-transport-ws"],
        graphql_ide=str(env("GRAPHIQL")).lower() == "true",
    )
    app.include_router(graphql_app, prefix="/graphql")
    logging.debug("==== REGISTERED ROUTES ====")
    for route in app.routes:
        logging.debug(
            f"Route: {route.path}, methods: {route.methods if hasattr(route, 'methods') else 'N/A'}"
        )
    logging.debug("==========================")
    return app
