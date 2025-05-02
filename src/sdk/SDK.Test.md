# SDK Testing Guide

This document outlines the testing approach and best practices for the SDK.

## Testing Framework

The SDK uses the following tools for testing:

- **pytest**: Primary testing framework
- **unittest.mock**: For mocking API responses
- **pytest-cov**: For code coverage reporting

## Test Structure

Tests are organized as follows:

```
sdk/
├── tests/
│   ├── fixtures/            # Test fixtures
│   ├── test_sdk.py          # Tests for main SDK class
│   ├── test_auth.py         # Tests for AuthSDK
│   ├── test_providers.py    # Tests for ProvidersSDK
│   └── test_extensions.py   # Tests for ExtensionsSDK
```

All test classes extend `AbstractSDKTest` which provides common functionality for testing SDK components.

## Running Tests

Use the provided test script to run all tests:

```bash
# Make the script executable if needed
chmod +x scripts/test.sh

# Run tests
./scripts/test.sh
```

This script:
1. Installs the package in development mode
2. Runs linting checks
3. Runs type checking
4. Runs tests with coverage reporting

To run specific tests:

```bash
# Run a specific test file
python -m pytest sdk/tests/test_auth.py

# Run a specific test class
python -m pytest sdk/tests/test_auth.py::TestAuthSDK

# Run a specific test method
python -m pytest sdk/tests/test_auth.py::TestAuthSDK::test_login
```

## Test Base Class

All test classes should extend `AbstractSDKTest`, which provides common functionality:

```python
from sdk.AbstractSDKTest import AbstractSDKTest

class TestYourModule(AbstractSDKTest):
    def setUp(self):
        super().setUp()
        # Additional setup for your module
        self.your_sdk = YourSDK(
            base_url=self.base_url,
            token=self.default_token
        )
    
    def test_your_method(self):
        # Set up mock response
        mock_response = {"key": "value"}
        self.mock_response_json(mock_response)
        
        # Call method
        result = self.your_sdk.your_method()
        
        # Verify request and response
        self.assert_request_called_with("GET", "/expected/endpoint")
        self.assertEqual(result, mock_response)
```

## Mocking HTTP Requests

The `AbstractSDKTest` class includes tools for mocking HTTP requests:

```python
# Mock a successful JSON response
self.mock_response_json({"key": "value"})

# Mock an error response
self.mock_response_error(404, "Resource not found")

# Mock a validation error
self.mock_response_validation_error({"field": ["This field is required"]})
```

## Testing Different Response Types

Test various response scenarios:

```python
# Test successful response
def test_successful_request(self):
    response_data = {"user": {"id": "123", "name": "Test User"}}
    self.mock_response_json(response_data)
    result = self.auth_sdk.get_user("123")
    self.assertEqual(result, response_data)

# Test error response
def test_error_response(self):
    self.mock_response_error(404, "User not found")
    with self.assertRaises(ResourceNotFoundError) as context:
        self.auth_sdk.get_user("nonexistent")
    self.assertEqual(context.exception.status_code, 404)
    
# Test exception during request
def test_request_exception(self):
    self.mock_request.side_effect = requests.RequestException("Connection error")
    with self.assertRaises(SDKException) as context:
        self.auth_sdk.get_user("123")
    self.assertIn("Connection error", str(context.exception))
```

## Using Test Fixtures

Create test fixtures for commonly used data:

```python
# Save fixture
user_data = {"id": "123", "name": "Test User"}
self.save_fixture("user.json", user_data)

# Load fixture
loaded_user = self.load_fixture("user.json")
```

## Code Coverage

Aim for high test coverage (90%+) for all SDK components. The test script includes coverage reporting. 

To view detailed coverage:

```bash
python -m pytest --cov=sdk --cov-report=html
# Then open htmlcov/index.html in your browser
```

## Testing Authentication

Test different authentication methods:

```python
# Test with token
def test_token_auth(self):
    sdk = YourSDK(base_url=self.base_url, token="test_token")
    # Make request and verify Authorization header
    
# Test with API key
def test_api_key_auth(self):
    sdk = YourSDK(base_url=self.base_url, api_key="test_api_key")
    # Make request and verify X-API-Key header
    
# Test with no auth
def test_no_auth(self):
    sdk = YourSDK(base_url=self.base_url)
    # Make request and verify no auth headers
```

## Testing Request Parameters

Verify correct request parameters:

```python
def test_query_parameters(self):
    # Call method with query parameters
    self.your_sdk.list_resources(offset=10, limit=50, sort_by="name")
    
    # Verify URL contains query parameters
    self.assert_request_called_with(
        "GET", 
        "/endpoint", 
        params={"offset": 10, "limit": 50, "sort_by": "name"}
    )
```

## Integration Testing

While most tests are unit tests that mock HTTP requests, you might want some integration tests against a real API:

```python
@pytest.mark.integration
def test_integration_login(self):
    # Skip if not running integration tests
    if not os.environ.get("RUN_INTEGRATION_TESTS"):
        pytest.skip("Skipping integration test")
        
    # Use real API for this test
    sdk = SDK(base_url="https://api.example.com")
    result = sdk.auth.login(
        email=os.environ.get("TEST_USER_EMAIL"),
        password=os.environ.get("TEST_USER_PASSWORD")
    )
    self.assertIn("token", result)
```

## Continuous Integration

Set up CI to run tests automatically:

```yaml
# .github/workflows/test.yml
name: Test

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, '3.10', '3.11']
    
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"
    - name: Run tests
      run: |
        ./scripts/test.sh
```

## Best Practices

1. **Test all public methods** - Every public method should have at least one test
2. **Test error cases** - Don't just test the "happy path"
3. **Test edge cases** - Null values, empty lists, etc.
4. **Isolation** - Tests should not depend on each other
5. **Mock external dependencies** - Tests should run without network access
6. **Clear assertions** - Make it obvious what you're testing
7. **Readable test names** - Name tests descriptively
8. **Small tests** - Each test should focus on a specific behavior 