from typing import Dict, Optional

from .AbstractSDKHandler import (
    AbstractSDKHandler,
    AuthenticationError,
    ResourceConflictError,
    ResourceNotFoundError,
    SDKException,
    ValidationError,
)
from .SDK_Auth import AuthSDK
from .SDK_Extensions import ExtensionsSDK
from .SDK_Providers import ProvidersSDK


class SDK:
    """Main SDK class for API access.

    This class serves as the central entry point for the SDK,
    providing access to various API modules.
    """

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
        verify_ssl: bool = True,
    ):
        """Initialize the SDK.

        Args:
            base_url: Base URL of the API (e.g., "https://api.example.com")
            token: JWT token for authentication
            api_key: API key for authentication
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url
        self.token = token
        self.api_key = api_key
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        # Initialize SDK modules
        self.auth = AuthSDK(base_url, token, api_key, timeout, verify_ssl)
        self.providers = ProvidersSDK(base_url, token, api_key, timeout, verify_ssl)
        self.extensions = ExtensionsSDK(base_url, token, api_key, timeout, verify_ssl)

    def set_token(self, token: str) -> None:
        """Set the JWT token for all SDK modules.

        Args:
            token: JWT token for authentication
        """
        self.token = token
        self.auth.token = token
        self.providers.token = token
        self.extensions.token = token

    def set_api_key(self, api_key: str) -> None:
        """Set the API key for all SDK modules.

        Args:
            api_key: API key for authentication
        """
        self.api_key = api_key
        self.auth.api_key = api_key
        self.providers.api_key = api_key
        self.extensions.api_key = api_key

    def login(self, email: str, password: str) -> Dict[str, any]:
        """Convenience method to login and set token for all SDK modules.

        Args:
            email: User email
            password: User password

        Returns:
            Dict containing user info and token

        Raises:
            AuthenticationError: If authentication fails
        """
        result = self.auth.login(email, password)
        if "token" in result:
            self.set_token(result["token"])
        return result

    def verify_credentials(self) -> bool:
        """Verify if the current credentials are valid.

        Returns:
            True if credentials are valid, False otherwise
        """
        return self.auth.verify_token()

    def set_timeout(self, timeout: int) -> None:
        """Set the timeout for all SDK modules.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.auth.timeout = timeout
        self.providers.timeout = timeout
        self.extensions.timeout = timeout

    def set_verify_ssl(self, verify_ssl: bool) -> None:
        """Set whether to verify SSL certificates for all SDK modules.

        Args:
            verify_ssl: Whether to verify SSL certificates
        """
        self.verify_ssl = verify_ssl
        self.auth.verify_ssl = verify_ssl
        self.providers.verify_ssl = verify_ssl
        self.extensions.verify_ssl = verify_ssl


# Define exports
__all__ = [
    "SDK",
    "AbstractSDKHandler",
    "AuthSDK",
    "ProvidersSDK",
    "ExtensionsSDK",
    "SDKException",
    "AuthenticationError",
    "ResourceNotFoundError",
    "ResourceConflictError",
    "ValidationError",
]
