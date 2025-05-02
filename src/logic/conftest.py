import pytest

# Add these fixtures to your existing conftest.py


@pytest.fixture(scope="function")
def requester_id() -> str:
    """
    Fixture that provides a consistent test requester ID.
    This ID will be used as the 'requester_id' when creating BLL manager instances.

    Returns:
        UUID string to use as requester ID in tests
    """
    return "00000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="function")
def test_user_id() -> str:
    """
    Fixture that provides a consistent test user ID.
    This ID will be used for entities that require a user_id.

    Returns:
        UUID string to use as user ID in tests
    """
    return "00000000-0000-0000-0000-000000000002"


@pytest.fixture(scope="function")
def test_team_id() -> str:
    """
    Fixture that provides a consistent test team ID.
    This ID will be used for entities that require a team_id.

    Returns:
        UUID string to use as team ID in tests
    """
    return "00000000-0000-0000-0000-000000000003"


@pytest.fixture(scope="function")
def seed_database(db, requester_id, test_user_id, test_team_id):
    """
    Fixture to seed the database with common test data.
    This creates basic records needed by many tests such as a test user and team.

    Args:
        db: The test database session
        requester_id: Test requester ID
        test_user_id: Test user ID
        test_team_id: Test team ID
    """
    # Import necessary models
    from database.DB_Auth import Team, User

    # Create test user if it doesn't exist
    if not User.exists(requester_id=requester_id, db=db, id=test_user_id):
        User.create(
            requester_id=requester_id,
            db=db,
            id=test_user_id,
            email="test@example.com",
            first_name="Test",
            last_name="User",
            display_name="Test User",
            active=True,
        )

    # Create test team if it doesn't exist
    if not Team.exists(requester_id=requester_id, db=db, id=test_team_id):
        Team.create(
            requester_id=requester_id,
            db=db,
            id=test_team_id,
            name="Test Team",
            description="Team for testing",
            encryption_key="test-encryption-key",
        )

    yield
