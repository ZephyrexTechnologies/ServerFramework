import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, mock_open, patch

# Add parent directory to sys.path to import Import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.Import import (
    build_dependency_graph,
    encode,
    find_extension_db_files,
    jwt,
    parse_imports_and_dependencies,
    parse_module_ast,
    patch_module_content,
    resolve_dependency_conflicts,
    scoped_import,
)


class TestImport(unittest.TestCase):
    """Test suite for Import.py functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = self.temp_dir.name

        # Create test Python modules
        self.create_test_modules()

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def create_test_modules(self):
        """Create test Python modules for import testing."""
        # Module A - simple module with no dependencies
        module_a = """
class ClassA:
    def method_a(self):
        return "A"
"""
        # Module B - imports module A
        module_b = """
from module_a import ClassA

class ClassB:
    def __init__(self):
        self.a = ClassA()
    
    def method_b(self):
        return f"B uses {self.a.method_a()}"
"""
        # Module C - imports module B and has a circular dependency
        module_c = """
from module_b import ClassB
# This creates a circular dependency
import module_d

class ClassC:
    def __init__(self):
        self.b = ClassB()
    
    def method_c(self):
        return f"C uses {self.b.method_b()}"
"""
        # Module D - imports module C, creating a circular dependency
        module_d = """
from module_c import ClassC

class ClassD:
    def __init__(self):
        self.c = ClassC()
    
    def method_d(self):
        return f"D uses {self.c.method_c()}"
"""
        # Module with class-level forward references
        module_forward_ref = """
from typing import List, Optional

class ForwardRefUser:
    references: List["ForwardReference"]
    optional_ref: Optional["ForwardReference"]

class ForwardReference:
    name: str
    user: "ForwardRefUser"
"""
        # Module with DB_ prefix for testing scoped_import
        db_module = """
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)
"""

        # Create files
        files = {
            "module_a.py": module_a,
            "module_b.py": module_b,
            "module_c.py": module_c,
            "module_d.py": module_d,
            "module_forward_ref.py": module_forward_ref,
            "DB_User.py": db_module,
        }

        for filename, content in files.items():
            file_path = os.path.join(self.test_dir, filename)
            with open(file_path, "w") as f:
                f.write(content)

        # Create directory structure for scoped_import testing
        os.makedirs(os.path.join(self.test_dir, "database"), exist_ok=True)
        os.makedirs(
            os.path.join(self.test_dir, "extensions", "test_ext"), exist_ok=True
        )

        # Copy the DB module to the database directory
        with open(os.path.join(self.test_dir, "database", "DB_User.py"), "w") as f:
            f.write(db_module)

        # Create an extension module
        ext_module = """
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ExtensionModel(Base):
    __tablename__ = 'extension_models'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    user_id = Column(Integer, ForeignKey('users.id'))
"""
        with open(
            os.path.join(self.test_dir, "extensions", "test_ext", "DB_Extension.py"),
            "w",
        ) as f:
            f.write(ext_module)

    def test_encode(self):
        """Test encode function."""
        with patch("lib.Import.env", return_value="encoded_value") as mock_env:
            result = encode("test_arg")
            mock_env.assert_called_once_with("test_arg")
            self.assertEqual(result, "encoded_value")

    @patch(
        "builtins.open", new_callable=mock_open, read_data="class TestClass:\n    pass"
    )
    def test_parse_module_ast(self, mock_file):
        """Test parse_module_ast for a simple module."""
        file_path = "test_module.py"
        imports, import_froms, classes = parse_module_ast(file_path)

        mock_file.assert_called_once_with(file_path, "r", encoding="utf-8")
        self.assertEqual(imports, [])
        self.assertEqual(import_froms, [])
        self.assertEqual(classes, ["TestClass"])

    def test_parse_module_ast_with_imports(self):
        """Test parse_module_ast with imports and from imports."""
        # Define the file content with imports and classes
        file_content = """
import os
import sys
from datetime import datetime
from typing import List, Optional

class TestClass:
    pass

class AnotherClass:
    def method(self):
        pass
"""
        # Create a temp file to test with real content
        test_file_path = os.path.join(self.test_dir, "test_imports.py")
        with open(test_file_path, "w") as f:
            f.write(file_content)

        # Now test the real file
        imports, import_froms, classes = parse_module_ast(test_file_path)

        # Verify the results
        self.assertEqual(imports, ["os", "sys"])
        self.assertEqual(
            import_froms, ["datetime.datetime", "typing.List", "typing.Optional"]
        )
        self.assertEqual(classes, ["TestClass", "AnotherClass"])

    @patch("lib.Import.parse_module_ast")
    def test_parse_imports_and_dependencies(self, mock_parse):
        """Test parse_imports_and_dependencies."""
        # Mock the AST parse results
        mock_parse.return_value = (
            ["os", "sys"],
            ["sqlalchemy.Column", "sqlalchemy.String"],
            ["User", "Admin"],
        )

        file_path = os.path.join(self.test_dir, "DB_User.py")
        module_name, dependencies, defined_classes, imports = (
            parse_imports_and_dependencies(file_path, scope="database")
        )

        self.assertEqual(module_name, "database.DB_User")
        self.assertEqual(dependencies, {"sqlalchemy.Column", "sqlalchemy.String"})
        self.assertEqual(
            defined_classes, {"database.DB_User.User", "database.DB_User.Admin"}
        )
        self.assertEqual(imports, {"os", "sys"})

    def test_build_dependency_graph(self):
        """Test build_dependency_graph function."""
        # Create test files by scope
        files_by_scope = {
            "test": [
                os.path.join(self.test_dir, "module_a.py"),
                os.path.join(self.test_dir, "module_b.py"),
                os.path.join(self.test_dir, "module_c.py"),
                os.path.join(self.test_dir, "module_d.py"),
            ]
        }

        ordered_files, dependency_graph, module_to_file = build_dependency_graph(
            files_by_scope
        )

        # Verify the files are ordered correctly for dependencies
        self.assertEqual(len(ordered_files), 4)

        # The exact order might vary, but module_a should come before module_b
        module_a_index = ordered_files.index(os.path.join(self.test_dir, "module_a.py"))
        module_b_index = ordered_files.index(os.path.join(self.test_dir, "module_b.py"))
        self.assertLess(module_a_index, module_b_index)

        # Verify the dependency graph has all modules
        self.assertEqual(len(dependency_graph), 4)

        # Verify module_to_file mapping
        self.assertEqual(len(module_to_file), 4)
        self.assertEqual(
            module_to_file["test.module_a"], os.path.join(self.test_dir, "module_a.py")
        )

    @patch("lib.Import.glob.glob")
    @patch("lib.Import.build_dependency_graph")
    def test_scoped_import(self, mock_build_graph, mock_glob):
        """Test scoped_import function."""
        # Mock the glob results
        mock_glob.return_value = [os.path.join(self.test_dir, "database", "DB_User.py")]

        # Mock build_dependency_graph to return our test files
        mock_build_graph.return_value = (
            [os.path.join(self.test_dir, "database", "DB_User.py")],
            {"database.DB_User": set()},
            {"database.DB_User": os.path.join(self.test_dir, "database", "DB_User.py")},
        )

        # Mock for importlib
        with patch("importlib.util.spec_from_file_location") as mock_spec:
            mock_module = MagicMock()
            mock_spec.return_value = MagicMock()
            mock_spec.return_value.loader = MagicMock()

            # Test scoped_import with default params
            imported_modules, errors = scoped_import()

            # Check results
            self.assertEqual(len(errors), 0)
            mock_build_graph.assert_called_once()
            mock_spec.assert_called()

    def test_find_extension_db_files(self):
        """Test find_extension_db_files function."""
        # Mock test directory structure
        with patch("os.path.dirname") as mock_dirname:
            mock_dirname.return_value = self.test_dir

            with patch("glob.glob") as mock_glob:
                # Mock glob to return test files
                mock_glob.return_value = [
                    os.path.join(
                        self.test_dir, "extensions", "test_ext", "DB_Extension.py"
                    )
                ]

                # Test finding extension DB files
                result = find_extension_db_files("test_ext")

                self.assertEqual(len(result), 1)
                self.assertEqual(
                    result[0],
                    os.path.join(
                        self.test_dir, "extensions", "test_ext", "DB_Extension.py"
                    ),
                )

    def test_patch_module_content_no_patch_needed(self):
        """Test patch_module_content when no patch is needed."""
        # Create a file that doesn't need patching
        file_content = """
class TestModel:
    __tablename__ = 'test'
    __table_args__ = {'extend_existing': True}
"""
        file_path = os.path.join(self.test_dir, "no_patch_needed.py")
        with open(file_path, "w") as f:
            f.write(file_content)

        patched_content, needs_patch = patch_module_content(file_path)

        self.assertFalse(needs_patch)
        self.assertIsNone(patched_content)

    def test_patch_module_content_needs_patch(self):
        """Test patch_module_content when a patch is needed."""
        # Create a file that needs patching - has __tablename__ but no extend_existing
        file_content = """
class TestModel:
    __tablename__ = 'test'
"""
        file_path = os.path.join(self.test_dir, "extensions", "needs_patch.py")
        os.makedirs(os.path.join(self.test_dir, "extensions"), exist_ok=True)
        with open(file_path, "w") as f:
            f.write(file_content)

        patched_content, needs_patch = patch_module_content(file_path)

        self.assertTrue(needs_patch)
        self.assertIsNotNone(patched_content)
        self.assertIn("__table_args__ = {'extend_existing': True}", patched_content)

    def test_patch_module_content_with_existing_table_args(self):
        """Test patch_module_content with existing __table_args__."""
        # Create a file with __table_args__ but no extend_existing
        file_content = """
class TestModel:
    __tablename__ = 'test'
    __table_args__ = {
        'mysql_engine': 'InnoDB'
    }
"""
        file_path = os.path.join(self.test_dir, "extensions", "existing_args.py")
        os.makedirs(os.path.join(self.test_dir, "extensions"), exist_ok=True)
        with open(file_path, "w") as f:
            f.write(file_content)

        patched_content, needs_patch = patch_module_content(file_path)

        self.assertTrue(needs_patch)
        self.assertIsNotNone(patched_content)
        self.assertIn("__table_args__ = {'extend_existing': True,", patched_content)

    def test_resolve_dependency_conflicts(self):
        """Test resolve_dependency_conflicts function."""
        # Simple test for now, as function is a stub
        ordered_modules = ["module_a", "module_b", "module_c"]
        result = resolve_dependency_conflicts(ordered_modules)

        # Should return the same list for now
        self.assertEqual(result, ordered_modules)

    def test_jwt_decode(self):
        """Test JWT decode method."""
        # Mock the JSONWebToken.decode method
        with patch(
            "lib.Import.JSONWebToken.decode", return_value={"user": "test"}
        ) as mock_decode:
            result = jwt.decode("test_token", key="secret")

            mock_decode.assert_called_once_with("test_token", key="secret")
            self.assertEqual(result, {"user": "test"})

    def test_jwt_decode_with_validation(self):
        """Test JWT decode method with i and s parameters."""
        # Test the JWT validation logic
        with patch("lib.Import.r.get") as mock_get:
            # Mock HTTP request to return 200 (validation passes)
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            with patch(
                "lib.Import.JSONWebToken.decode", return_value={"data": "valid"}
            ) as mock_decode:
                result = jwt.decode("test_token", i=123, s="test", key="secret")

                mock_get.assert_called_once()
                mock_decode.assert_called_once()
                self.assertEqual(result, {"data": "valid"})

            # Test validation failure (403)
            mock_response.status_code = 403
            with self.assertRaises(Exception):
                jwt.decode("test_token", i=123, s="test", key="secret")


if __name__ == "__main__":
    unittest.main()
