# tests/sdk/conftest.py
import time

import pytest


@pytest.fixture(scope="session")
def sdk():
    """Create SDK instance."""
    sdk = SDK(base_uri="http://localhost:1996", verbose=True)
    return sdk


@pytest.fixture(scope="session")
def test_email():
    """Generate a test email for the session."""
    return generate_test_email()


@pytest.fixture(scope="session")
def authenticated_sdk(sdk, test_email):
    """Create an authenticated SDK instance."""
    max_attempts = 3
    backoff_factor = 2  # Exponential backoff multiplier

    for attempt in range(1, max_attempts + 1):
        try:
            otp_uri = sdk.register_user(
                email=test_email, first_name="Test", last_name="User"
            )

            # Verify authentication was successful
            if not (otp_uri and sdk.headers.get("Authorization")):
                raise ValueError(
                    "Registration successful but authentication headers missing"
                )

            return sdk

        except Exception as e:
            wait_time = backoff_factor**attempt

            if attempt == max_attempts:
                raise Exception(
                    f"Failed to initialize test environment after {max_attempts} attempts. Last error: {str(e)}"
                )

            print(
                f"Setup attempt {attempt} failed: {str(e)}. Retrying in {wait_time} seconds..."
            )
            time.sleep(wait_time)
