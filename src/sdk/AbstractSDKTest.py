import json
import os
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest
from requests import Response

from AbstractTest import AbstractTest, TestCategory, TestClassConfig

from .AbstractSDKHandler import (
    AbstractSDKHandler,
    AuthenticationError,
    ResourceConflictError,
    ResourceNotFoundError,
    SDKException,
    ValidationError,
)


class AbstractSDKTest(AbstractTest):
    """Base class for SDK tests.

    This class provides common functionality for testing SDK modules,
    including mocking HTTP requests and responses.
    """

    # Default configuration for tests
    base_url = "https://api.example.com"
    default_token = "test_token"
    default_api_key = "test_api_key"

    # Test configuration
    test_config = TestClassConfig(
        categories=[TestCategory.UNIT],
        parallel=True,
        cleanup_after_each=True,
    )

    # Fixtures needed for these tests
    required_fixtures = {
        "mock_request": "Mock for requests library",
        "mock_response": "Mock HTTP response object",
    }

    @pytest.fixture(autouse=True)
    def setup_sdk_test(self, monkeypatch):
        """Set up test environment for SDK tests.

        Args:
            monkeypatch: pytest monkeypatch fixture
        """
        # Start patching requests
        self.requests_patcher = patch("requests.request")
        self.mock_request = self.requests_patcher.start()

        # Create a mock response
        self.mock_response = MagicMock(spec=Response)
        self.mock_response.status_code = 200
        self.mock_response.ok = True
        self.mock_response.json.return_value = {"message": "success"}
        self.mock_response.text = json.dumps({"message": "success"})
        self.mock_response.content = json.dumps({"message": "success"}).encode()

        # Set the mock response as the return value for the request
        self.mock_request.return_value = self.mock_response

        # Initialize the SDK handler
        self.sdk_handler = AbstractSDKHandler(
            base_url=self.base_url,
            token=self.default_token,
            api_key=self.default_api_key,
        )

        yield

        # Clean up
        self.requests_patcher.stop()

    def mock_response_json(self, data: Dict[str, Any]) -> None:
        """Set the JSON data for the mock response.

        Args:
            data: JSON data to return
        """
        self.mock_response.json.return_value = data
        self.mock_response.text = json.dumps(data)
        self.mock_response.content = json.dumps(data).encode()

    def mock_response_error(self, status_code: int, message: str = None) -> None:
        """Set the mock response to return an error.

        Args:
            status_code: HTTP status code
            message: Error message
        """
        self.mock_response.ok = False
        self.mock_response.status_code = status_code

        error_data = {"detail": message or f"Error {status_code}"}

        self.mock_response.json.return_value = error_data
        self.mock_response.text = json.dumps(error_data)
        self.mock_response.content = json.dumps(error_data).encode()

    def mock_response_validation_error(self, errors: Dict[str, Any]) -> None:
        """Set the mock response to return a validation error.

        Args:
            errors: Validation errors
        """
        self.mock_response.ok = False
        self.mock_response.status_code = 422

        error_data = {
            "detail": "Validation Error",
            "errors": errors,
        }

        self.mock_response.json.return_value = error_data
        self.mock_response.text = json.dumps(error_data)
        self.mock_response.content = json.dumps(error_data).encode()

    def assert_request_called_with(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Assert that the request was called with the expected arguments.

        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request data
            params: Query parameters
            headers: Request headers
        """
        # Ensure request was called
        self.mock_request.assert_called()

        # Get the call arguments
        call_args, call_kwargs = self.mock_request.call_args

        # Check method
        self.assertEqual(call_kwargs.get("method"), method)

        # Check URL
        expected_url = self.base_url
        if not endpoint.startswith("/"):
            expected_url += "/"
        expected_url += endpoint.lstrip("/")

        if params:
            # Add query parameters
            query_params = []
            for key, value in params.items():
                if isinstance(value, list):
                    value = ",".join(str(v) for v in value)
                query_params.append(f"{key}={value}")

            expected_url += "?" + "&".join(query_params)

        self.assertEqual(call_kwargs.get("url"), expected_url)

        # Check data if provided
        if data is not None:
            # Data should be JSON string
            self.assertEqual(call_kwargs.get("data"), json.dumps(data))

        # Check headers if provided
        if headers is not None:
            for key, value in headers.items():
                self.assertEqual(call_kwargs.get("headers").get(key), value)

        # Check that authentication is included in headers
        auth_headers = call_kwargs.get("headers", {})
        if self.sdk_handler.token:
            self.assertEqual(
                auth_headers.get("Authorization"), f"Bearer {self.sdk_handler.token}"
            )
        elif self.sdk_handler.api_key:
            self.assertEqual(auth_headers.get("X-API-Key"), self.sdk_handler.api_key)

    def get_fixture_path(self, filename: str) -> str:
        """Get the path to a test fixture file.

        Args:
            filename: Fixture filename

        Returns:
            Absolute path to the fixture file
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        fixtures_dir = os.path.join(current_dir, "fixtures")

        # Create fixtures directory if it doesn't exist
        if not os.path.exists(fixtures_dir):
            os.makedirs(fixtures_dir)

        return os.path.join(fixtures_dir, filename)

    def load_fixture(self, filename: str) -> Dict[str, Any]:
        """Load a JSON fixture file.

        Args:
            filename: Fixture filename

        Returns:
            Fixture data
        """
        fixture_path = self.get_fixture_path(filename)

        with open(fixture_path, "r") as f:
            return json.load(f)

    def save_fixture(self, filename: str, data: Dict[str, Any]) -> None:
        """Save data to a JSON fixture file.

        Args:
            filename: Fixture filename
            data: Data to save
        """
        fixture_path = self.get_fixture_path(filename)

        with open(fixture_path, "w") as f:
            json.dump(data, f, indent=2)

    def test_get_headers(self):
        """Test that the correct headers are returned."""
        # Test with token
        handler = AbstractSDKHandler(base_url=self.base_url, token=self.default_token)
        headers = handler._get_headers()

        self.assertEqual(headers["Authorization"], f"Bearer {self.default_token}")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Accept"], "application/json")

        # Test with API key
        handler = AbstractSDKHandler(
            base_url=self.base_url, api_key=self.default_api_key
        )
        headers = handler._get_headers()

        self.assertEqual(headers["X-API-Key"], self.default_api_key)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Accept"], "application/json")

    def test_build_url(self):
        """Test building URLs with query parameters."""
        # Test basic URL
        url = self.sdk_handler._build_url("/test")
        self.assertEqual(url, f"{self.base_url}/test")

        # Test URL with query parameters
        url = self.sdk_handler._build_url(
            "/test", {"param1": "value1", "param2": "value2"}
        )
        self.assertEqual(url, f"{self.base_url}/test?param1=value1&param2=value2")

        # Test URL with list parameters
        url = self.sdk_handler._build_url("/test", {"param1": ["value1", "value2"]})
        self.assertEqual(url, f"{self.base_url}/test?param1=value1%2Cvalue2")

        # Test URL with None parameters
        url = self.sdk_handler._build_url("/test", {"param1": "value1", "param2": None})
        self.assertEqual(url, f"{self.base_url}/test?param1=value1")

    def test_request_methods(self):
        """Test that request methods call the _request method correctly."""
        # Test GET
        self.sdk_handler.get("/test", {"param": "value"}, "test")
        self.assert_request_called_with("GET", "/test", params={"param": "value"})

        # Test POST
        data = {"key": "value"}
        self.sdk_handler.post("/test", data, {"param": "value"}, "test")
        self.assert_request_called_with(
            "POST", "/test", data=data, params={"param": "value"}
        )

        # Test PUT
        data = {"key": "value"}
        self.sdk_handler.put("/test", data, {"param": "value"}, "test")
        self.assert_request_called_with(
            "PUT", "/test", data=data, params={"param": "value"}
        )

        # Test DELETE
        self.sdk_handler.delete("/test", {"param": "value"}, "test")
        self.assert_request_called_with("DELETE", "/test", params={"param": "value"})

        # Test PATCH
        data = {"key": "value"}
        self.sdk_handler.patch("/test", data, {"param": "value"}, "test")
        self.assert_request_called_with(
            "PATCH", "/test", data=data, params={"param": "value"}
        )

    def test_handle_response_error(self):
        """Test handling response errors."""
        # Test 401 error
        self.mock_response_error(401, "Unauthorized")
        with self.assertRaises(AuthenticationError):
            self.sdk_handler._handle_response_error(self.mock_response)

        # Test 404 error
        self.mock_response_error(404, "Not Found")
        self.mock_response.url = f"{self.base_url}/test/123"
        with self.assertRaises(ResourceNotFoundError):
            self.sdk_handler._handle_response_error(self.mock_response, "test")

        # Test 422 error
        self.mock_response_error(422, "Validation Error")
        with self.assertRaises(ValidationError):
            self.sdk_handler._handle_response_error(self.mock_response)

        # Test 409 error - create conflict
        self.mock_response_error(409, "Resource already exists")
        with self.assertRaises(ResourceConflictError) as context:
            self.sdk_handler._handle_response_error(self.mock_response, "test")
        self.assertEqual(context.exception.conflict_type, "creation")

        # Test 409 error - update conflict
        self.mock_response_error(409, "Resource conflict")
        with self.assertRaises(ResourceConflictError) as context:
            self.sdk_handler._handle_response_error(self.mock_response, "test")
        self.assertEqual(context.exception.conflict_type, "update")

        # Test generic error
        self.mock_response_error(500, "Internal Server Error")
        with self.assertRaises(SDKException):
            self.sdk_handler._handle_response_error(self.mock_response)
