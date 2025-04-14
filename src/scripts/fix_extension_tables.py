#!/usr/bin/env python
"""
Script to fix extension database tables by adding extend_existing=True to all table definitions.
This helps prevent duplicate table errors when extensions define tables that might conflict with core tables.

Usage:
    python src/scripts/fix_extension_tables.py
    python src/scripts/fix_extension_tables.py --extension <extension_name>
"""

import argparse
import glob
import re
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


def find_extension_db_files(src_dir, extension_name=None):
    """
    Find all DB_*.py files in extensions

    Args:
        src_dir: Path to src directory
        extension_name: Optional specific extension name

    Returns:
        List of DB file paths
    """
    extensions_dir = src_dir / "extensions"
    all_db_files = []

    if extension_name:
        # Only search in the specified extension
        ext_dir = extensions_dir / extension_name
        if ext_dir.exists() and ext_dir.is_dir():
            pattern = ext_dir / "DB_*.py"
            db_files = [Path(f) for f in glob.glob(str(pattern))]
            all_db_files.extend(db_files)
    else:
        # Search in all extensions
        for ext_dir in extensions_dir.iterdir():
            if ext_dir.is_dir():
                pattern = ext_dir / "DB_*.py"
                db_files = [Path(f) for f in glob.glob(str(pattern))]
                all_db_files.extend(db_files)

    return all_db_files


def add_extend_existing(file_path):
    """
    Add extend_existing=True to table definitions in a file

    Args:
        file_path: Path to the DB file

    Returns:
        bool: True if file was modified
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check if the file contains table definitions
    if "__tablename__" not in content:
        print(f"No table definitions found in {file_path}")
        return False

    # Check if extend_existing is already added
    if "extend_existing" in content:
        print(f"File {file_path} already has extend_existing")
        return False

    # Find all class definitions with __tablename__
    modified = False
    class_blocks = []

    # Pattern to match class definition followed by __tablename__
    class_pattern = r'class\s+([A-Za-z0-9_]+)\s*\([^)]*\):\s*(?:[^"]*?)__tablename__\s*=\s*(["\'])[^"\']*\2'
    for match in re.finditer(class_pattern, content, re.DOTALL):
        # Get start of the class
        class_start = match.start()
        # Get the text until __tablename__
        class_text = content[class_start : match.end()]
        class_blocks.append((class_start, class_text))

    # No class definitions with __tablename__ found
    if not class_blocks:
        print(f"No matching class definitions found in {file_path}")
        return False

    # Process the file content, adding __table_args__ where needed
    new_content = ""
    last_pos = 0

    for start, class_text in class_blocks:
        # Add text until this class
        new_content += content[last_pos:start]

        # Check if this class already has __table_args__
        if "__table_args__" in class_text:
            # Does it have a dictionary form?
            if re.search(r"__table_args__\s*=\s*{", class_text):
                # Add extend_existing to the dictionary
                modified_class = re.sub(
                    r"(__table_args__\s*=\s*{)",
                    r'\1"extend_existing": True, ',
                    class_text,
                )
            else:
                # Convert existing __table_args__ to include extend_existing
                modified_class = (
                    re.sub(
                        r"(__table_args__\s*=\s*)",
                        r'\1{"extend_existing": True, **',
                        class_text,
                    )
                    + "}"
                )
        else:
            # Add __table_args__ before __tablename__
            modified_class = re.sub(
                r"(\s*)(__tablename__)",
                r'\1__table_args__ = {"extend_existing": True}\n\1\2',
                class_text,
            )

        new_content += modified_class
        last_pos = start + len(class_text)
        modified = True

    # Add remaining text
    new_content += content[last_pos:]

    if modified:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Updated {file_path} to add extend_existing=True")

    return modified


def main():
    parser = argparse.ArgumentParser(
        description="Fix extension database tables by adding extend_existing=True"
    )
    parser.add_argument("--extension", help="Specific extension to process")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't modify files, just show what would be done",
    )

    args = parser.parse_args()

    paths = setup_python_path()
    db_files = find_extension_db_files(paths["src_dir"], args.extension)

    if not db_files:
        if args.extension:
            print(f"No DB files found in extension: {args.extension}")
        else:
            print("No DB files found in any extension")
        return

    print(f"Found {len(db_files)} DB files to check")

    modified_count = 0
    for file_path in db_files:
        try:
            if args.dry_run:
                print(f"Would check {file_path}")
            else:
                if add_extend_existing(file_path):
                    modified_count += 1
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    if args.dry_run:
        print(f"Dry run completed for {len(db_files)} files")
    else:
        print(f"Updated {modified_count} files to add extend_existing=True")


if __name__ == "__main__":
    main()
