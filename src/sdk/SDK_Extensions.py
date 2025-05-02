from typing import Any, Dict, List, Optional

from .AbstractSDKHandler import AbstractSDKHandler


class ExtensionsSDK(AbstractSDKHandler):
    """SDK for provider extension management.

    This class provides methods for managing provider extensions,
    including listing available extensions, installing extensions,
    and uninstalling extensions.
    """

    def list_available_extensions(
        self,
        offset: int = 0,
        limit: int = 100,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """List all available extensions that can be installed.

        This method returns a catalog of all available extensions that
        can be installed on providers, regardless of whether they are
        currently installed.

        Args:
            offset: Number of items to skip
            limit: Maximum number of items to return
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)
            filters: Optional filters to apply to the results

        Returns:
            List of available extensions with metadata
        """
        params = {
            "offset": offset,
            "limit": limit,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }

        # Add filters to params
        if filters:
            params.update(filters)

        return self.get(
            "/v1/extension/available",
            query_params=params,
            resource_name="extensions",
        )

    def get_provider_extensions(
        self, provider_id: str, status: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get all extensions for a specific provider.

        This method retrieves all extensions installed on a specific provider,
        with optional filtering by status.

        Args:
            provider_id: The ID of the provider to get extensions for
            status: Optional filter by extension status (enabled, disabled)

        Returns:
            List of extensions installed on the provider

        Raises:
            ResourceNotFoundError: If the provider is not found
        """
        params = {}
        if status:
            params["status"] = status

        return self.get(
            f"/v1/provider/{provider_id}/extension",
            query_params=params,
            resource_name="provider_extensions",
        )

    def install_extension(
        self, provider_id: str, extension_id: str, config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Install an extension for a provider.

        This method installs a specific extension for a provider and configures it
        with the provided options.

        Args:
            provider_id: The ID of the provider to install the extension for
            extension_id: The ID of the extension to install
            config: Optional configuration parameters for the extension

        Returns:
            The installed extension details

        Raises:
            ResourceNotFoundError: If the extension or provider is not found
            ValidationError: If the configuration is invalid
        """
        data = {
            "provider_extension": {
                "extension_id": extension_id,
                "config_json": None,
            }
        }

        if config:
            import json

            data["provider_extension"]["config_json"] = json.dumps(config)

        return self.post(
            f"/v1/provider/{provider_id}/extension",
            data=data,
            resource_name="provider_extension",
        )

    def uninstall_extension(self, provider_id: str, extension_id: str) -> None:
        """Uninstall an extension from a provider.

        This method removes an installed extension from a provider.

        Args:
            provider_id: The ID of the provider to uninstall the extension from
            extension_id: The ID of the extension to uninstall

        Raises:
            ResourceNotFoundError: If the extension or provider is not found
        """
        self.delete(
            f"/v1/provider/{provider_id}/extension/{extension_id}",
            resource_name="extension",
        )

    # Standard CRUD operations for extensions

    def create_extension(
        self,
        name: str,
        description: str,
        icon_url: Optional[str] = None,
        version: str = "1.0.0",
        **kwargs,
    ) -> Dict[str, Any]:
        """Create a new extension.

        Args:
            name: Extension name
            description: Extension description
            icon_url: URL to the extension's icon
            version: Extension version
            **kwargs: Additional extension data

        Returns:
            New extension information
        """
        data = {
            "extension": {
                "name": name,
                "description": description,
                "icon_url": icon_url,
                "version": version,
                **kwargs,
            }
        }

        return self.post("/v1/extension", data, resource_name="extension")

    def get_extension(self, extension_id: str) -> Dict[str, Any]:
        """Get an extension by ID.

        Args:
            extension_id: Extension ID

        Returns:
            Extension information
        """
        return self.get(f"/v1/extension/{extension_id}", resource_name="extension")

    def update_extension(
        self,
        extension_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        icon_url: Optional[str] = None,
        version: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Update an extension.

        Args:
            extension_id: Extension ID
            name: Updated extension name
            description: Updated extension description
            icon_url: Updated icon URL
            version: Updated extension version
            **kwargs: Additional extension data to update

        Returns:
            Updated extension information
        """
        data = {"extension": {}}

        if name:
            data["extension"]["name"] = name
        if description:
            data["extension"]["description"] = description
        if icon_url:
            data["extension"]["icon_url"] = icon_url
        if version:
            data["extension"]["version"] = version

        # Add any additional kwargs
        data["extension"].update(kwargs)

        return self.put(
            f"/v1/extension/{extension_id}", data, resource_name="extension"
        )

    def list_extensions(
        self,
        offset: int = 0,
        limit: int = 100,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
    ) -> Dict[str, Any]:
        """List extensions with pagination.

        Args:
            offset: Number of items to skip
            limit: Maximum number of items to return
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)

        Returns:
            List of extensions
        """
        params = {
            "offset": offset,
            "limit": limit,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }

        return self.get(
            "/v1/extension", query_params=params, resource_name="extensions"
        )

    def delete_extension(self, extension_id: str) -> None:
        """Delete an extension.

        Args:
            extension_id: Extension ID
        """
        self.delete(f"/v1/extension/{extension_id}", resource_name="extension")

    def search_extensions(
        self,
        query: str,
        offset: int = 0,
        limit: int = 100,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
    ) -> Dict[str, Any]:
        """Search for extensions.

        Args:
            query: Search query
            offset: Number of items to skip
            limit: Maximum number of items to return
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)

        Returns:
            List of matching extensions
        """
        params = {
            "query": query,
            "offset": offset,
            "limit": limit,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }

        return self.get(
            "/v1/extension/search",
            query_params=params,
            resource_name="extensions",
        )
