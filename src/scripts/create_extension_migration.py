#!/usr/bin/env python
"""
Demonstration script for creating a new extension with migrations.
This script:
1. Creates a new extension directory
2. Adds a sample DB_*.py file with table definitions
3. Creates and applies migrations for the new extension

Usage:
    python src/scripts/create_extension_migration.py extension_name
"""

import argparse
import subprocess
import sys
from pathlib import Path


def setup_python_path():
    """Set up Python path to include the project root"""
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


def create_extension_directory(extension_name, src_dir):
    """Create the extension directory structure"""
    extension_dir = src_dir / "extensions" / extension_name

    # Create main extension directory
    if extension_dir.exists():
        print(f"Extension directory {extension_dir} already exists")
        return extension_dir

    extension_dir.mkdir(exist_ok=True, parents=True)

    # Create __init__.py
    with open(extension_dir / "__init__.py", "w") as f:
        f.write(f'"""Extension: {extension_name}"""\n')

    print(f"Created extension directory: {extension_dir}")
    return extension_dir


def create_db_file(extension_dir, extension_name):
    """Create a sample DB_*.py file with table definitions"""
    db_file_path = extension_dir / f"DB_{extension_name.capitalize()}.py"

    # Don't overwrite existing file
    if db_file_path.exists():
        print(f"DB file {db_file_path} already exists, not overwriting")
        return db_file_path

    # Create the file with example table definitions
    with open(db_file_path, "w") as f:
        f.write(
            f'''"""
Database models for the {extension_name} extension.
"""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database.Base import Base
from database.DB_Auth import UserRefMixin
from database.Mixins import BaseMixin, UpdateMixin


class {extension_name.capitalize()}Item(Base, BaseMixin, UpdateMixin, UserRefMixin):
    """
    Represents an item in the {extension_name} extension.
    """
    __tablename__ = "{extension_name}_items"
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Make sure extending existing tables works correctly
    __table_args__ = {{"extend_existing": True}}


class {extension_name.capitalize()}Setting(Base, BaseMixin, UpdateMixin, UserRefMixin):
    """
    Settings for {extension_name} items.
    """
    __tablename__ = "{extension_name}_settings"
    
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=True)
    
    # Reference to the item
    item_id = Column(Integer, ForeignKey("{extension_name}_items.id"), nullable=False)
    item = relationship("{extension_name.capitalize()}Item", backref="{extension_name}_settings")
    
    # Make sure extending existing tables works correctly
    __table_args__ = {{"extend_existing": True}}
'''
        )

    print(f"Created DB file: {db_file_path}")
    return db_file_path


def update_extension_config(extension_name, src_dir):
    """Update the migration_extensions.json file to include the new extension"""
    config_path = src_dir / "database" / "migrations" / "migration_extensions.json"

    if not config_path.exists():
        print(f"Configuration file {config_path} not found")
        return False

    # Read the current config
    import json

    with open(config_path, "r") as f:
        config = json.load(f)

    # Check if extension is already in the list
    if extension_name in config.get("extensions", []):
        print(f"Extension {extension_name} already in configuration")
        return True

    # Add the extension to the list
    extensions = config.get("extensions", [])
    extensions.append(extension_name)
    config["extensions"] = extensions

    # Write the updated config
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)

    print(f"Updated configuration to include {extension_name}")
    return True


def create_migration(extension_name, root_dir):
    """Create a migration for the extension"""
    migration_script = root_dir / "src" / "database" / "migrations" / "Migration.py"

    if not migration_script.exists():
        print(f"Migration script {migration_script} not found")
        return False

    print(f"Creating migration for extension {extension_name}...")
    cmd = [
        sys.executable,
        str(migration_script),
        "revision",
        "--extension",
        extension_name,
        "-m",
        f"Initial {extension_name} extension setup",
        "--auto",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
        if result.stderr:
            print(f"Warnings/Errors: {result.stderr}")
        print(f"Successfully created migration for {extension_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to create migration: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False


def apply_migration(extension_name, root_dir):
    """Apply the migration for the extension"""
    migration_script = root_dir / "src" / "database" / "migrations" / "Migration.py"

    if not migration_script.exists():
        print(f"Migration script {migration_script} not found")
        return False

    print(f"Applying migration for extension {extension_name}...")
    cmd = [
        sys.executable,
        str(migration_script),
        "upgrade",
        "--extension",
        extension_name,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
        if result.stderr:
            print(f"Warnings/Errors: {result.stderr}")
        print(f"Successfully applied migration for {extension_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to apply migration: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Create a new extension with migrations"
    )
    parser.add_argument("extension_name", help="Name of the extension to create")
    parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help="Skip migration creation and application",
    )

    args = parser.parse_args()
    extension_name = args.extension_name

    # Setup paths
    paths = setup_python_path()

    # Create extension directory
    extension_dir = create_extension_directory(extension_name, paths["src_dir"])

    # Create DB file
    db_file_path = create_db_file(extension_dir, extension_name)

    # Update extension config
    update_extension_config(extension_name, paths["src_dir"])

    if not args.skip_migrate:
        # Create migration
        if create_migration(extension_name, paths["root_dir"]):
            # Apply migration
            apply_migration(extension_name, paths["root_dir"])

    print(f"\nExtension {extension_name} setup complete!")
    print(f"Extension directory: {extension_dir}")
    print(f"DB file: {db_file_path}")
    print(f"Add your extension code to {extension_dir}")
    print("To manually create migrations in the future, run:")
    print(
        f'  python src/database/migrations/Migration.py revision --extension {extension_name} -m "Your message" --auto'
    )


if __name__ == "__main__":
    main()
