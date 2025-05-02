import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    Security,
    status,
)
from fastapi.security import APIKeyHeader, HTTPBasic
from pluralizer import Pluralizer
from pydantic import BaseModel, ValidationError, create_model

# Set up logging
logger = logging.getLogger(__name__)

# Instantiate Pluralizer
pluralizer = Pluralizer()

# Generic type variables for network models
T = TypeVar("T", bound=BaseModel)


class AuthType(Enum):
    """Authentication types supported by the API."""

    NONE = "none"
    JWT = "jwt"
    API_KEY = "api_key"
    BASIC = "basic"


class RouterConfig(BaseModel):
    """Configuration for creating a FastAPI router from Pydantic models."""

    prefix: str
    tags: List[str]
    manager_factory: Callable
    network_model_cls: Any
    manager_property: Optional[str] = None
    resource_name: Optional[str] = None
    example_overrides: Optional[Dict[str, Dict]] = None
    routes_to_register: Optional[List[str]] = None
    auth_type: AuthType = AuthType.JWT
    parent_router: Optional[Any] = None
    parent_param_name: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


def extract_body_data(
    body: Any, resource_name: str, resource_name_plural: str
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Extract data from a request body object.

    Handles different body formats:
    - Pydantic models with nested attributes
    - Plain dictionaries
    - Lists of models

    Args:
        body: The request body
        resource_name: The name of the resource in singular form
        resource_name_plural: The name of the resource in plural form

    Returns:
        Extracted data as a dictionary or list of dictionaries
    """
    # Handle list of items
    if isinstance(body, list):
        return [
            extract_body_data(item, resource_name, resource_name_plural)
            for item in body
        ]

    # Handle plain dictionary
    if isinstance(body, dict):
        # Check if dictionary has the resource_name as a key
        if resource_name in body:
            return body[resource_name]
        # Check if dictionary has resource_name_plural as a key
        elif resource_name_plural in body:
            return body[resource_name_plural]
        # Return the dictionary as is
        return body

    # Handle Pydantic model
    if hasattr(body, "__dict__"):
        # First try to get the attribute with the resource name
        if hasattr(body, resource_name):
            attr_value = getattr(body, resource_name)
            if hasattr(attr_value, "model_dump"):
                return attr_value.model_dump(exclude_unset=True)
            return attr_value

        # Try to get the attribute with resource_name_plural
        if hasattr(body, resource_name_plural):
            attr_value = getattr(body, resource_name_plural)
            if hasattr(attr_value, "model_dump"):
                return attr_value.model_dump(exclude_unset=True)
            return attr_value

        # Extract first attribute if no specific attribute found
        attribute_names = list(vars(body).keys())
        if attribute_names:
            actual_name = attribute_names[0]
            if hasattr(body, actual_name):
                attr_value = getattr(body, actual_name)
                if hasattr(attr_value, "model_dump"):
                    return attr_value.model_dump(exclude_unset=True)
                return attr_value

    # Default case: return empty dict
    logger.warning(f"Could not extract data from body: {body}")
    return {}


def get_auth_dependency(auth_type: AuthType) -> Optional[Any]:
    """Get the authentication dependency based on auth_type."""
    if auth_type == AuthType.JWT:
        from logic.BLL_Auth import UserManager

        return Depends(UserManager.auth)
    elif auth_type == AuthType.API_KEY:
        return Security(APIKeyHeader(name="X-API-Key"))
    elif auth_type == AuthType.BASIC:
        return Security(HTTPBasic())
    else:
        return None


def create_example_response(
    examples: Dict[str, Dict[str, Any]], operation: str
) -> Optional[Dict[str, Any]]:
    """Create an example response for documentation."""
    if operation in examples:
        return {"example": examples.get(operation)}
    return None


def generate_batch_update_model(resource_name: str) -> Type[BaseModel]:
    """
    Create a dynamic BatchUpdateModel with the resource name.

    Args:
        resource_name: The name of the resource

    Returns:
        A Pydantic model class for batch updates
    """
    return create_model(
        f"{resource_name.capitalize()}BatchUpdateModel",
        **{
            resource_name: (Dict[str, Any], ...),
            "target_ids": (List[str], ...),
        },
    )


def create_router(config: RouterConfig) -> APIRouter:
    """
    Create a FastAPI router from Pydantic models.

    This is the main function that creates a router from a configuration object.
    It handles the conversion of Pydantic models to FastAPI routes.

    Args:
        config: Configuration for the router

    Returns:
        A FastAPI router with routes registered
    """
    # Standard responses for all endpoints
    standard_responses = {
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid request format or parameters"
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Not authenticated"},
        status.HTTP_403_FORBIDDEN: {"description": "Permission denied"},
        status.HTTP_404_NOT_FOUND: {"description": "Resource not found"},
        status.HTTP_409_CONFLICT: {
            "description": "Resource conflict (e.g., duplicate name)"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Server error"},
    }

    # Initialize router
    router = APIRouter(
        prefix=config.prefix,
        tags=config.tags,
        responses=standard_responses,
    )

    # Derive resource names if not provided
    resource_name = config.resource_name
    if not resource_name:
        resource_name = config.prefix.split("/")[-1]
        resource_name = resource_name.replace("-", "_")

    resource_name_plural = pluralizer.plural(resource_name)

    # Get auth dependency
    auth_dependency = get_auth_dependency(config.auth_type)

    # Add routes to the router (would be implemented separately for each route type)
    # For simplicity, we'll return the router without routes
    # The actual route registration would happen in AbstractEndpointRouter using this router

    # Return the configured router
    return router


def register_create_route(
    router: APIRouter,
    resource_name: str,
    resource_name_plural: str,
    network_model_cls: Any,
    manager_factory: Callable,
    examples: Dict[str, Dict[str, Any]],
    auth_dependency: Optional[Any] = None,
) -> None:
    """
    Register the POST route for creating resources.

    Args:
        router: The FastAPI router
        resource_name: Name of the resource in singular form
        resource_name_plural: Name of the resource in plural form
        network_model_cls: The network model class
        manager_factory: Function that returns manager instance
        examples: Dict of examples for documentation
        auth_dependency: Optional authentication dependency
    """
    # Handle dependencies
    depends_list = []
    if auth_dependency:
        depends_list.append(auth_dependency)
    depends_list = depends_list if depends_list else None

    # Create example response
    create_example = create_example_response(examples, "create")

    # Register the route
    @router.post(
        "",
        summary=f"Create {resource_name}",
        description=f"""
        Creates a new {resource_name} or batch of {resource_name_plural}.
        
        Supports two formats:
        1. Single creation: `{{{resource_name}: {{...}}}}`
        2. Batch creation: `{{{resource_name_plural}: [{{...}}, {{...}}, ...]}}`
        
        Returns the created resource(s) with generated ID(s).
        """,
        response_model=Union[
            network_model_cls.ResponseSingle, network_model_cls.ResponsePlural
        ],
        status_code=status.HTTP_201_CREATED,
        responses={
            status.HTTP_201_CREATED: {
                "description": f"{resource_name.title()} successfully created",
                "content": {"application/json": create_example},
            },
            status.HTTP_400_BAD_REQUEST: {
                "description": f"Invalid {resource_name} configuration provided",
            },
            status.HTTP_409_CONFLICT: {
                "description": f"{resource_name.title()} with the provided name already exists",
            },
        },
        dependencies=depends_list,
    )
    async def create_resource(
        body: Union[
            network_model_cls.POST, List[network_model_cls.POST], Dict[str, Any]
        ] = Body(...),
        manager=Depends(manager_factory),
    ):
        """Create a new resource or batch of resources."""
        try:
            # Handle batch creation from list format
            if isinstance(body, list):
                items = []
                for item in body:
                    item_data = extract_body_data(
                        item, resource_name, resource_name_plural
                    )
                    items.append(manager.create(**item_data))
                return network_model_cls.ResponsePlural(**{resource_name_plural: items})

            # Handle batch creation from dict format with pluralized key
            elif isinstance(body, dict) and resource_name_plural in body:
                items = []
                for item_data in body[resource_name_plural]:
                    items.append(manager.create(**item_data))
                return network_model_cls.ResponsePlural(**{resource_name_plural: items})

            # Handle single resource creation
            else:
                item_data = extract_body_data(body, resource_name, resource_name_plural)
                result = manager.create(**item_data)
                return network_model_cls.ResponseSingle(**{resource_name: result})
        except Exception as err:
            handle_resource_operation_error(err)


def register_get_route(
    router: APIRouter,
    resource_name: str,
    network_model_cls: Any,
    manager_factory: Callable,
    examples: Dict[str, Dict[str, Any]],
    manager_property: Optional[str] = None,
    auth_dependency: Optional[Any] = None,
) -> None:
    """
    Register the GET route for retrieving a single resource.

    Args:
        router: The FastAPI router
        resource_name: Name of the resource in singular form
        network_model_cls: The network model class
        manager_factory: Function that returns manager instance
        examples: Dict of examples for documentation
        manager_property: Optional property path to access on manager
        auth_dependency: Optional authentication dependency
    """
    # Handle dependencies
    depends_list = []
    if auth_dependency:
        depends_list.append(auth_dependency)
    depends_list = depends_list if depends_list else None

    # Create example response
    get_example = create_example_response(examples, "get")

    @router.get(
        "/{id}",
        summary=f"Get {resource_name} details",
        description=f"""
        Retrieves detailed information about a specific {resource_name}.
        
        Supports optional query parameters:
        - `include`: List of related entities to include
        - `fields`: List of specific fields to include in the response
        """,
        response_model=network_model_cls.ResponseSingle,
        status_code=status.HTTP_200_OK,
        responses={
            status.HTTP_200_OK: {
                "description": f"{resource_name.title()} details retrieved successfully",
                "content": {"application/json": get_example},
            },
            status.HTTP_404_NOT_FOUND: {
                "description": f"{resource_name.title()} with specified ID not found",
            },
        },
        dependencies=depends_list,
    )
    async def get_resource(
        id: str = Path(..., description=f"{resource_name.title()} ID"),
        include: Optional[List[str]] = Query(
            None, description="Related entities to include"
        ),
        fields: Optional[List[str]] = Query(
            None, description="Fields to include in response"
        ),
        manager=Depends(manager_factory),
    ):
        """Get a specific resource by ID."""
        try:
            # Get the appropriate manager
            if manager_property:
                for prop in manager_property.split("."):
                    manager = getattr(manager, prop)

            return network_model_cls.ResponseSingle(
                **{resource_name: manager.get(id=id, include=include, fields=fields)}
            )
        except Exception as err:
            handle_resource_operation_error(err)


def register_list_route(
    router: APIRouter,
    resource_name: str,
    resource_name_plural: str,
    network_model_cls: Any,
    manager_factory: Callable,
    examples: Dict[str, Dict[str, Any]],
    manager_property: Optional[str] = None,
    auth_dependency: Optional[Any] = None,
) -> None:
    """
    Register the GET route for listing resources.

    Args:
        router: The FastAPI router
        resource_name: Name of the resource in singular form
        resource_name_plural: Name of the resource in plural form
        network_model_cls: The network model class
        manager_factory: Function that returns manager instance
        examples: Dict of examples for documentation
        manager_property: Optional property path to access on manager
        auth_dependency: Optional authentication dependency
    """
    # Handle dependencies
    depends_list = []
    if auth_dependency:
        depends_list.append(auth_dependency)
    depends_list = depends_list if depends_list else None

    # Create example response
    list_example = create_example_response(examples, "list")

    @router.get(
        "",
        summary=f"List {resource_name_plural}",
        description=f"""
        Retrieves a paginated list of {resource_name_plural}.
        
        Supports filtering, pagination, and sorting:
        - `include`: List of related entities to include
        - `fields`: List of specific fields to include in the response
        - `offset`: Number of items to skip (for pagination)
        - `limit`: Maximum number of items to return
        - `sort_by`: Field to sort results by
        - `sort_order`: Sort direction ('asc' or 'desc')
        """,
        response_model=network_model_cls.ResponsePlural,
        status_code=status.HTTP_200_OK,
        responses={
            status.HTTP_200_OK: {
                "description": f"List of {resource_name_plural} retrieved successfully",
                "content": {"application/json": list_example},
            },
        },
        dependencies=depends_list,
    )
    async def list_resources(
        include: Optional[List[str]] = Query(
            None, description="Related entities to include"
        ),
        fields: Optional[List[str]] = Query(
            None, description="Fields to include in response"
        ),
        offset: int = Query(0, ge=0, description="Number of items to skip"),
        limit: int = Query(
            100, ge=1, le=1000, description="Maximum number of items to return"
        ),
        sort_by: Optional[str] = Query(None, description="Field to sort by"),
        sort_order: Optional[str] = Query(
            "asc", description="Sort order (asc or desc)"
        ),
        manager=Depends(manager_factory),
    ):
        """List resources with pagination and filtering options."""
        try:
            # Get the appropriate manager
            actual_manager = get_manager(manager, manager_property)

            return network_model_cls.ResponsePlural(
                **{
                    resource_name_plural: actual_manager.list(
                        include=include,
                        fields=fields,
                        offset=offset,
                        limit=limit,
                        sort_by=sort_by,
                        sort_order=sort_order,
                    )
                }
            )
        except Exception as err:
            handle_resource_operation_error(err)


def register_search_route(
    router: APIRouter,
    resource_name: str,
    resource_name_plural: str,
    network_model_cls: Any,
    manager_factory: Callable,
    examples: Dict[str, Dict[str, Any]],
    manager_property: Optional[str] = None,
    auth_dependency: Optional[Any] = None,
) -> None:
    """
    Register the POST /search route for searching resources.

    Args:
        router: The FastAPI router
        resource_name: Name of the resource in singular form
        resource_name_plural: Name of the resource in plural form
        network_model_cls: The network model class
        manager_factory: Function that returns manager instance
        examples: Dict of examples for documentation
        manager_property: Optional property path to access on manager
        auth_dependency: Optional authentication dependency
    """
    # Handle dependencies
    depends_list = []
    if auth_dependency:
        depends_list.append(auth_dependency)
    depends_list = depends_list if depends_list else None

    # Create example response
    search_example = create_example_response(examples, "search")

    @router.post(
        "/search",
        summary=f"Search {resource_name_plural}",
        description=f"""
        Search for {resource_name_plural} using advanced criteria.
        
        Allows complex filtering with field-specific criteria in the request body.
        Also supports pagination, sorting, and field selection via query parameters:
        - `include`: List of related entities to include
        - `fields`: List of specific fields to include in the response
        - `offset`: Number of items to skip (for pagination)
        - `limit`: Maximum number of items to return
        - `sort_by`: Field to sort results by
        - `sort_order`: Sort direction ('asc' or 'desc')
        """,
        response_model=network_model_cls.ResponsePlural,
        status_code=status.HTTP_200_OK,
        responses={
            status.HTTP_200_OK: {
                "description": f"Search results retrieved successfully",
                "content": {"application/json": search_example},
            },
            status.HTTP_400_BAD_REQUEST: {
                "description": "Invalid search criteria provided",
            },
        },
        dependencies=depends_list,
    )
    async def search_resources(
        criteria: network_model_cls.SEARCH = Body(...),
        include: Optional[List[str]] = Query(
            None, description="Related entities to include"
        ),
        fields: Optional[List[str]] = Query(
            None, description="Fields to include in response"
        ),
        offset: int = Query(0, ge=0, description="Number of items to skip"),
        limit: int = Query(
            100, ge=1, le=1000, description="Maximum number of items to return"
        ),
        sort_by: Optional[str] = Query(None, description="Field to sort by"),
        sort_order: Optional[str] = Query(
            "asc", description="Sort order (asc or desc)"
        ),
        manager=Depends(manager_factory),
    ):
        """Search for resources using specified criteria with pagination and sorting."""
        try:
            # Get the appropriate manager
            actual_manager = get_manager(manager, manager_property)

            # Extract search data from criteria
            search_data = extract_body_data(
                criteria, resource_name, resource_name_plural
            )

            return network_model_cls.ResponsePlural(
                **{
                    resource_name_plural: actual_manager.search(
                        include=include,
                        fields=fields,
                        offset=offset,
                        limit=limit,
                        sort_by=sort_by,
                        sort_order=sort_order,
                        **search_data,
                    )
                }
            )
        except Exception as err:
            handle_resource_operation_error(err)


def register_update_route(
    router: APIRouter,
    resource_name: str,
    network_model_cls: Any,
    manager_factory: Callable,
    examples: Dict[str, Dict[str, Any]],
    manager_property: Optional[str] = None,
    auth_dependency: Optional[Any] = None,
) -> None:
    """
    Register the PUT route for updating resources.

    Args:
        router: The FastAPI router
        resource_name: Name of the resource in singular form
        network_model_cls: The network model class
        manager_factory: Function that returns manager instance
        examples: Dict of examples for documentation
        manager_property: Optional property path to access on manager
        auth_dependency: Optional authentication dependency
    """
    # Handle dependencies
    depends_list = []
    if auth_dependency:
        depends_list.append(auth_dependency)
    depends_list = depends_list if depends_list else None

    # Create example response
    update_example = create_example_response(examples, "update")

    @router.put(
        "/{id}",
        summary=f"Update {resource_name}",
        description=f"""
        Updates an existing {resource_name}.
        
        Provide the resource ID in the URL path and the updated fields in the request body.
        Only the fields that need to be changed should be included in the request.
        """,
        response_model=network_model_cls.ResponseSingle,
        status_code=status.HTTP_200_OK,
        responses={
            status.HTTP_200_OK: {
                "description": f"{resource_name.title()} successfully updated",
                "content": {"application/json": update_example},
            },
            status.HTTP_400_BAD_REQUEST: {
                "description": f"Invalid {resource_name} configuration provided",
            },
            status.HTTP_404_NOT_FOUND: {
                "description": f"{resource_name.title()} with specified ID not found",
            },
            status.HTTP_409_CONFLICT: {
                "description": f"Update would create a name conflict with another {resource_name}",
            },
        },
        dependencies=depends_list,
    )
    async def update_resource(
        id: str = Path(..., description=f"{resource_name.title()} ID"),
        body: network_model_cls.PUT = Body(...),
        manager=Depends(manager_factory),
    ):
        """Update an existing resource."""
        try:
            # Get the appropriate manager
            actual_manager = get_manager(manager, manager_property)

            # Extract update data from body
            update_data = extract_body_data(
                body, resource_name, pluralizer.plural(resource_name)
            )

            return network_model_cls.ResponseSingle(
                **{resource_name: actual_manager.update(id, **update_data)}
            )
        except Exception as err:
            handle_resource_operation_error(err)


def register_delete_route(
    router: APIRouter,
    resource_name: str,
    manager_factory: Callable,
    manager_property: Optional[str] = None,
    auth_dependency: Optional[Any] = None,
) -> None:
    """
    Register the DELETE route for deleting resources.

    Args:
        router: The FastAPI router
        resource_name: Name of the resource in singular form
        manager_factory: Function that returns manager instance
        manager_property: Optional property path to access on manager
        auth_dependency: Optional authentication dependency
    """
    # Handle dependencies
    depends_list = []
    if auth_dependency:
        depends_list.append(auth_dependency)
    depends_list = depends_list if depends_list else None

    @router.delete(
        "/{id}",
        summary=f"Delete {resource_name}",
        description=f"""
        Deletes a specific {resource_name} by ID.
        
        This operation is permanent and cannot be undone.
        """,
        status_code=status.HTTP_204_NO_CONTENT,
        responses={
            status.HTTP_204_NO_CONTENT: {
                "description": f"{resource_name.title()} successfully deleted"
            },
            status.HTTP_404_NOT_FOUND: {
                "description": f"{resource_name.title()} with specified ID not found",
            },
        },
        dependencies=depends_list,
    )
    async def delete_resource(
        id: str = Path(..., description=f"{resource_name.title()} ID"),
        manager=Depends(manager_factory),
    ):
        """Delete a resource."""
        try:
            # Get the appropriate manager
            actual_manager = get_manager(manager, manager_property)

            actual_manager.delete(id=id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except Exception as err:
            handle_resource_operation_error(err)


def register_batch_update_route(
    router: APIRouter,
    resource_name: str,
    resource_name_plural: str,
    network_model_cls: Any,
    manager_factory: Callable,
    examples: Dict[str, Dict[str, Any]],
    manager_property: Optional[str] = None,
    auth_dependency: Optional[Any] = None,
) -> None:
    """
    Register the PUT route for batch updating resources.

    Args:
        router: The FastAPI router
        resource_name: Name of the resource in singular form
        resource_name_plural: Name of the resource in plural form
        network_model_cls: The network model class
        manager_factory: Function that returns manager instance
        examples: Dict of examples for documentation
        manager_property: Optional property path to access on manager
        auth_dependency: Optional authentication dependency
    """
    # Handle dependencies
    depends_list = []
    if auth_dependency:
        depends_list.append(auth_dependency)
    depends_list = depends_list if depends_list else None

    # Create example response
    batch_update_example = create_example_response(examples, "batch_update")

    # Create a dynamic BatchUpdateModel with the resource name
    DynamicBatchUpdateModel = generate_batch_update_model(resource_name)

    @router.put(
        "",
        summary=f"Batch update {resource_name_plural}",
        description=f"""
        Updates multiple {resource_name_plural} in a single request.
        
        Provide a list of resource IDs to update and the fields to change.
        The same field values will be applied to all resources in the batch.
        
        Format:
        ```json
        {{
            "{resource_name}": {{
                "field1": "value1",
                "field2": "value2"
            }},
            "target_ids": ["id1", "id2", "id3"]
        }}
        ```
        """,
        response_model=network_model_cls.ResponsePlural,
        status_code=status.HTTP_200_OK,
        responses={
            status.HTTP_200_OK: {
                "description": f"{resource_name_plural.title()} successfully updated",
                "content": {"application/json": batch_update_example},
            },
            status.HTTP_400_BAD_REQUEST: {
                "description": f"Invalid {resource_name} configuration provided",
            },
            status.HTTP_404_NOT_FOUND: {
                "description": f"One or more {resource_name_plural} not found",
            },
        },
        dependencies=depends_list,
    )
    async def batch_update_resources(
        body: DynamicBatchUpdateModel = Body(...),
        manager=Depends(manager_factory),
    ):
        """Update multiple resources in a batch."""
        try:
            # Get the appropriate manager
            actual_manager = get_manager(manager, manager_property)

            # Extract the update data and target IDs
            update_data = getattr(body, resource_name)
            target_ids = body.target_ids

            # Prepare the items for batch update
            items = [{"id": id, "data": update_data} for id in target_ids]

            # Perform batch update
            updated_items = actual_manager.batch_update(items=items)

            return network_model_cls.ResponsePlural(
                **{resource_name_plural: updated_items}
            )
        except Exception as err:
            handle_resource_operation_error(err)


def register_batch_delete_route(
    router: APIRouter,
    resource_name: str,
    resource_name_plural: str,
    examples: Dict[str, Dict[str, Any]],
    manager_factory: Callable,
    manager_property: Optional[str] = None,
    auth_dependency: Optional[Any] = None,
) -> None:
    """
    Register the DELETE route for batch deleting resources.

    Args:
        router: The FastAPI router
        resource_name: Name of the resource in singular form
        resource_name_plural: Name of the resource in plural form
        examples: Dict of examples for documentation
        manager_factory: Function that returns manager instance
        manager_property: Optional property path to access on manager
        auth_dependency: Optional authentication dependency
    """
    # Handle dependencies
    depends_list = []
    if auth_dependency:
        depends_list.append(auth_dependency)
    depends_list = depends_list if depends_list else None

    # Create example response
    batch_delete_example = create_example_response(examples, "batch_delete")

    @router.delete(
        "",
        summary=f"Batch delete {resource_name_plural}",
        description=f"""
        Deletes multiple {resource_name_plural} in a single request.
        
        Provide a list of resource IDs to delete in the query parameters.
        This operation is permanent and cannot be undone.
        
        Format: `?target_ids=id1,id2,id3`
        """,
        status_code=status.HTTP_204_NO_CONTENT,
        responses={
            status.HTTP_204_NO_CONTENT: {
                "description": f"{resource_name_plural.title()} successfully deleted",
                "content": {"application/json": batch_delete_example},
            },
            status.HTTP_400_BAD_REQUEST: {
                "description": "Invalid request format, missing query parameter(s)",
            },
            status.HTTP_404_NOT_FOUND: {
                "description": f"One or more {resource_name_plural} not found",
            },
        },
        dependencies=depends_list,
    )
    async def batch_delete_resources(
        target_ids: str = Query(
            ...,
            description=f"Comma-separated list of {resource_name_plural} IDs to delete",
        ),
        manager=Depends(manager_factory),
    ):
        """Delete multiple resources in a batch."""
        try:
            # Get the appropriate manager
            actual_manager = get_manager(manager, manager_property)

            # Split the comma-separated IDs into a list
            ids_list = [id.strip() for id in target_ids.split(",") if id.strip()]
            if not ids_list:
                from endpoints.AbstractEndpointRouter import InvalidRequestError

                raise InvalidRequestError(
                    "No valid IDs provided in target_ids parameter"
                )

            actual_manager.batch_delete(ids=ids_list)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except Exception as err:
            handle_resource_operation_error(err)


def register_nested_create_route(
    router: APIRouter,
    resource_name: str,
    parent_param_name: str,
    network_model_cls: Any,
    manager_factory: Callable,
    examples: Dict[str, Dict[str, Any]],
    manager_property: Optional[str] = None,
    auth_dependency: Optional[Any] = None,
) -> None:
    """
    Register the POST route for creating resources under a parent.

    Args:
        router: The FastAPI router
        resource_name: Name of the resource in singular form
        parent_param_name: Name of the parent parameter
        network_model_cls: The network model class
        manager_factory: Function that returns manager instance
        examples: Dict of examples for documentation
        manager_property: Optional property path to access on manager
        auth_dependency: Optional authentication dependency
    """
    # Handle dependencies
    depends_list = []
    if auth_dependency:
        depends_list.append(auth_dependency)
    depends_list = depends_list if depends_list else None

    # Create example response
    create_example = create_example_response(examples, "create")

    # Get parent name from param name (e.g., "project_id" -> "project")
    parent_name = parent_param_name.replace("_id", "")

    @router.post(
        "",
        summary=f"Create {resource_name} for {parent_name}",
        description=f"""
        Creates a new {resource_name} under the specified {parent_name}.
        
        The {parent_name} ID is specified in the URL path.
        """,
        response_model=network_model_cls.ResponseSingle,
        status_code=status.HTTP_201_CREATED,
        responses={
            status.HTTP_201_CREATED: {
                "description": f"{resource_name.title()} successfully created",
                "content": {"application/json": create_example},
            },
            status.HTTP_400_BAD_REQUEST: {
                "description": f"Invalid {resource_name} configuration provided",
            },
            status.HTTP_404_NOT_FOUND: {
                "description": f"{parent_name.title()} not found",
            },
            status.HTTP_409_CONFLICT: {
                "description": f"{resource_name.title()} with the provided name already exists",
            },
        },
        dependencies=depends_list,
    )
    async def create_nested_resource(
        request: Request,
        body: network_model_cls.POST = Body(...),
        manager=Depends(manager_factory),
    ):
        """Create a new resource under a parent."""
        try:
            # Extract parent ID from path params using the correct name
            parent_id_value = request.path_params[parent_param_name]

            # Get the nested manager
            nested_manager = get_manager(manager, manager_property)

            # Extract data from request body
            resource_name_plural = pluralizer.plural(resource_name)
            item_data = extract_body_data(body, resource_name, resource_name_plural)

            # Add parent ID to the data
            item_data[parent_param_name] = parent_id_value

            # Create the resource
            result = nested_manager.create(**item_data)

            return network_model_cls.ResponseSingle(**{resource_name: result})
        except Exception as err:
            handle_resource_operation_error(err)


def register_nested_list_route(
    router: APIRouter,
    resource_name: str,
    resource_name_plural: str,
    parent_param_name: str,
    network_model_cls: Any,
    manager_factory: Callable,
    examples: Dict[str, Dict[str, Any]],
    manager_property: Optional[str] = None,
    auth_dependency: Optional[Any] = None,
) -> None:
    """
    Register the GET route for listing resources under a parent.

    Args:
        router: The FastAPI router
        resource_name: Name of the resource in singular form
        resource_name_plural: Name of the resource in plural form
        parent_param_name: Name of the parent parameter
        network_model_cls: The network model class
        manager_factory: Function that returns manager instance
        examples: Dict of examples for documentation
        manager_property: Optional property path to access on manager
        auth_dependency: Optional authentication dependency
    """
    # Handle dependencies
    depends_list = []
    if auth_dependency:
        depends_list.append(auth_dependency)
    depends_list = depends_list if depends_list else None

    # Create example response
    list_example = create_example_response(examples, "list")

    # Get parent name from param name (e.g., "project_id" -> "project")
    parent_name = parent_param_name.replace("_id", "")

    @router.get(
        "",
        summary=f"List {resource_name_plural} for {parent_name}",
        description=f"""
        Lists {resource_name_plural} under the specified {parent_name}.
        
        The {parent_name} ID is specified in the URL path.
        Supports filtering, pagination, and sorting:
        - `include`: List of related entities to include
        - `fields`: List of specific fields to include in the response
        - `offset`: Number of items to skip (for pagination)
        - `limit`: Maximum number of items to return
        - `sort_by`: Field to sort results by
        - `sort_order`: Sort direction ('asc' or 'desc')
        """,
        response_model=network_model_cls.ResponsePlural,
        status_code=status.HTTP_200_OK,
        responses={
            status.HTTP_200_OK: {
                "description": f"List of {resource_name_plural} retrieved successfully",
                "content": {"application/json": list_example},
            },
            status.HTTP_404_NOT_FOUND: {
                "description": f"{parent_name.title()} not found",
            },
        },
        dependencies=depends_list,
    )
    async def list_nested_resources(
        request: Request,
        include: Optional[List[str]] = Query(
            None, description="Related entities to include"
        ),
        fields: Optional[List[str]] = Query(
            None, description="Fields to include in response"
        ),
        offset: int = Query(0, ge=0, description="Number of items to skip"),
        limit: int = Query(
            100, ge=1, le=1000, description="Maximum number of items to return"
        ),
        sort_by: Optional[str] = Query(None, description="Field to sort by"),
        sort_order: Optional[str] = Query(
            "asc", description="Sort order (asc or desc)"
        ),
        manager=Depends(manager_factory),
    ):
        """List resources under a parent."""
        try:
            # Extract parent ID from path params using the correct name
            parent_id_value = request.path_params[parent_param_name]

            # Get the nested manager
            nested_manager = get_manager(manager, manager_property)

            # Search resources with parent ID filter
            results = nested_manager.search(
                include=include,
                fields=fields,
                offset=offset,
                limit=limit,
                sort_by=sort_by,
                sort_order=sort_order,
                # Pass parent ID filter directly as kwarg for filter_by
                **{parent_param_name: parent_id_value},
            )

            return network_model_cls.ResponsePlural(**{resource_name_plural: results})
        except Exception as err:
            handle_resource_operation_error(err)


def register_nested_search_route(
    router: APIRouter,
    resource_name: str,
    resource_name_plural: str,
    parent_param_name: str,
    network_model_cls: Any,
    manager_factory: Callable,
    examples: Dict[str, Dict[str, Any]],
    manager_property: Optional[str] = None,
    auth_dependency: Optional[Any] = None,
) -> None:
    """
    Register the POST /search route for searching resources under a parent.

    Args:
        router: The FastAPI router
        resource_name: Name of the resource in singular form
        resource_name_plural: Name of the resource in plural form
        parent_param_name: Name of the parent parameter
        network_model_cls: The network model class
        manager_factory: Function that returns manager instance
        examples: Dict of examples for documentation
        manager_property: Optional property path to access on manager
        auth_dependency: Optional authentication dependency
    """
    # Handle dependencies
    depends_list = []
    if auth_dependency:
        depends_list.append(auth_dependency)
    depends_list = depends_list if depends_list else None

    # Create example response
    search_example = create_example_response(examples, "search")

    # Get parent name from param name (e.g., "project_id" -> "project")
    parent_name = parent_param_name.replace("_id", "")

    @router.post(
        "/search",
        summary=f"Search {resource_name_plural} for {parent_name}",
        description=f"""
        Search for {resource_name_plural} under the specified {parent_name} using advanced criteria.
        
        The {parent_name} ID is specified in the URL path.
        Allows complex filtering with field-specific criteria in the request body.
        Also supports pagination, sorting, and field selection via query parameters.
        """,
        response_model=network_model_cls.ResponsePlural,
        status_code=status.HTTP_200_OK,
        responses={
            status.HTTP_200_OK: {
                "description": f"Search results retrieved successfully",
                "content": {"application/json": search_example},
            },
            status.HTTP_400_BAD_REQUEST: {
                "description": "Invalid search criteria provided",
            },
            status.HTTP_404_NOT_FOUND: {
                "description": f"{parent_name.title()} not found",
            },
        },
        dependencies=depends_list,
    )
    async def search_nested_resources(
        request: Request,
        criteria: network_model_cls.SEARCH = Body(...),
        include: Optional[List[str]] = Query(
            None, description="Related entities to include"
        ),
        fields: Optional[List[str]] = Query(
            None, description="Fields to include in response"
        ),
        offset: int = Query(0, ge=0, description="Number of items to skip"),
        limit: int = Query(
            100, ge=1, le=1000, description="Maximum number of items to return"
        ),
        sort_by: Optional[str] = Query(None, description="Field to sort by"),
        sort_order: Optional[str] = Query(
            "asc", description="Sort order (asc or desc)"
        ),
        manager=Depends(manager_factory),
    ):
        """Search for resources under a parent using specified criteria."""
        try:
            # Extract parent ID from path params using the correct name
            parent_id_value = request.path_params[parent_param_name]

            # Get the nested manager
            nested_manager = get_manager(manager, manager_property)

            # Extract search criteria
            search_data = extract_body_data(
                criteria, resource_name, resource_name_plural
            )

            # Add parent ID to search criteria
            search_data[parent_param_name] = parent_id_value

            # Search with combined criteria
            results = nested_manager.search(
                include=include,
                fields=fields,
                offset=offset,
                limit=limit,
                sort_by=sort_by,
                sort_order=sort_order,
                **search_data,
            )

            return network_model_cls.ResponsePlural(**{resource_name_plural: results})
        except Exception as err:
            handle_resource_operation_error(err)


def handle_resource_operation_error(err: Exception) -> None:
    """
    Handle resource operation errors and raise appropriate HTTP exceptions.

    Args:
        err: The exception to handle

    Raises:
        HTTPException: Appropriate HTTP exception based on the error
    """
    # Import locally to avoid circular imports
    from endpoints.AbstractEndpointRouter import ResourceOperationError

    if isinstance(err, ResourceOperationError):
        raise HTTPException(
            status_code=err.status_code,
            detail={"message": err.message, "details": err.details},
        )
    elif isinstance(err, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Validation error", "details": err.errors()},
        )
    elif isinstance(err, HTTPException):
        raise err
    else:
        logger.exception(f"Unexpected error during operation: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "An unexpected error occurred", "details": str(err)},
        )


def get_manager(manager: Any, manager_property: Optional[str]) -> Any:
    """
    Get the appropriate manager (base or nested property).

    Args:
        manager: The base manager instance
        manager_property: Property path to access on manager

    Returns:
        The appropriate manager for the router
    """
    if not manager_property:
        return manager

    for prop in manager_property.split("."):
        manager = getattr(manager, prop)
    return manager
