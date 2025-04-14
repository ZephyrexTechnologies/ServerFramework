import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.DB_Agents import Agent

# Import database models and base
from database.DB_Auth import Role, Team, User, UserTeam
from database.DB_Providers import Provider, ProviderInstance
from database.migrations.MigrationHelper import check_and_apply_migrations


# Set up a test database
@pytest.fixture(scope="session")
def engine():
    """Create an in-memory SQLite database for tests."""
    # Use SQLite in-memory database for tests
    engine = create_engine("sqlite:///:memory:")
    check_and_apply_migrations()
    return engine


@pytest.fixture(scope="function")
def db_session(engine):
    """Create a new session for each test with transaction rollback."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    # Rollback transaction after test to clean up
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def system_user(db_session):
    """Create system user for tests."""
    system_id = env("SYSTEM_ID", "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF")
    user = db_session.query(User).filter(User.id == system_id).first()

    if not user:
        user = User(
            id=system_id,
            email="system@example.com",
            username="system",
            display_name="System User",
        )
        db_session.add(user)
        db_session.commit()

    return user


@pytest.fixture
def test_user(db_session):
    """Create a regular test user."""
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email="testuser@example.com",
        username="testuser",
        display_name="Test User",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def admin_user(db_session, admin_role):
    """Create an admin test user."""
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email="adminuser@example.com",
        username="adminuser",
        display_name="Admin User",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_team(db_session):
    """Create a test team."""
    team_id = str(uuid.uuid4())
    team = Team(id=team_id, name="Test Team", description="Test team description")
    db_session.add(team)
    db_session.commit()
    return team


@pytest.fixture
def user_role(db_session):
    """Create a user role."""
    role_id = str(uuid.uuid4())
    role = Role(id=role_id, name="user", friendly_name="User", parent_id=None)
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def admin_role(db_session, user_role):
    """Create an admin role that inherits from user role."""
    role_id = str(uuid.uuid4())
    role = Role(id=role_id, name="admin", friendly_name="Admin", parent_id=user_role.id)
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def team_with_user(db_session, test_team, test_user, user_role):
    """Create a team with a user as a member."""
    user_team = UserTeam(
        user_id=test_user.id, team_id=test_team.id, role_id=user_role.id, enabled=True
    )
    db_session.add(user_team)
    db_session.commit()
    return (test_team, test_user)


@pytest.fixture
def team_with_admin(db_session, test_team, admin_user, admin_role):
    """Create a team with an admin user as a member."""
    user_team = UserTeam(
        user_id=admin_user.id, team_id=test_team.id, role_id=admin_role.id, enabled=True
    )
    db_session.add(user_team)
    db_session.commit()
    return (test_team, admin_user)


@pytest.fixture
def test_provider(db_session):
    """Create a test provider."""
    provider_id = str(uuid.uuid4())
    provider = Provider(
        id=provider_id, name="Test Provider", agent_settings_json='{"key": "value"}'
    )
    db_session.add(provider)
    db_session.commit()
    return provider


@pytest.fixture
def test_provider_instance(db_session, test_provider, test_user):
    """Create a test provider instance for user."""
    instance_id = str(uuid.uuid4())
    instance = ProviderInstance(
        id=instance_id,
        name="Test Provider Instance",
        provider_id=test_provider.id,
        user_id=test_user.id,
        model_name="test-model",
        api_key="test-api-key",
    )
    db_session.add(instance)
    db_session.commit()
    return instance


@pytest.fixture
def test_agent(db_session, test_user):
    """Create a test agent."""
    agent_id = str(uuid.uuid4())
    agent = Agent(id=agent_id, name="Test Agent", user_id=test_user.id, favourite=False)
    db_session.add(agent)
    db_session.commit()
    return agent
