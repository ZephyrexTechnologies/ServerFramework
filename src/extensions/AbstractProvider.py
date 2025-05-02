import importlib
import inspect
import logging
import os
from abc import ABC
from typing import Any, Dict, List, Optional, Set


class AbstractProvider(ABC):
    """
    Abstract base class for all service providers.
    This class defines the common interface and functionality that all providers should implement.
    """

    def __init__(
        self,
        extension_id: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize the provider with common configuration parameters.

        Args:
            extension_id: The ID of the extension this provider is associated with
            **kwargs: Additional provider-specific parameters
        """
        self.friendly_name = self.__class__.__name__
        self.extension_id = extension_id
        self.failures = 0
        self.MAX_FAILURES = 3
        self.unsupported_capabilities: Set[str] = set()
        self.abilities: Dict[str, Any] = {}
        self._error_handler = None
        self._has_error_handler = False

        # Get capabilities from the extension
        self._extension_capabilities = set()
        if extension_id:
            # Try to find the corresponding extension
            try:
                # Import the extension module
                module_name = f"extensions.EXT_{extension_id}"
                extension_module = importlib.import_module(module_name)

                # Find the extension class
                for name, obj in inspect.getmembers(extension_module):
                    if (
                        inspect.isclass(obj)
                        and hasattr(obj, "capabilities")
                        and hasattr(obj, "name")
                        and obj.name == extension_id
                    ):
                        # Set the extension capabilities
                        self._extension_capabilities = set(
                            getattr(obj, "capabilities", [])
                        )
                        break
            except (ImportError, AttributeError) as e:
                # Log but continue - this just means we couldn't determine capabilities
                logging.warning(
                    f"Could not determine capabilities for extension {extension_id}: {e}"
                )

        # Set up working directory for extension providers
        self.WORKING_DIRECTORY = (
            kwargs.get("conversation_directory")
            if "conversation_directory" in kwargs
            else os.path.join(os.getcwd(), "WORKSPACE")
        )

        # Store all kwargs as instance attributes
        for key, value in kwargs.items():
            setattr(self, key, value)

        self.kwargs = kwargs
        self._configure_provider(**kwargs)

    def _configure_provider(self, **kwargs) -> None:
        """
        Configure provider-specific settings.
        Override this method in subclasses to handle initialization
        of provider-specific settings.
        """
        pass

    @property
    def services(self) -> List[str]:
        """
        Return a list of services provided by this provider.
        This is derived from the extension's capabilities that are not unsupported.

        Returns:
            List of service identifiers (e.g., "llm", "vision", "tts", etc.)
        """
        if not hasattr(self, "_extension_capabilities"):
            return []
        return [
            cap
            for cap in self._extension_capabilities
            if cap not in self.unsupported_capabilities
        ]

    def register_unsupported_ability(self, ability: str) -> None:
        """
        Register a ability that this provider does not support.

        Args:
            ability: ability identifier to register as unsupported
        """
        self.unsupported_capabilities.add(ability)

    def has_ability(self, ability: str) -> bool:
        """
        Check if this provider has a specific ability.

        Args:
            ability: ability identifier to check

        Returns:
            True if the provider has the ability, False otherwise
        """
        if not hasattr(self, "_extension_capabilities"):
            return False
        return (
            ability in self._extension_capabilities
            and ability not in self.unsupported_capabilities
        )

    def get_abilities(self) -> Dict[str, Any]:
        """
        Get the available abilities for this provider.

        Returns:
            Dict of ability names to ability handler functions
        """
        return self.abilities

    def get_capabilities(self) -> Set[str]:
        """
        Return provider capabilities.
        Should be implemented by subclasses.

        Returns:
            Set of capability identifiers
        """
        return set()

    def validate_config(self) -> bool:
        """
        Validate the provider configuration.
        Should be implemented by subclasses.

        Returns:
            True if configuration is valid, False otherwise
        """
        return True

    def get_parent_extension(self):
        """
        Get the extension this provider is associated with.

        Returns:
            Extension instance or None if not associated with an extension
        """
        if not self.extension_id:
            return None

        try:
            from extensions.AbstractExtension import AbstractExtension

            return AbstractExtension.get_extension_by_id(self.extension_id)
        except (ImportError, AttributeError):
            return None

    def get_parent_extension_id(self):
        """
        Return the extension ID this provider is associated with.

        Returns:
            Extension ID or None if not associated with an extension
        """
        return self.extension_id

    def safe_join(self, base: str, paths: str) -> str:
        """
        Safely join paths together, ensuring they don't escape the base directory.

        Args:
            base: The base directory
            paths: The path components to join

        Returns:
            str: The joined path, normalized and secured
        """
        if "/path/to/" in paths:
            paths = paths.replace("/path/to/", "")
        new_path = os.path.normpath(os.path.join(base, *paths.split("/")))
        # Ensure the path doesn't escape the base directory
        if not os.path.commonpath([base, new_path]).startswith(base):
            raise ValueError(f"Path attempted to escape base directory: {paths}")

        path_dir = os.path.dirname(new_path)
        os.makedirs(path_dir, exist_ok=True)
        return new_path

    def _handle_failure(self, error: Exception) -> bool:
        """
        Handle a failure and determine if retrying is appropriate.

        Args:
            error: Exception that occurred

        Returns:
            True if the operation should be retried, False otherwise

        Raises:
            Exception: If max failures reached
        """
        self.failures += 1
        logging.error(f"{self.friendly_name} error: {str(error)}")

        if self.failures > self.MAX_FAILURES:
            raise Exception(f"{self.friendly_name} Error: Too many failures. {error}")

        return True

    def set_error_handler(self, handler):
        """
        Set a custom error handler for this provider.

        Args:
            handler: Error handler function that takes (provider, exception, method_name, *args, **kwargs)

        Returns:
            None
        """
        self._error_handler = handler
        self._has_error_handler = handler is not None

    def get_extension_info(self) -> Dict[str, Any]:
        """
        Get information about the extension this provider is associated with.
        Override in extension providers to provide specific information.

        Returns:
            Dict containing extension metadata
        """
        return {
            "name": self.friendly_name,
            "description": "Generic provider",
        }


class AbstractAPIProvider(AbstractProvider):
    """
    Abstract base class for API-based service providers.
    This class extends AbstractProvider with API-specific functionality.
    """

    def __init__(
        self,
        api_key: str = "",
        api_uri: str = "",
        wait_between_requests: int = 1,
        wait_after_failure: int = 3,
        extension_id: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize the API provider with API-specific configuration parameters.

        Args:
            api_key: The API key for the service
            api_uri: The base URL for the API
            wait_between_requests: Time to wait between API requests in seconds
            wait_after_failure: Time to wait after a failed request before retrying
            extension_id: The ID of the extension this provider is associated with
            **kwargs: Additional provider-specific parameters
        """
        super().__init__(extension_id=extension_id, **kwargs)
        self.api_key = api_key
        self.api_uri = api_uri
        self.WAIT_BETWEEN_REQUESTS = wait_between_requests
        self.WAIT_AFTER_FAILURE = wait_after_failure
