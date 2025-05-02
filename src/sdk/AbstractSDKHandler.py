import json
import logging
import urllib.parse
from typing import Any, Dict, Optional

import requests
from requests.exceptions import RequestException


class SDKException(Exception):
    """Base exception for SDK errors."""

    def __init__(
        self, message: str, status_code: int = None, details: Dict[str, Any] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class AuthenticationError(SDKException):
    """Raised when authentication fails."""

    def __init__(
        self, message: str = "Authentication failed", details: Dict[str, Any] = None
    ):
        super().__init__(message, 401, details)


class ResourceNotFoundError(SDKException):
    """Raised when a resource is not found."""

    def __init__(
        self, resource_name: str, resource_id: str, details: Dict[str, Any] = None
    ):
        message = f"{resource_name.title()} with ID '{resource_id}' not found"
        super().__init__(message, 404, details)


class ValidationError(SDKException):
    """Raised when data validation fails."""

    def __init__(
        self, message: str = "Validation failed", details: Dict[str, Any] = None
    ):
        super().__init__(message, 422, details)


class ResourceConflictError(SDKException):
    """Raised when a resource conflict occurs."""

    def __init__(
        self, resource_name: str, conflict_type: str, details: Dict[str, Any] = None
    ):
        message = f"{resource_name.title()} {conflict_type} conflict"
        super().__init__(message, 409, details)


class AbstractSDKHandler:
    """Base class for all SDK handlers.

    This class provides common functionality for interacting with the API,
    including authentication, request handling, and error handling.

    All SDK modules should extend this class to leverage common HTTP functionality.
    """

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
        verify_ssl: bool = True,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize the SDK handler.

        Args:
            base_url: Base URL of the API (e.g., "https://api.example.com")
            token: JWT token for authentication
            api_key: API key for authentication
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
            logger: Optional custom logger instance
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.api_key = api_key
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        # Use provided logger or create one based on class name
        self.logger = logger or logging.getLogger(f"sdk.{self.__class__.__name__}")

        # Validate that we have either a token or an API key if required
        if not token and not api_key:
            self.logger.warning("No authentication credentials provided")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests, including authentication.

        Returns:
            Dictionary of HTTP headers for API requests
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.api_key:
            headers["X-API-Key"] = self.api_key

        return headers

    def _build_url(self, endpoint: str, query_params: Dict[str, Any] = None) -> str:
        """Build a complete URL for the API request.

        Args:
            endpoint: API endpoint (e.g., "/v1/user")
            query_params: Query parameters to include in the URL

        Returns:
            Complete URL for the API request
        """
        # Ensure endpoint starts with a slash
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"

        url = f"{self.base_url}{endpoint}"

        # Add query parameters if provided
        if query_params:
            # Filter out None values
            params = {k: v for k, v in query_params.items() if v is not None}

            # Handle list parameters
            for key, value in params.items():
                if isinstance(value, list):
                    params[key] = ",".join(str(v) for v in value)

            # Add to URL
            if params:
                query_string = urllib.parse.urlencode(params)
                url = f"{url}?{query_string}"

        return url

    def _format_response(self, response: requests.Response) -> Dict[str, Any]:
        """Format the API response into a more usable structure.

        Args:
            response: Response from API request

        Returns:
            Formatted response data
        """
        try:
            return response.json()
        except ValueError:
            if response.content:
                return {"raw_content": response.content.decode("utf-8")}
            return {}

    def _handle_response_error(
        self, response: requests.Response, resource_name: str = "resource"
    ):
        """Handle error responses from the API.

        Args:
            response: Error response from API
            resource_name: Name of the resource being accessed

        Raises:
            AuthenticationError: If authentication fails
            ResourceNotFoundError: If resource is not found
            ValidationError: If request validation fails
            ResourceConflictError: If resource conflict occurs
            SDKException: For other API errors
        """
        error_data = {}
        try:
            error_data = response.json()
        except ValueError:
            error_message = response.text or f"HTTP {response.status_code} error"
        else:
            error_message = error_data.get(
                "detail",
                error_data.get("message", f"HTTP {response.status_code} error"),
            )

        self.logger.error(
            f"API error: {error_message} (Status code: {response.status_code})"
        )

        if response.status_code == 401:
            raise AuthenticationError(error_message, error_data)
        elif response.status_code == 404:
            resource_id = "unknown"
            # Try to extract ID from URL path
            path_parts = response.url.split("/")
            if len(path_parts) > 0:
                resource_id = path_parts[-1]
            raise ResourceNotFoundError(resource_name, resource_id, error_data)
        elif response.status_code == 422:
            raise ValidationError(error_message, error_data)
        elif response.status_code == 409:
            conflict_type = (
                "creation" if "already exists" in error_message else "update"
            )
            raise ResourceConflictError(resource_name, conflict_type, error_data)
        else:
            raise SDKException(error_message, response.status_code, error_data)

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Any = None,
        query_params: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        resource_name: str = "resource",
    ) -> Dict[str, Any]:
        """Send a request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint
            data: Request data (for POST, PUT, etc.)
            query_params: Query parameters
            headers: Additional headers
            resource_name: Name of the resource being accessed (for error messages)

        Returns:
            Response data from the API

        Raises:
            SDKException: If the request fails
        """
        url = self._build_url(endpoint, query_params)
        request_headers = self._get_headers()

        # Add additional headers if provided
        if headers:
            request_headers.update(headers)

        # Convert data to JSON if needed
        request_data = None
        if data is not None:
            request_data = json.dumps(data)

        self.logger.debug(f"{method} {url}")
        if data:
            self.logger.debug(f"Request data: {request_data}")

        try:
            response = requests.request(
                method=method,
                url=url,
                data=request_data,
                headers=request_headers,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )

            # Log response status
            self.logger.debug(f"Response status: {response.status_code}")

            # Check for errors
            if not response.ok:
                self._handle_response_error(response, resource_name)

            # Return response data
            if response.status_code == 204:  # No content
                return {}

            result = self._format_response(response)
            self.logger.debug(f"Response data: {result}")
            return result

        except RequestException as e:
            self.logger.error(f"Request failed: {str(e)}")
            raise SDKException(f"Request failed: {str(e)}")

    def get(
        self,
        endpoint: str,
        query_params: Dict[str, Any] = None,
        resource_name: str = "resource",
        headers: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Send a GET request to the API.

        Args:
            endpoint: API endpoint
            query_params: Query parameters
            resource_name: Name of the resource being accessed (for error messages)
            headers: Additional headers to include in the request

        Returns:
            Response data from the API
        """
        return self._request(
            "GET",
            endpoint,
            query_params=query_params,
            resource_name=resource_name,
            headers=headers,
        )

    def post(
        self,
        endpoint: str,
        data: Any,
        query_params: Dict[str, Any] = None,
        resource_name: str = "resource",
        headers: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Send a POST request to the API.

        Args:
            endpoint: API endpoint
            data: Request data
            query_params: Query parameters
            resource_name: Name of the resource being accessed (for error messages)
            headers: Additional headers to include in the request

        Returns:
            Response data from the API
        """
        return self._request(
            "POST",
            endpoint,
            data=data,
            query_params=query_params,
            resource_name=resource_name,
            headers=headers,
        )

    def put(
        self,
        endpoint: str,
        data: Any,
        query_params: Dict[str, Any] = None,
        resource_name: str = "resource",
        headers: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Send a PUT request to the API.

        Args:
            endpoint: API endpoint
            data: Request data
            query_params: Query parameters
            resource_name: Name of the resource being accessed (for error messages)
            headers: Additional headers to include in the request

        Returns:
            Response data from the API
        """
        return self._request(
            "PUT",
            endpoint,
            data=data,
            query_params=query_params,
            resource_name=resource_name,
            headers=headers,
        )

    def delete(
        self,
        endpoint: str,
        query_params: Dict[str, Any] = None,
        resource_name: str = "resource",
        headers: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Send a DELETE request to the API.

        Args:
            endpoint: API endpoint
            query_params: Query parameters
            resource_name: Name of the resource being accessed (for error messages)
            headers: Additional headers to include in the request

        Returns:
            Response data from the API
        """
        return self._request(
            "DELETE",
            endpoint,
            query_params=query_params,
            resource_name=resource_name,
            headers=headers,
        )

    def patch(
        self,
        endpoint: str,
        data: Any,
        query_params: Dict[str, Any] = None,
        resource_name: str = "resource",
        headers: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Send a PATCH request to the API.

        Args:
            endpoint: API endpoint
            data: Request data
            query_params: Query parameters
            resource_name: Name of the resource being accessed (for error messages)
            headers: Additional headers to include in the request

        Returns:
            Response data from the API
        """
        return self._request(
            "PATCH",
            endpoint,
            data=data,
            query_params=query_params,
            resource_name=resource_name,
            headers=headers,
        )
