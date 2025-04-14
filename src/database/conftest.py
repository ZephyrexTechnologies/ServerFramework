import pytest
from sqlalchemy.orm import Session

from database.Base import get_session
from database.DB_Agents import Agent
from database.DB_Auth import User
from database.DB_Providers import Provider
from helptest import generate_test_email

# Import database components after environment setup


@pytest.fixture(scope="session")
def db_session(db):
    """Get a database session for testing"""
    session = get_session()
    yield session
    cleanup_session(session)


def cleanup_session(session: Session):
    """Helper to properly cleanup a session"""
    try:
        session.rollback()
    except:
        pass
    finally:
        session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(email=generate_test_email(), first_name="John", last_name="Doe")
    db_session.add(user)
    db_session.commit()
    yield user


@pytest.fixture
def sample_provider(db_session):
    """Create a sample provider"""
    provider = Provider(name="test_provider")
    db_session.add(provider)
    db_session.commit()
    yield provider


@pytest.fixture
def sample_agent(db_session, test_user, sample_provider):
    """Create a sample agent"""
    agent = Agent(
        name="test_agent",
        # provider_id=sample_provider.id,
        # TODO: Update conftest.py (this and others) to reflect any new API/DB changes
        created_by_user_id=test_user.id,  # Use test_user.id instead of hardcoded value
    )
    db_session.add(agent)
    db_session.commit()
    yield agent
