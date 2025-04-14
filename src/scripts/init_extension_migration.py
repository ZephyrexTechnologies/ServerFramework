#!/usr/bin/env python
"""
Script to initialize a migration structure for an extension
and create the initial migration.

Usage:
    python src/scripts/init_extension_migration.py extension_name
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def setup_python_path():
    """
    Setup the Python path to allow importing from the project
    """
    # Get the absolute path of the current file
    current_file_path = Path(__file__).resolve()
    # Get scripts directory (where this file is)
    scripts_dir = current_file_path.parent
    # Get src directory (parent of scripts)
    src_dir = scripts_dir.parent
    # Get root directory (parent of src)
    root_dir = src_dir.parent

    # Add to Python path if not already there
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    return {
        "scripts_dir": scripts_dir,
        "src_dir": src_dir,
        "root_dir": root_dir,
    }


def ensure_extension_directory(extension_name, src_dir):
    """
    Ensure the extension directory exists

    Args:
        extension_name: Name of the extension
        src_dir: Source directory path

    Returns:
        Path to extension directory
    """
    extension_dir = src_dir / "extensions" / extension_name

    if not extension_dir.exists():
        extension_dir.mkdir(parents=True)
        logging.info(f"Created extension directory at {extension_dir}")

        # Create __init__.py in extension directory
        init_file = extension_dir / "__init__.py"
        with open(init_file, "w") as f:
            f.write(f'"""Extension: {extension_name}"""\n')
        logging.info(f"Created {init_file}")
    else:
        logging.info(f"Extension directory already exists at {extension_dir}")

    return extension_dir


def update_extension_config(extension_name, src_dir):
    """
    Update the migration_extensions.json file to include the extension

    Args:
        extension_name: Name of the extension
        src_dir: Source directory path

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        import json

        config_file = src_dir / "database" / "migrations" / "migration_extensions.json"

        if not config_file.exists():
            logging.error(f"Config file not found at {config_file}")
            return False

        # Read existing config
        with open(config_file, "r") as f:
            config = json.load(f)

        # Check if extension is already included
        extensions = config.get("extensions", [])
        if extension_name in extensions:
            logging.info(f"Extension {extension_name} already in configuration")
            return True

        # Add extension to the list
        extensions.append(extension_name)
        config["extensions"] = extensions

        # Write updated config
        with open(config_file, "w") as f:
            json.dump(config, f, indent=4)

        logging.info(f"Added extension {extension_name} to migration_extensions.json")
        return True
    except Exception as e:
        logging.error(f"Error updating extension config: {e}")
        return False


def ensure_migrations_dir(extension_dir):
    """
    Create the migrations directory structure for an extension

    Args:
        extension_dir: Path to extension directory

    Returns:
        tuple: (migrations_dir, versions_dir)
    """
    migrations_dir = extension_dir / "migrations"
    versions_dir = migrations_dir / "versions"

    # Create directories
    if not migrations_dir.exists():
        migrations_dir.mkdir()
        logging.info(f"Created migrations directory at {migrations_dir}")

    if not versions_dir.exists():
        versions_dir.mkdir()
        logging.info(f"Created versions directory at {versions_dir}")

    # Create __init__.py files
    (migrations_dir / "__init__.py").touch(exist_ok=True)
    (versions_dir / "__init__.py").touch(exist_ok=True)

    return migrations_dir, versions_dir


def create_sample_model(extension_name, extension_dir):
    """
    Create a sample DB model file for the extension

    Args:
        extension_name: Name of the extension
        extension_dir: Path to extension directory

    Returns:
        bool: True if successful, False otherwise
    """
    model_file = extension_dir / f"DB_{extension_name.capitalize()}.py"

    # Don't overwrite existing model file
    if model_file.exists():
        logging.info(f"Model file already exists at {model_file}")
        return True

    try:
        with open(model_file, "w") as f:
            f.write(
                f'''"""
Database models for the {extension_name} extension.
"""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database.Base import Base
from database.Mixins import BaseMixin


class {extension_name.capitalize()}Item(Base, BaseMixin):
    """
    Example item model for the {extension_name} extension.
    """
    __tablename__ = "{extension_name}_items"
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Make sure extending existing tables works correctly
    __table_args__ = {{"extend_existing": True}}
'''
            )

        logging.info(f"Created sample model file at {model_file}")
        return True
    except Exception as e:
        logging.error(f"Error creating sample model file: {e}")
        return False


def run_migration_init(extension_name, root_dir):
    """
    Run the Migration.py init command to initialize the migration structure

    Args:
        extension_name: Name of the extension
        root_dir: Root directory path

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        migration_script = root_dir / "src" / "database" / "migrations" / "Migration.py"

        if not migration_script.exists():
            logging.error(f"Migration script not found at {migration_script}")
            return False

        cmd = [
            sys.executable,
            str(migration_script),
            "init",
            "--extension",
            extension_name,
        ]

        logging.info(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode == 0:
            logging.info(
                f"Successfully initialized migration structure for {extension_name}"
            )
            logging.info(result.stdout)
            return True
        else:
            logging.error(f"Failed to initialize migration structure: {result.stderr}")
            return False

    except Exception as e:
        logging.error(f"Error running migration init: {e}")
        return False


def create_initial_migration(extension_name, root_dir):
    """
    Create the initial migration for the extension

    Args:
        extension_name: Name of the extension
        root_dir: Root directory path

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        migration_script = root_dir / "src" / "database" / "migrations" / "Migration.py"

        if not migration_script.exists():
            logging.error(f"Migration script not found at {migration_script}")
            return False

        cmd = [
            sys.executable,
            str(migration_script),
            "revision",
            "--extension",
            extension_name,
            "-m",
            f"Initial {extension_name} migration",
            "--auto",
        ]

        logging.info(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode == 0:
            logging.info(f"Successfully created initial migration for {extension_name}")
            logging.info(result.stdout)
            return True
        else:
            logging.error(f"Failed to create initial migration: {result.stderr}")
            return False

    except Exception as e:
        logging.error(f"Error creating initial migration: {e}")
        return False


def apply_migration(extension_name, root_dir):
    """
    Apply the migration for the extension

    Args:
        extension_name: Name of the extension
        root_dir: Root directory path

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        migration_script = root_dir / "src" / "database" / "migrations" / "Migration.py"

        if not migration_script.exists():
            logging.error(f"Migration script not found at {migration_script}")
            return False

        cmd = [
            sys.executable,
            str(migration_script),
            "upgrade",
            "--extension",
            extension_name,
        ]

        logging.info(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode == 0:
            logging.info(f"Successfully applied migration for {extension_name}")
            logging.info(result.stdout)
            return True
        else:
            logging.error(f"Failed to apply migration: {result.stderr}")
            return False

    except Exception as e:
        logging.error(f"Error applying migration: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Initialize extension migration structure"
    )
    parser.add_argument("extension_name", help="Name of the extension")
    parser.add_argument(
        "--skip-model", action="store_true", help="Skip creating sample model"
    )
    parser.add_argument(
        "--skip-apply", action="store_true", help="Skip applying migration"
    )

    args = parser.parse_args()

    extension_name = args.extension_name

    # Setup paths
    paths = setup_python_path()

    # Step 1: Ensure extension directory exists
    extension_dir = ensure_extension_directory(extension_name, paths["src_dir"])

    # Step 2: Update configuration to include the extension
    update_extension_config(extension_name, paths["src_dir"])

    # Step 3: Create sample model (if not skipped)
    if not args.skip_model:
        create_sample_model(extension_name, extension_dir)

    # Step 4: Initialize migration structure
    run_migration_init(extension_name, paths["root_dir"])

    # Step 5: Create initial migration
    create_initial_migration(extension_name, paths["root_dir"])

    # Step 6: Apply migration (if not skipped)
    if not args.skip_apply:
        apply_migration(extension_name, paths["root_dir"])

    logging.info(f"Extension {extension_name} setup complete!")
    logging.info(f"To create additional migrations, run:")
    logging.info(
        f'  python src/database/migrations/Migration.py revision --extension {extension_name} -m "Your message" --auto'
    )


if __name__ == "__main__":
    main()
