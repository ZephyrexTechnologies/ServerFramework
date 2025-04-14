import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
class AbstractProvider(ABC):
    """
    Abstract base class for all service providers (AI and Extensions).
    This class defines the common interface and functionality that all providers should implement.
    """
    def __init__(
        self,
        api_uri: str = "",
        extension_id: Optional[str] = None,
        wait_between_requests: int = 1,
        wait_after_failure: int = 3,
        **kwargs,
    ):
        """
        Initialize the provider with common configuration parameters.
        Args:
            api_key: The API key for the service
            api_uri: The base URL for the API
            wait_between_requests: Time to wait between API requests in seconds
            wait_after_failure: Time to wait after a failed request before retrying
            **kwargs: Additional provider-specific parameters
        """
        self.friendly_name = self.__class__.__name__
        self.extension_id = extension_id
        self.requirements: List[str] = []
        self.api_key = api_key
        self.api_uri = api_uri
        self.WAIT_BETWEEN_REQUESTS = wait_between_requests
        self.WAIT_AFTER_FAILURE = wait_after_failure
        self.failures = 0
        self.MAX_FAILURES = 3
        self.capabilities: Set[str] = set()
        self.commands: Dict[str, Any] = {}
        # Set up working directory for extension providers
        self.WORKING_DIRECTORY = (
            kwargs.get("conversation_directory")
            if "conversation_directory" in kwargs
        )
        self.kwargs = kwargs
        self._configure_provider(**kwargs)
    def _configure_provider(self, **kwargs) -> None:
        """
        Configure provider-specific settings.
        of provider-specific settings.
        """
    @staticmethod
    @abstractmethod
    def services() -> List[str]:
        """
        Return a list of services provided by this provider.
        Returns:
            List of service identifiers (e.g., "llm", "vision", "tts", etc.)
        pass
    def supports_service(self, service: str) -> bool:
        """
        Check if this provider supports a specific service.
        Args:
        Returns:
            True if the service is supported, False otherwise
        """
        return service in self.services()
        """
        Register a capability for this provider.
        Args:
        """
        self.capabilities.add(capability)
        """
        Check if this provider has a specific capability.
        Args:
            capability: Capability identifier to check
            True if the provider has the capability, False otherwise
        """
        return capability in self.capabilities
        """
        Get the available commands for this provider.
        Returns:
            Dict of command names to command handler functions
        return self.commands
    def safe_join(self, base: str, paths: str) -> str:
        """
        Args:
            base: The base directory
        Returns:
            str: The joined path, normalized and secured
        """
        if "/path/to/" in paths:
        new_path = os.path.normpath(os.path.join(base, *paths.split("/")))
        # Ensure the path doesn't escape the base directory
        if not os.path.commonpath([base, new_path]).startswith(base):
        path_dir = os.path.dirname(new_path)
        os.makedirs(path_dir, exist_ok=True)
        return new_path
    def _handle_failure(self, error: Exception) -> bool:
        Handle a failure and determine if retrying is appropriate.
        Args:
            error: Exception that occurred
            True if the operation should be retried, False otherwise
        Raises:
            Exception: If max failures reached
        self.failures += 1
        logging.error(f"{self.friendly_name} error: {str(error)}")
        if self.failures > self.MAX_FAILURES:
            raise Exception(f"{self.friendly_name} Error: Too many failures. {error}")
        return True
    def get_extension_info(self) -> Dict[str, Any]:
        """
        Get information about the extension this provider is associated with.
        Override in extension providers to provide specific information.
            Dict containing extension metadata
        """
        return {
            "description": "Generic provider",
        }
