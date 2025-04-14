import pytest
from fastapi.testclient import TestClient

from app import create_app
from endpoints.EP_Auth_test import TestTeamEndpoints, TestUserEndpoints


@pytest.fixture(scope="session")
def server(db):
    """Get a server for testing"""
    print("Creating test client!")
    return TestClient(create_app())


@pytest.fixture(scope="session")
def user_a(server):
    return TestUserEndpoints().test_POST_201(server)


@pytest.fixture(scope="session")
def jwt_a(server, user_a):
    return TestUserEndpoints().test_POST_200_authorize(server, user_a)


@pytest.fixture(scope="session")
def team_a(server, user_a, jwt_a):
    return TestTeamEndpoints().test_POST_201(server, jwt_a, None, user_a)


@pytest.fixture(scope="session")
def user_b(server):
    return TestUserEndpoints().test_POST_201(server)


@pytest.fixture(scope="session")
def jwt_b(server, user_b):
    return TestUserEndpoints().test_POST_200_authorize(server, user_b)


@pytest.fixture(scope="session")
def team_b(server, user_b, jwt_b):
    return TestTeamEndpoints().test_POST_201(server, user_b, jwt_b)
