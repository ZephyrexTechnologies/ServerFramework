import pytest
from sqlalchemy.orm import Session
from database.Base import get_session
from database.DB_Auth import User
from database.DB_Providers import Provider

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
def test_user(db_session, faker):
    """Create a test user"""
    user = User(
        email=faker.email(), first_name=faker.first_name(), last_name=faker.last_name()
    )
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
