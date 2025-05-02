from typing import Any, Dict, List, Optional

from fastapi import Body, Depends, HTTPException, Path, Query, status

from endpoints.AbstractEndpointRouter import AuthType, create_router_tree
from logic.BLL_Auth import User, UserManager
from logic.BLL_Extensions import ExtensionManager
from logic.BLL_Providers import ProviderExtensionNetworkModel, ProviderManager


def get_provider_extension_manager(user: User = Depends(UserManager.auth)):
    """Get an initialized ProviderExtensionManager instance.

    Args:
        user: Authenticated user from JWT token

    Returns:
        ExtensionManager: An initialized extension manager with the user's permissions
    """
    return ExtensionManager(requester_id=user.id)


# Create router tree for provider extensions following EP.schema.md specification
extension_routers = create_router_tree(
    base_prefix="/v1/provider/extension",
    resource_name="extension",
    tags=["Provider Extension Management"],
    manager_factory=get_provider_extension_manager,
    network_model_cls=ProviderExtensionNetworkModel,
    auth_type=AuthType.JWT,
    example_overrides={
        "get": {
            "extension": {
                "id": "ext-10b5fc76-7b5d-4d28-ac9c-215488921624",
                "name": "WebSearch",
                "description": "Provides web search capabilities to agents",
                "provider_id": "prov-0a1b2c3d-4e5f-6789-0a1b-2c3d4e5f6789",
                "created_at": "2023-09-15T14:30:00Z",
                "updated_at": "2023-09-15T14:30:00Z",
            }
        },
        "create": {
            "extension": {
                "name": "GoogleDrive",
                "description": "Allows access to files in Google Drive",
                "provider_id": "prov-0a1b2c3d-4e5f-6789-0a1b-2c3d4e5f6789",
            }
        },
    },
)

# Access the main router
provider_extension_router = extension_routers["extension"]


# Add custom route for listing available extensions for a provider
@provider_extension_router.get(
    "/available",
    summary="List available extensions",
    description="Lists all available extensions that can be installed.",
    response_model=Dict[str, List[Dict[str, Any]]],
    status_code=status.HTTP_200_OK,
)
async def list_available_extensions(
    manager: ExtensionManager = Depends(get_provider_extension_manager),
):
    """List all available extensions that can be installed.

    This endpoint returns a catalog of all available extensions that
    can be installed on providers, regardless of whether they are
    currently installed.

    Returns:
        Dict[str, List[Dict[str, Any]]]: List of available extensions with metadata
    """
    try:
        extensions = manager.list_available_extensions()
        return {"extensions": extensions}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list available extensions: {str(e)}",
        )


# Add custom route for getting extensions for a specific provider
@provider_extension_router.get(
    "/provider/{provider_id}",
    summary="List provider extensions",
    description="Lists all extensions for a specific provider.",
    response_model=Dict[str, List[Dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Provider not found"},
    },
)
async def get_provider_extensions(
    provider_id: str = Path(..., description="Provider ID"),
    status: Optional[str] = Query(
        None, description="Filter by extension status (enabled, disabled)"
    ),
    manager: ExtensionManager = Depends(get_provider_extension_manager),
):
    """Get all extensions for a specific provider.

    This endpoint retrieves all extensions installed on a specific provider,
    with optional filtering by status.

    Args:
        provider_id: The ID of the provider to get extensions for
        status: Optional filter by extension status (enabled, disabled)
        manager: The extension manager instance

    Returns:
        Dict[str, List[Dict[str, Any]]]: List of extensions installed on the provider

    Raises:
        HTTPException: If the provider is not found or if retrieval fails
    """
    try:
        # Verify provider exists
        provider_manager = ProviderManager(requester_id=manager.requester.id)
        provider = provider_manager.get(id=provider_id)

        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider with ID {provider_id} not found",
            )

        # Get provider extensions with optional status filter
        filters = {"provider_id": provider_id}
        if status:
            filters["status"] = status

        extensions = manager.list(filters=filters)
        return {"extensions": extensions}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get provider extensions: {str(e)}",
        )


# Add custom route for installing an extension
@provider_extension_router.post(
    "/{id}/install",
    summary="Install extension",
    description="Installs an extension for a provider.",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Extension not found"},
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid installation parameters"},
    },
)
async def install_extension(
    id: str = Path(..., description="Extension ID"),
    provider_id: str = Query(..., description="Provider ID"),
    options: Dict[str, Any] = Body({}, description="Installation options"),
    manager: ExtensionManager = Depends(get_provider_extension_manager),
):
    """Install an extension for a provider.

    This endpoint installs a specific extension for a provider and configures it
    with the provided options. If the extension is already installed, it will
    update the configuration.

    Args:
        id: The ID of the extension to install
        provider_id: The ID of the provider to install the extension for
        options: Optional configuration parameters for the extension
        manager: The extension manager instance

    Returns:
        Dict[str, Any]: A success response with the installed extension details

    Raises:
        HTTPException: If the extension or provider is not found, or if installation fails
    """
    try:
        # Verify provider exists
        provider_manager = ProviderManager(requester_id=manager.requester.id)
        provider = provider_manager.get(id=provider_id)

        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider with ID {provider_id} not found",
            )

        # Get the extension
        extension = manager.get(id=id)
        if not extension:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Extension with ID {id} not found",
            )

        # Install the extension
        result = manager.install_extension(
            extension_id=id, provider_id=provider_id, options=options
        )
        return {"result": "success", "extension": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to install extension: {str(e)}",
        )


# Add custom route for uninstalling an extension
@provider_extension_router.post(
    "/{id}/uninstall",
    summary="Uninstall extension",
    description="Uninstalls an extension from a provider.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Extension not found"},
    },
)
async def uninstall_extension(
    id: str = Path(..., description="Extension ID"),
    provider_id: str = Query(..., description="Provider ID"),
    manager: ExtensionManager = Depends(get_provider_extension_manager),
):
    """Uninstall an extension from a provider.

    This endpoint removes an installed extension from a provider. If the extension
    is not installed, it will return a 404 error.

    Args:
        id: The ID of the extension to uninstall
        provider_id: The ID of the provider to uninstall the extension from
        manager: The extension manager instance

    Returns:
        None: Returns 204 No Content on success

    Raises:
        HTTPException: If the extension or provider is not found, or if uninstallation fails
    """
    try:
        # Verify provider exists
        provider_manager = ProviderManager(requester_id=manager.requester.id)
        provider = provider_manager.get(id=provider_id)

        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider with ID {provider_id} not found",
            )

        # Get the extension
        extension = manager.get(id=id)
        if not extension:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Extension with ID {id} not found",
            )

        # Uninstall the extension
        manager.uninstall_extension(extension_id=id, provider_id=provider_id)
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to uninstall extension: {str(e)}",
        )


# Export the router
router = provider_extension_router
