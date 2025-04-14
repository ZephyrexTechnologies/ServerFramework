import glob
import importlib
import logging
import os
import sys
import tempfile

from sqlalchemy.orm import configure_mappers


def scoped_import(file_type="DB", scopes=["database", "extensions"]):
    """
    Safely import models with automatic dependency resolution

    Args:
        file_type: Prefix of the file name (e.g., "DB" for files starting with "DB_")
        scopes: List of relative module paths to search for files

    Returns:
        tuple: (imported_modules, import_errors)
            - imported_modules: List of successfully imported module names
            - import_errors: List of tuples (file_path, error_message) for failed imports
    """
    # Get the source directory (assuming it's the parent of the current file)
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Import the dependency analyzer
    sys.path.insert(0, os.path.join(src_dir, "lib"))
    try:
        import Dependencies
    except ImportError:
        # Create the lib directory if it doesn't exist
        lib_dir = os.path.join(src_dir, "lib")
        if not os.path.exists(lib_dir):
            os.makedirs(lib_dir)
            with open(os.path.join(lib_dir, "__init__.py"), "w") as f:
                f.write("# Package initialization file\n")

        # Copy the Dependencies.py file content to the lib directory
        dependencies_path = os.path.join(lib_dir, "Dependencies.py")
        with open(dependencies_path, "w") as f:
            # Insert the content of Dependencies.py here (will be auto-created if missing)
            logging.warning(
                f"Dependencies.py not found, creating it at {dependencies_path}"
            )

        # Try importing again
        import Dependencies

    # Dictionary to store files by scope
    files_by_scope = {}

    # Track already imported modules to prevent duplicates
    already_imported_modules = set()
    for module_name in sys.modules:
        if module_name.startswith("database.DB_") or module_name.startswith(
            "extensions."
        ):
            already_imported_modules.add(module_name)
            logging.info(f"Module already imported: {module_name}")

    # Expand "extensions" scope to include all extension subdirectories
    expanded_scopes = []
    for scope in scopes:
        if scope == "extensions":
            # Find all extension directories
            extensions_dir = os.path.join(src_dir, "extensions")
            if os.path.exists(extensions_dir) and os.path.isdir(extensions_dir):
                for ext_name in os.listdir(extensions_dir):
                    ext_path = os.path.join(extensions_dir, ext_name)
                    if os.path.isdir(ext_path):
                        expanded_scopes.append(f"extensions.{ext_name}")
        else:
            expanded_scopes.append(scope)

    # Find all Python files with the specified prefix in all scopes
    for scope in expanded_scopes:
        # Convert module path to directory path
        scope_dir = os.path.join(src_dir, *scope.split("."))

        # Create the pattern for files with the specified prefix
        files_pattern = os.path.join(scope_dir, f"{file_type}_*.py")

        # Get all matching files
        all_files = glob.glob(files_pattern)

        # Filter out test files
        matching_files = [
            f for f in all_files if not os.path.basename(f).endswith("_test.py")
        ]

        if matching_files:
            files_by_scope[scope] = matching_files
            logging.info(f"Found {len(matching_files)} {file_type} files in {scope}")

    if not files_by_scope:
        logging.warning(
            f"No {file_type} files found in any of the specified scopes: {scopes}, expanded to {expanded_scopes}"
        )
        return [], []

    # Build dependency graph and get ordered file list
    ordered_files, dependency_graph, module_to_file = (
        Dependencies.build_dependency_graph(files_by_scope)
    )

    # Log the determined order and dependencies
    logging.info("Automatically determined import order:")
    for i, file_path in enumerate(ordered_files):
        # Determine the module name based on the file path
        module_name = None
        for scope, files in files_by_scope.items():
            if file_path in files:
                module_name = f"{scope}.{os.path.basename(file_path)[:-3]}"
                break

        if module_name is None:
            # This should not happen if everything is working correctly
            module_name = f"unknown.{os.path.basename(file_path)[:-3]}"

        deps = dependency_graph.get(module_name, [])
        logging.info(
            f"{i+1}. {module_name} (depends on: {', '.join(deps) if deps else 'none'})"
        )

    # Track imported modules and errors
    imported_modules = []
    import_errors = []
    imported_file_paths = set()

    # Import modules in the determined order
    for file_path in ordered_files:
        # Skip if already imported
        if file_path in imported_file_paths:
            continue

        # Determine the module name and scope based on the file path
        module_name = None
        module_scope = None
        for scope, files in files_by_scope.items():
            if file_path in files:
                module_name = f"{scope}.{os.path.basename(file_path)[:-3]}"
                module_scope = scope
                break

        if module_name is None:
            # This should not happen if everything is working correctly
            module_name = f"unknown.{os.path.basename(file_path)[:-3]}"
            logging.warning(f"Could not determine module name for {file_path}")
            continue

        # Skip this module if it's already imported
        if module_name in already_imported_modules:
            logging.info(f"Skipping already imported module: {module_name}")
            imported_modules.append(module_name)
            imported_file_paths.add(file_path)
            continue

        try:
            logging.info(f"Importing {module_name}")

            # Check if we need to patch the module for extend_existing
            # NOTE: We only patch extension modules now, never core database modules
            patched_content, needs_patch = Dependencies.patch_module_content(file_path)

            # Use a temporary file if we've patched the content
            temp_file = None
            actual_file_path = file_path

            if needs_patch and patched_content:
                temp_file = tempfile.NamedTemporaryFile(suffix=".py", delete=False)
                temp_file.write(patched_content.encode("utf-8"))
                temp_file.close()
                actual_file_path = temp_file.name
                logging.info(
                    f"Using patched version of {module_name} with extend_existing=True"
                )

            # Check if core module is attempting to be re-imported
            if "database.DB_" in module_name and module_name in sys.modules:
                logging.info(f"Reusing already imported core module: {module_name}")
                module = sys.modules[module_name]
            else:
                # Import the module
                spec = importlib.util.spec_from_file_location(
                    module_name, actual_file_path
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

            # Register this module as imported
            already_imported_modules.add(module_name)

            # Tag tables with their module path for filtering in migrations
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                # Look for SQLAlchemy Table or declarative model classes
                if hasattr(attr, "__tablename__") and hasattr(attr, "__table__"):
                    # Add module_path to table.info
                    table = getattr(attr, "__table__")
                    if "info" not in table.__dict__:
                        table.info = {}
                    table.info["module_path"] = module_name

                    # For core database tables, make sure they have extend_existing=False
                    # This ensures no duplicates for core tables
                    if "database.DB_" in module_name and "extend_existing" not in str(
                        table.__dict__.get("__table_args__", "")
                    ):
                        if not hasattr(attr, "__table_args__"):
                            setattr(attr, "__table_args__", {})

                        # Make sure this doesn't cause a duplicate table error for core tables
                        attr.__table__.metadata._remove_table(
                            attr.__tablename__, attr.__table__.schema
                        )

            # Clean up temp file if we created one
            if temp_file:
                os.unlink(temp_file.name)

            imported_modules.append(module_name)
            imported_file_paths.add(file_path)
            logging.info(f"Successfully imported {module_name}")

        except Exception as e:
            import_errors.append((file_path, str(e)))
            logging.error(f"Error importing {file_path}: {e}")

    # Log summary
    if import_errors:
        logging.warning(f"Failed to import {len(import_errors)} model files:")
        for file_path, error in import_errors:
            logging.warning(f"  {file_path}: {error}")

    # Configure mappers to resolve any remaining issues
    try:
        configure_mappers()
    except Exception as e:
        logging.error(f"Error configuring mappers: {e}")

    return imported_modules, import_errors


def find_extension_db_files(extension_name):
    """
    Find all DB_*.py files for a specific extension

    Args:
        extension_name: Name of the extension

    Returns:
        list: List of file paths
    """
    # Get the source directory
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Get the extension directory
    ext_dir = os.path.join(src_dir, "extensions", extension_name)

    if not os.path.exists(ext_dir) or not os.path.isdir(ext_dir):
        logging.error(f"Extension directory not found: {ext_dir}")
        return []

    # Find all DB_*.py files
    files_pattern = os.path.join(ext_dir, "DB_*.py")
    all_files = glob.glob(files_pattern)

    # Filter out test files
    db_files = [f for f in all_files if not os.path.basename(f).endswith("_test.py")]

    return db_files
