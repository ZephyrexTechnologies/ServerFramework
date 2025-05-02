# tests/sdk/conftest.py
import logging
import os
import time

import pytest

from AbstractTest import TestCategory


# Setup logging for tests
@pytest.fixture(scope="session", autouse=True)
def setup_logging():
    """Configure logging for tests."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Reduce noise from third-party libraries
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


@pytest.fixture(scope="session")
def test_base_url() -> str:
    """Get base URL for API tests."""
    return os.environ.get("TEST_API_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def sdk(test_base_url):
    """Create SDK instance."""
    from .SDK import SDK

    sdk = SDK(base_url=test_base_url, verify_ssl=False)
    return sdk


@pytest.fixture(scope="session")
def test_email():
    """Generate a test email for the session."""
    timestamp = int(time.time())
    return f"test-user-{timestamp}@example.com"


@pytest.fixture(scope="session")
def test_password():
    """Generate a test password for the session."""
    return "Test123!"


@pytest.fixture(scope="function")
def mock_sdk():
    """Create a mock SDK for unit tests."""
    from unittest.mock import MagicMock

    from .SDK import SDK

    mock = MagicMock(spec=SDK)
    # Setup mock with needed attributes and methods
    mock.base_url = "https://api.example.com"
    mock.token = None
    mock.api_key = None

    # Create mock modules
    mock.auth = MagicMock()

    return mock


@pytest.fixture(scope="session")
def authenticated_sdk(sdk, test_email, test_password):
    """Create an authenticated SDK instance."""
    max_attempts = 3
    backoff_factor = 2  # Exponential backoff multiplier

    for attempt in range(1, max_attempts + 1):
        try:
            # Try to register a test user
            sdk.auth.register(
                email=test_email,
                password=test_password,
                first_name="Test",
                last_name="User",
                display_name="Test User",
            )

            # Login with the test user
            result = sdk.auth.login(test_email, test_password)

            # Verify authentication was successful
            if not result.get("token"):
                raise ValueError("Login successful but token missing from response")

            # Set the token on the SDK
            sdk.set_token(result["token"])

            return sdk

        except Exception as e:
            wait_time = backoff_factor**attempt

            if attempt == max_attempts:
                pytest.skip(
                    f"Failed to initialize authenticated test environment after {max_attempts} attempts. Last error: {str(e)}"
                )

            print(
                f"Setup attempt {attempt} failed: {str(e)}. Retrying in {wait_time} seconds..."
            )
            time.sleep(wait_time)


@pytest.fixture(scope="session")
def test_categories():
    """Provide test categories for filtering test execution."""
    return {
        "unit": TestCategory.UNIT,
        "integration": TestCategory.INTEGRATION,
        "functional": TestCategory.FUNCTIONAL,
        "performance": TestCategory.PERFORMANCE,
        "smoke": TestCategory.SMOKE,
        "regression": TestCategory.REGRESSION,
        "security": TestCategory.SECURITY,
    }


@pytest.fixture(scope="function")
def requester_id() -> str:
    """Provide a requester ID for tests."""
    return "test-requester-id"


@pytest.fixture(scope="function")
def test_user_id() -> str:
    """Provide a test user ID for tests."""
    return "test-user-id"


@pytest.fixture(scope="function")
def test_team_id() -> str:
    """Provide a test team ID for tests."""
    return "test-team-id"
