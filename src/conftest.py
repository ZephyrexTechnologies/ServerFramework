import base64
import logging
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import bcrypt
import pytest
from faker import Faker
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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

# Setup paths correctly - follow Server.py pattern
src_path = Path(__file__).resolve().parent
project_root = src_path.parent

# Add project root and src directories to path
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

logger.debug(f"Added to sys.path: {src_path}, {project_root}")

from lib.Environment import env, push_env_update
from logic.BLL_Auth import RoleModel, TeamModel, UserModel, UserTeamModel


# IMPORTANT: Configure test environment BEFORE any imports from the application
def configure_test_environment():
    """Configure environment for testing with SQLite database"""
    logger.debug("Configuring test environment")

    # Get the original database name if it exists
    original_db_name = env("DATABASE_NAME")
    config_test_db_name = f"{original_db_name}.test"

    # Update environment variables using the new function
    push_env_update(
        {
            "DATABASE_TYPE": "sqlite",
            "DATABASE_NAME": config_test_db_name,
            "SEED_DATA": "true",
        }
    )

    # Delete existing test database if it exists (for clean start)
    db_file = f"{config_test_db_name}.db"
    for check_path in [
        ".",  # Current directory
        str(project_root),  # Project root
        str(src_path),  # src directory
        os.path.join(project_root, "instance"),  # Instance folder
    ]:
        test_db_path = os.path.join(check_path, db_file)
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
                logger.debug(f"Deleted existing test database: {test_db_path}")
            except Exception as e:
                logger.error(f"Failed to delete database file {test_db_path}: {e}")

    logger.debug(f"Set DATABASE_TYPE=sqlite, DATABASE_NAME={config_test_db_name}")
    return config_test_db_name


# Function to modify alembic.ini (Helper)
def modify_alembic_ini(db_name):
    """Update alembic.ini to use the test database"""
    logger.debug(f"Modifying alembic.ini to use database: {db_name}")
    ini_path = Path(project_root / "alembic.ini").absolute()

    if not ini_path.exists():
        logger.error(f"alembic.ini not found at {ini_path}")
        return False

    try:
        with open(ini_path, "r") as f:
            ini_contents = f.readlines()

        # Find and replace the sqlalchemy.url line
        for i, line in enumerate(ini_contents):
            if line.strip().startswith("sqlalchemy.url ="):
                # Replace with test database URL
                test_db_url = f"sqlalchemy.url = sqlite:///{db_name}.db\n"
                ini_contents[i] = test_db_url
                logger.debug(f"Updated sqlalchemy.url to: {test_db_url.strip()}")
                break

        # Write the modified content back
        with open(ini_path, "w") as f:
            f.writelines(ini_contents)

        logger.debug(f"Successfully modified {ini_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to modify alembic.ini: {e}", exc_info=True)
        return False


# Import all required functions from Server directly
from app import (
    create_app,
    import_all_db_models,
    import_extension_endpoints,
    import_extension_models,
    seed_data,
    setup_python_path,
)
from database.Base import get_session
from database.DB_Auth import Role, Team, User, UserCredential, UserTeam

# Configure environment before importing any application code
test_db_name = configure_test_environment()

# Now import the application creation function


# Add mocker fixture for tests that use mock functionality
@pytest.fixture
def mocker():
    """
    Simple mock fixture to replace pytest-mock dependency.
    Provides basic mock functionality for tests.
    """

    class SimpleMocker:
        def patch(self, *args, **kwargs):
            """Create a MagicMock and pass through args"""
            patcher = MagicMock()
            patcher.return_value = MagicMock()
            return patcher

        def patch_object(self, target, attribute, **kwargs):
            """Patch an object's attribute with a mock"""
            if hasattr(target, attribute):
                original = getattr(target, attribute)
                mock = MagicMock()
                for key, value in kwargs.items():
                    setattr(mock, key, value)
                setattr(target, attribute, mock)
                yield mock
                setattr(target, attribute, original)
            else:
                mock = MagicMock()
                for key, value in kwargs.items():
                    setattr(mock, key, value)
                setattr(target, attribute, mock)
                yield mock
                delattr(target, attribute)

    return SimpleMocker()


# First, store original environment variables before loading .env
original_env = {}
for key in ["DATABASE_TYPE", "DATABASE_NAME"]:
    if key in os.environ:
        original_env[key] = os.environ[key]

# Setup paths correctly - follow Server.py pattern
src_path = Path(__file__).resolve().parent
project_root = src_path.parent

# Add project root and src directories to path
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

logger.debug(f"Added to sys.path: {src_path}, {project_root}")

# Import Environment after path setup
from lib.Environment import env, push_env_update


# IMPORTANT: Configure test environment BEFORE any imports from the application
def configure_test_environment():
    """Configure environment for testing with SQLite database"""
    logger.debug("Configuring test environment")

    # Get the original database name if it exists
    original_db_name = env("DATABASE_NAME")
    config_test_db_name = f"{original_db_name}.test"

    # Update environment variables using the new function
    push_env_update(
        {
            "DATABASE_TYPE": "sqlite",
            "DATABASE_NAME": config_test_db_name,
            "SEED_DATA": "true",
        }
    )

    # Delete existing test database if it exists (for clean start)
    db_file = f"{config_test_db_name}.db"
    for check_path in [
        ".",  # Current directory
        str(project_root),  # Project root
        str(src_path),  # src directory
        os.path.join(project_root, "instance"),  # Instance folder
    ]:
        test_db_path = os.path.join(check_path, db_file)
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
                logger.debug(f"Deleted existing test database: {test_db_path}")
            except Exception as e:
                logger.error(f"Failed to delete database file {test_db_path}: {e}")

    logger.debug(f"Set DATABASE_TYPE=sqlite, DATABASE_NAME={config_test_db_name}")
    return config_test_db_name


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

    # Update alembic.ini for testing
    logger.debug("Modifying alembic.ini for testing...")
    if not modify_alembic_ini(current_db_name):
        logger.error("Failed to modify alembic.ini")
        raise Exception("Failed to modify alembic.ini for testing")

    # Follow the same initialization process as app.py
    logger.debug("Setting up Python path...")
    setup_python_path()

    logger.debug("Importing all database models...")
    import_all_db_models()

    logger.debug("Importing extension models...")
    import_extension_models()

    # Use run_all_migrations correctly, just like app.py
    from database.migrations.Migration import run_all_migrations

    logger.debug("Running migrations...")
    migration_result = run_all_migrations("upgrade", "head")
    if not migration_result:
        logger.warning("Some migrations failed to apply, but continuing with tests")
        # Check if we still have the core migrations applied
        from sqlalchemy import inspect

        from database.Base import engine

        inspector = inspect(engine)
        # Check for some critical tables
        core_tables = ["users", "roles", "teams"]
        missing_core_tables = [t for t in core_tables if not inspector.has_table(t)]
        if missing_core_tables:
            logger.error(f"Critical core tables are missing: {missing_core_tables}")
            raise Exception("Failed to apply core migrations - missing critical tables")
        logger.debug(
            "Core tables exist, proceeding with tests despite extension migration failures"
        )
    else:
        logger.debug("Successfully applied all migrations")

    logger.debug("Importing extension endpoints...")
    import_extension_endpoints()

    # Rebuild GraphQL schema after importing extension endpoints
    from lib.Pydantic2Strawberry import build_dynamic_strawberry_types

    try:
        logger.debug("Rebuilding GraphQL schema for tests...")
        # Rebuild with max_recursion_depth=3 to ensure deep relationships are properly included
        build_dynamic_strawberry_types(max_recursion_depth=3)
        logger.debug("GraphQL schema rebuilt successfully for tests")
    except Exception as e:
        logger.error(f"Error rebuilding GraphQL schema: {str(e)}", exc_info=True)

    # Check if the database file was created correctly
    db_file = f"{current_db_name}.db"
    db_paths = []
    for check_path in [
        ".",  # Current directory
        str(project_root),  # Project root
        str(src_path),  # src directory
        os.path.join(project_root, "instance"),  # Instance folder
    ]:
        test_db_path = os.path.join(check_path, db_file)
        if os.path.exists(test_db_path):
            db_paths.append(test_db_path)
            logger.debug(f"Found database file at: {test_db_path}")

    if not db_paths:
        logger.error(f"No database file was created after migrations")

    # Double check we're still using the test database
    logger.debug(f"DATABASE_NAME before seeding: {env('DATABASE_NAME')}")

    try:
        logger.debug("Starting data seeding...")
        seed_data()
        logger.debug("Finished seeding data successfully")
    except Exception as e:
        logger.error(f"Error in seeding data: {str(e)}", exc_info=True)
        raise

    seed_data()

    logger.debug("Database setup complete")

    # Provide the fixture
    yield

    # Teardown: restore alembic.ini and delete the test database
    cleanup_test_database(test_db_name)


@pytest.fixture(scope="session")
def db_session(db):
    """Get a database session for testing"""
    session = get_session()
    yield session
    session.close()


@pytest.fixture(scope="session")
def server(db):
    """Get a server for testing"""
    logger.debug("Creating test client!")
    return TestClient(create_app())


def generate_test_email(prefix="test"):
    """Generate a unique test email using Faker"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"


def create_user(
    db_session: Session,
    email=None,
    password="testpassword",
    first_name="Test",
    last_name="User",
):
    """Helper function to create a test user and their credentials"""
    user = User.create(
        requester_id=env("SYSTEM_ID"),
        db=db_session,
        return_type="dto",
        override_dto=UserModel,
        email=generate_test_email(),
        username=email.split("@")[0],
        first_name=first_name,
        last_name=last_name,
        display_name=f"{first_name} {last_name} Display",
    )
    if password:
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode(), salt).decode()
        password_salt = salt.decode()

        UserCredential.create(
            requester_id=user.id,
            db=db_session,
            user_id=user.id,
            password_hash=password_hash,
            password_salt=password_salt,
        )
    return user


def authorize_user(server, email: str, password="testpassword"):
    credentials = f"{email}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    response = server.post(
        "/v1/user/authorize", headers={"Authorization": f"Basic {encoded_credentials}"}
    )
    assert "token" in response.json(), "JWT token missing from authorization response."
    return response.json()["token"]


def create_team(db_session: Session, user_id, name="Test Team", parent_id=None):
    """Helper function to create a test team"""
    faker = Faker()
    team = Team.create(
        requester_id=user_id,
        db=db_session,
        return_type="dto",
        override_dto=TeamModel,
        name=name,
        description=faker.catch_phrase(),
        encryption_key=faker.uuid4(),
        created_by_user_id=user_id,
        parent_id=parent_id,
    )
    add_user_to_team(
        db_session,
        user_id,
        team.id,
        env("ADMIN_ROLE_ID"),
    )
    return team


def create_role(
    db_session: Session,
    user_id,
    team_id,
    name="mod",
    friendly_name="Moderator",
    parent_id=env("USER_ROLE_ID"),
):
    """Helper function to create a custom role"""
    return Role.create(
        requester_id=user_id,
        db=db_session,
        return_type="dto",
        override_dto=RoleModel,
        name=name,
        friendly_name=friendly_name,
        parent_id=parent_id,
        team_id=team_id,
    )


def add_user_to_team(db_session: Session, user_id, team_id, role_id):
    """Add a user to a team with the specified role"""
    # TODO Add logic to automatically set the creator ID back to the user after this is created for the initial user in a team otherwise they can't leave.
    return UserTeam.create(
        requester_id=env("SYSTEM_ID"),
        db=db_session,
        return_type="dto",
        override_dto=UserTeamModel,
        user_id=user_id,
        team_id=team_id,
        role_id=role_id,
    )


@pytest.fixture(scope="session")
def admin_a(db_session):
    """Admin user for team_a"""
    return create_user(
        db_session,
        email=generate_test_email("admin_a"),
        last_name="AdminA",
    )


@pytest.fixture(scope="session")
def admin_a_jwt(server, admin_a):
    return authorize_user(server, admin_a.email)


@pytest.fixture(scope="session")
def team_a(db_session, admin_a):
    """Create team_a for testing"""
    return create_team(db_session, admin_a.id, name="Team A")


# FIXME Restructure these to follow the above example, they're set up to test permissions but are being created all wonky.
# @pytest.fixture(scope="session")
# def team_b(db_session):
#     """Create team_b for testing"""
#     return create_team(db_session, name="Team B", created_by_user_id=env("SYSTEM_ID"))


# @pytest.fixture(scope="session")
# def mod_b_role(db_session, team_b):
#     """Create team-scoped moderator role for team_b"""
#     return create_role(
#         db_session,
#         name="moderator_b",
#         friendly_name="Team B Moderator",
#         parent_id=env("USER_ROLE_ID"),
#         team_id=team_b.id,
#         created_by_user_id=env("SYSTEM_ID"),
#     )


# @pytest.fixture(scope="session")
# def admin_b(db_session, team_b):
#     """Admin user for team_b"""
#     user = create_user(
#         db_session,
#         email=generate_test_email("admin_b"),
#         first_name="Admin",
#         last_name="B",
#         created_by_user_id=env("SYSTEM_ID"),
#         password="testpassword",
#     )
#     add_user_to_team(
#         db_session,
#         user.id,
#         team_b.id,
#         env("ADMIN_ROLE_ID"),
#         created_by_user_id=env("SYSTEM_ID"),
#     )
#     return user


# @pytest.fixture(scope="session")
# def user_b(db_session, team_b):
#     """Regular user for team_b"""
#     user = create_user(
#         db_session,
#         email=generate_test_email("user_b"),
#         first_name="User",
#         last_name="B",
#         created_by_user_id=env("SYSTEM_ID"),
#         password="testpassword",
#     )
#     add_user_to_team(
#         db_session,
#         user.id,
#         team_b.id,
#         env("USER_ROLE_ID"),
#         created_by_user_id=env("SYSTEM_ID"),
#     )
#     return user


# @pytest.fixture(scope="session")
# def mod_b(db_session, team_b, mod_b_role):
#     """Moderator user for team_b"""
#     user = create_user(
#         db_session,
#         email=generate_test_email("mod_b"),
#         first_name="Mod",
#         last_name="B",
#         created_by_user_id=env("SYSTEM_ID"),
#         password="testpassword",
#     )
#     add_user_to_team(
#         db_session,
#         user.id,
#         team_b.id,
#         mod_b_role.id,
#         created_by_user_id=env("SYSTEM_ID"),
#     )
#     return user


# @pytest.fixture(scope="session")
# def team_p(db_session):
#     """Create parent team_p for testing"""
#     return create_team(
#         db_session, name="Team Parent", created_by_user_id=env("SYSTEM_ID")
#     )


# @pytest.fixture(scope="session")
# def admin_p(db_session, team_p):
#     """Admin user for parent team_p"""
#     user = create_user(
#         db_session,
#         email=generate_test_email("admin_p"),
#         first_name="Admin",
#         last_name="P",
#         created_by_user_id=env("SYSTEM_ID"),
#         password="testpassword",
#     )
#     add_user_to_team(
#         db_session,
#         user.id,
#         team_p.id,
#         env("ADMIN_ROLE_ID"),
#         created_by_user_id=env("SYSTEM_ID"),
#     )
#     return user


# @pytest.fixture(scope="session")
# def mod_p_role(db_session, team_p):
#     """Create team-scoped moderator role for team_p"""
#     return create_role(
#         db_session,
#         name="moderator_p",
#         friendly_name="Parent Team Moderator",
#         parent_id=env("USER_ROLE_ID"),
#         team_id=team_p.id,
#         created_by_user_id=env("SYSTEM_ID"),
#     )


# @pytest.fixture(scope="session")
# def mod_p(db_session, team_p, mod_p_role):
#     """Moderator user for parent team_p"""
#     user = create_user(
#         db_session,
#         email=generate_test_email("mod_p"),
#         first_name="Mod",
#         last_name="P",
#         created_by_user_id=env("SYSTEM_ID"),
#         password="testpassword",
#     )
#     add_user_to_team(
#         db_session,
#         user.id,
#         team_p.id,
#         mod_p_role.id,
#         created_by_user_id=env("SYSTEM_ID"),
#     )
#     return user


# @pytest.fixture(scope="session")
# def user_p(db_session, team_p):
#     """Regular user for parent team_p"""
#     user = create_user(
#         db_session,
#         email=generate_test_email("user_p"),
#         first_name="User",
#         last_name="P",
#         created_by_user_id=env("SYSTEM_ID"),
#         password="testpassword",
#     )
#     add_user_to_team(
#         db_session,
#         user.id,
#         team_p.id,
#         env("USER_ROLE_ID"),
#         created_by_user_id=env("SYSTEM_ID"),
#     )
#     return user


# @pytest.fixture(scope="session")
# def team_c(db_session, team_p):
#     """Create child team_c that belongs to parent team_p"""
#     return create_team(
#         db_session,
#         name="Team Child",
#         parent_id=team_p.id,
#         created_by_user_id=env("SYSTEM_ID"),
#     )


# @pytest.fixture(scope="session")
# def mod_c_role(db_session, team_c):
#     """Create team-scoped moderator role for team_c"""
#     return create_role(
#         db_session,
#         name="moderator_c",
#         friendly_name="Child Team Moderator",
#         parent_id=env("USER_ROLE_ID"),
#         team_id=team_c.id,
#         created_by_user_id=env("SYSTEM_ID"),
#     )


# @pytest.fixture(scope="session")
# def admin_c(db_session, team_c):
#     """Admin user for child team_c"""
#     user = create_user(
#         db_session,
#         email=generate_test_email("admin_c"),
#         first_name="Admin",
#         last_name="C",
#         created_by_user_id=env("SYSTEM_ID"),
#         password="testpassword",
#     )
#     add_user_to_team(
#         db_session,
#         user.id,
#         team_c.id,
#         env("ADMIN_ROLE_ID"),
#         created_by_user_id=env("SYSTEM_ID"),
#     )
#     return user


# @pytest.fixture(scope="session")
# def mod_c(db_session, team_c, mod_c_role):
#     """Moderator user for child team_c"""
#     user = create_user(
#         db_session,
#         email=generate_test_email("mod_c"),
#         first_name="Mod",
#         last_name="C",
#         created_by_user_id=env("SYSTEM_ID"),
#         password="testpassword",
#     )
#     add_user_to_team(
#         db_session,
#         user.id,
#         team_c.id,
#         mod_c_role.id,
#         created_by_user_id=env("SYSTEM_ID"),
#     )
#     return user


# @pytest.fixture(scope="session")
# def user_c(db_session, team_c):
#     """Regular user for child team_c"""
#     user = create_user(
#         db_session,
#         email=generate_test_email("user_c"),
#         first_name="User",
#         last_name="C",
#         created_by_user_id=env("SYSTEM_ID"),
#         password="testpassword",
#     )
#     add_user_to_team(
#         db_session,
#         user.id,
#         team_c.id,
#         env("USER_ROLE_ID"),
#         created_by_user_id=env("SYSTEM_ID"),
#     )
#     return user


# @pytest.fixture(scope="session")
# def all_test_users(
#     admin_a, admin_b, user_b, mod_b, admin_p, mod_p, user_p, admin_c, mod_c, admin_a
# ):
#     """Return all test users for convenience"""
#     return {
#         "admin_a": admin_a,
#         "admin_b": admin_b,
#         "user_b": user_b,
#         "mod_b": mod_b,
#         "admin_p": admin_p,
#         "mod_p": mod_p,
#         "user_p": user_p,
#         "admin_c": admin_c,
#         "mod_c": mod_c,
#         "user_c": admin_a,
#     }


# @pytest.fixture(scope="session")
# def all_test_teams(team_a, team_b, team_p, team_c):
#     """Return all test teams for convenience"""
#     return {"team_a": team_a, "team_b": team_b, "team_p": team_p, "team_c": team_c}


# @pytest.fixture(scope="session")
# def all_custom_roles(mod_b_role, mod_p_role, mod_c_role):
#     """Return all custom roles for convenience"""
#     return {
#         "mod_b_role": mod_b_role,
#         "mod_p_role": mod_p_role,
#         "mod_c_role": mod_c_role,
#     }


# endregion


# region -- Test Fixtures --
def cleanup_test_database(db_name):
    """Clean up the test database after tests are complete"""
    try:
        # Restore original alembic.ini settings
        ini_path = Path(project_root / "alembic.ini").absolute()
        if ini_path.exists():
            # Get original database name without .test suffix
            original_db_name = db_name.replace(".test", "")
            with open(ini_path, "r") as f:
                ini_contents = f.readlines()

            # Find and replace the sqlalchemy.url line
            for i, line in enumerate(ini_contents):
                if line.strip().startswith("sqlalchemy.url ="):
                    # Replace with original database URL
                    original_db_url = (
                        f"sqlalchemy.url = sqlite:///{original_db_name}.db\n"
                    )
                    ini_contents[i] = original_db_url
                    logger.debug(
                        f"Restored sqlalchemy.url to: {original_db_url.strip()}"
                    )
                    break

            # Write the restored content back
            with open(ini_path, "w") as f:
                f.writelines(ini_contents)

            logger.debug(f"Successfully restored {ini_path}")

        logger.debug(f"Starting database cleanup for {db_name}")

        # For SQLite, find and delete the database file
        if env("DATABASE_TYPE") == "sqlite":
            db_file = f"{db_name}.db"
            deleted_count = 0

            # Check multiple possible locations
            for check_path in [
                ".",  # Current directory
                str(project_root),  # Project root
                str(src_path),  # src directory
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


def restore_environment():
    """Restore original environment variables when done"""
    for env_key, value in original_env.items():
        os.environ[env_key] = value
    logger.debug("Restored original environment variables")
