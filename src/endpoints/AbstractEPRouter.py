import logging
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar, Union

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    Security,
    status,
)
from fastapi.security import APIKeyHeader, HTTPBasic
from pydantic import BaseModel, Field, ValidationError, create_model

from lib.Strings import pluralize
from logic.BLL_Auth import UserManager
from src.endpoints.StaticExampleFactory import ExampleGenerator

# Set up logging
logger = logging.getLogger(__name__)

# Generic type variables for network models
T = TypeVar("T", bound=BaseModel)
ResponseSingleT = TypeVar("ResponseSingleT", bound=BaseModel)
ResponsePluralT = TypeVar("ResponsePluralT", bound=BaseModel)


class AuthType(Enum):
    """Authentication types supported by the API."""

    NONE = "none"
    JWT = "jwt"
    API_KEY = "api_key"
    BASIC = "basic"


class MessageModel(BaseModel):
    """Standard message response model."""

    message: str


class BatchDeleteModel(BaseModel):
    """Model for batch delete requests.

    Format as defined in EP.schema.md:
    DELETE: `{target_ids: ["", "", ""]}`
    """

    target_ids: List[str] = Field(..., description="List of IDs to delete")


class BatchUpdateModel(BaseModel):
    """Model for batch update requests.

    Format as defined in EP.schema.md:
    PUT: `{entity_name: {}, target_ids: ["", "", ""]}`
    """

    resource: Dict[str, Any] = Field(..., description="Resource data to update")
    target_ids: List[str] = Field(..., description="List of IDs to update")


class ResourceOperationError(Exception):
    """Base exception for resource operation errors."""

    def __init__(
        self, message: str, status_code: int, details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ResourceNotFoundError(ResourceOperationError):
    """Exception raised when a resource is not found."""

    def __init__(
        self,
        resource_name: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=f"{resource_name.title()} with ID '{resource_id}' not found",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ResourceConflictError(ResourceOperationError):
    """Exception raised when a resource conflict occurs."""

    def __init__(
        self,
        resource_name: str,
        conflict_type: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=f"{resource_name.title()} {conflict_type} conflict",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class InvalidRequestError(ResourceOperationError):
    """Exception raised when a request is invalid."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class AbstractEPRouter(APIRouter, Generic[T]):
    """
    Abstract endpoint router that implements standard CRUD operations following the patterns
    outlined in EP.schema.md and EP.patterns.md.

    This class provides a reusable implementation of standard API endpoints
    to reduce code duplication across resource-based routers. It follows
    RESTful patterns and provides consistent behavior across different resources.

    Features:
    - Standard CRUD operations (create, read, update, delete)
    - Batch operations for create, update, and delete
    - Search functionality
    - Support for nested resources
    - Consistent error handling
    - Authentication integration
    - Example generation for documentation
    """

    def __init__(
        self,
        prefix: str,
        tags: List[str],
        manager_factory: Callable,
        network_model_cls: Any,
        manager_property: Optional[str] = None,
        resource_name: str = None,
        example_overrides: Optional[Dict[str, Dict]] = None,
        routes_to_register: Optional[List[str]] = None,
        auth_type: AuthType = AuthType.JWT,
        parent_router: Optional["AbstractEPRouter"] = None,
        parent_param_name: Optional[str] = None,
    ):
        """
        Initialize the abstract router.

        Args:
            prefix: URL prefix for all routes (e.g., "/v1/conversation")
            tags: OpenAPI tags for documentation
            manager_factory: Function that returns manager instance
            network_model_cls: NetworkModel class with POST, PUT, SEARCH, Response classes
            manager_property: For nested resources, property path to access on manager
            resource_name: Name of resource in singular form (derived from prefix if not provided)
            example_overrides: Optional dict of example overrides for specific operations
            routes_to_register: Optional list of routes to register (defaults to all routes if None)
            auth_type: Authentication type to use for this router (JWT, API Key, Basic, or None)
            parent_router: Optional parent router for nested resources
            parent_param_name: Optional parent parameter name for nested resources
        """
        logger.debug(f"Initializing AbstractEPRouter with prefix {prefix}")

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

        # Initialize as an APIRouter
        super().__init__(
            prefix=prefix,
            tags=tags,
            responses=standard_responses,
        )

        self.prefix = prefix
        self.tags = tags
        self.manager_factory = manager_factory
        self.network_model_cls = network_model_cls
        self.manager_property = manager_property
        self.routes_to_register = routes_to_register or self._get_default_routes()
        self.auth_type = auth_type
        self.parent_router = parent_router
        self.parent_param_name = parent_param_name

        # Derive resource names if not provided
        if not resource_name:
            resource_name = prefix.split("/")[-1]
            resource_name = resource_name.replace("-", "_")
        self.resource_name = resource_name
        self.resource_name_plural = pluralize(resource_name)

        # Configure auth dependency based on auth_type
        self.auth_dependency = self._get_auth_dependency()

        # Generate examples for documentation
        self.examples = self._generate_examples(example_overrides)

        # Register default routes if not a nested router
        if not parent_router:
            self._register_routes()

    def _get_default_routes(self) -> List[str]:
        """Get the default routes to register."""
        return [
            "create",
            "get",
            "list",
            "search",
            "update",
            "delete",
            "batch_update",
            "batch_delete",
        ]

    def _get_auth_dependency(self) -> Optional[Any]:
        """Get the authentication dependency based on auth_type."""
        if self.auth_type == AuthType.JWT:
            return Depends(UserManager.auth)
        elif self.auth_type == AuthType.API_KEY:
            return Security(APIKeyHeader(name="X-API-Key"))
        elif self.auth_type == AuthType.BASIC:
            return Security(HTTPBasic())
        else:
            return None

    def _generate_examples(
        self, overrides: Optional[Dict[str, Dict]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Generate examples for documentation with optional overrides."""
        logger.debug(f"Generating examples for {self.resource_name}")
        examples = ExampleGenerator.generate_operation_examples(
            self.network_model_cls, self.resource_name
        )

        # Apply overrides if provided
        if overrides:
            for op_name, override in overrides.items():
                if op_name in examples:
                    examples[op_name].update(override)

        return examples

    def get_manager(self, manager: Any) -> Any:
        """Get the appropriate manager (base or nested property).

        Args:
            manager: The base manager instance

        Returns:
            The appropriate manager for this router
        """
        if not self.manager_property:
            return manager

        for prop in self.manager_property.split("."):
            manager = getattr(manager, prop)
        return manager

    def _extract_body_data(
        self, body: Any, attribute_name: Optional[str] = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Extract data from a request body object.

        Handles different body formats:
        - Pydantic models with nested attributes
        - Plain dictionaries
        - Lists of models

        Args:
            body: The request body
            attribute_name: Optional attribute name to extract (defaults to resource_name)

        Returns:
            Extracted data as a dictionary or list of dictionaries
        """
        if not attribute_name:
            attribute_name = self.resource_name

        # Handle list of items
        if isinstance(body, list):
            return [self._extract_body_data(item, attribute_name) for item in body]

        # Handle plain dictionary
        if isinstance(body, dict):
            # Check if dictionary has the attribute_name as a key
            if attribute_name in body:
                return body[attribute_name]
            # Check if dictionary has resource_name_plural as a key
            elif self.resource_name_plural in body:
                return body[self.resource_name_plural]
            # Return the dictionary as is
            return body

        # Handle Pydantic model
        if hasattr(body, "__dict__"):
            # First try to get the attribute with the specified name
            if hasattr(body, attribute_name):
                attr_value = getattr(body, attribute_name)
                if hasattr(attr_value, "model_dump"):
                    return attr_value.model_dump(exclude_unset=True)
                return attr_value

            # Try to get the attribute with resource_name_plural
            if hasattr(body, self.resource_name_plural):
                attr_value = getattr(body, self.resource_name_plural)
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

    def _add_dependencies(self, depends_list: List = None) -> List:
        """Build the dependencies list for a route."""
        if depends_list is None:
            depends_list = []

        if self.auth_dependency:
            depends_list.append(self.auth_dependency)

        return depends_list if depends_list else None

    def _register_routes(self) -> None:
        """Register standard CRUD routes based on routes_to_register."""
        route_mapping = {
            "create": self._register_create_route,
            "get": self._register_get_route,
            "list": self._register_list_route,
            "search": self._register_search_route,
            "update": self._register_update_route,
            "delete": self._register_delete_route,
            "batch_update": self._register_batch_update_route,
            "batch_delete": self._register_batch_delete_route,
        }

        # Register only the requested routes
        for route in self.routes_to_register:
            if route in route_mapping:
                logger.debug(f"Registering route: {route} for {self.resource_name}")
                route_mapping[route]()

    def _handle_resource_operation_error(self, err: Exception) -> None:
        """
        Handle resource operation errors and raise appropriate HTTP exceptions.

        Args:
            err: The exception to handle

        Raises:
            HTTPException: Appropriate HTTP exception based on the error
        """
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

    def _create_example_response(self, operation: str) -> Optional[Dict[str, Any]]:
        """Create an example response for documentation."""
        if operation in self.examples:
            return {"example": self.examples.get(operation)}
        return None

    def _register_create_route(self) -> None:
        """Register the POST route for creating resources.

        Follows the pattern in EP.schema.md:
        - POST /v1/resource
        - Request body:
          - Single: `{resource_name: {}}`
          - Batch: `{resource_name_plural: [{}, {}, {}]}`
        """
        network_model = self.network_model_cls
        resource_name = self.resource_name
        resource_name_plural = self.resource_name_plural

        create_example = self._create_example_response("create")
        depends_list = self._add_dependencies()

        @self.post(
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
                network_model.ResponseSingle, network_model.ResponsePlural
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
                network_model.POST, List[network_model.POST], Dict[str, Any]
            ] = Body(...),
            manager=Depends(self.manager_factory),
        ):
            """Create a new resource or batch of resources."""
            try:
                base_manager = self.get_manager(manager)

                # Handle batch creation from list format
                if isinstance(body, list):
                    items = []
                    for item in body:
                        item_data = self._extract_body_data(item)
                        items.append(base_manager.create(**item_data))
                    return network_model.ResponsePlural(**{resource_name_plural: items})

                # Handle batch creation from dict format with pluralized key
                elif isinstance(body, dict) and resource_name_plural in body:
                    items = []
                    for item_data in body[resource_name_plural]:
                        items.append(base_manager.create(**item_data))
                    return network_model.ResponsePlural(**{resource_name_plural: items})

                # Handle single resource creation
                else:
                    item_data = self._extract_body_data(body)
                    result = base_manager.create(**item_data)
                    return network_model.ResponseSingle(**{resource_name: result})
            except Exception as err:
                self._handle_resource_operation_error(err)

    def _register_get_route(self) -> None:
        """Register the GET route for retrieving a single resource.

        Follows the pattern in EP.schema.md:
        - GET /v1/resource/{id}
        """
        network_model = self.network_model_cls
        resource_name = self.resource_name

        get_example = self._create_example_response("get")
        depends_list = self._add_dependencies()

        @self.get(
            "/{id}",
            summary=f"Get {resource_name} details",
            description=f"""
            Retrieves detailed information about a specific {resource_name}.
            
            Supports optional query parameters:
            - `include`: List of related entities to include
            - `fields`: List of specific fields to include in the response
            """,
            response_model=network_model.ResponseSingle,
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
            manager=Depends(self.manager_factory),
        ):
            """Get a specific resource by ID."""
            try:
                return network_model.ResponseSingle(
                    **{
                        resource_name: self.get_manager(manager).get(
                            id=id, include=include, fields=fields
                        )
                    }
                )
            except Exception as err:
                self._handle_resource_operation_error(err)

    def _register_list_route(self) -> None:
        """Register the GET route for listing resources.

        Follows the pattern in EP.schema.md:
        - GET /v1/resource
        """
        network_model = self.network_model_cls
        resource_name_plural = self.resource_name_plural

        list_example = self._create_example_response("list")
        depends_list = self._add_dependencies()

        @self.get(
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
            response_model=network_model.ResponsePlural,
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
            manager=Depends(self.manager_factory),
        ):
            """List resources with pagination and filtering options."""
            try:
                return network_model.ResponsePlural(
                    **{
                        resource_name_plural: self.get_manager(manager).list(
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
                self._handle_resource_operation_error(err)

    def _register_search_route(self) -> None:
        """Register the POST /search route for searching resources.

        Follows the pattern in EP.schema.md:
        - POST /v1/resource/search
        """
        network_model = self.network_model_cls
        resource_name_plural = self.resource_name_plural

        search_example = self._create_example_response("search")
        depends_list = self._add_dependencies()

        @self.post(
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
            response_model=network_model.ResponsePlural,
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
            criteria: network_model.SEARCH = Body(...),
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
            manager=Depends(self.manager_factory),
        ):
            """Search for resources using specified criteria with pagination and sorting."""
            try:
                base_manager = self.get_manager(manager)
                search_data = self._extract_body_data(criteria)

                return network_model.ResponsePlural(
                    **{
                        resource_name_plural: base_manager.search(
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
                self._handle_resource_operation_error(err)

    def _register_update_route(self) -> None:
        """Register the PUT route for updating resources.

        Follows the pattern in EP.schema.md:
        - PUT /v1/resource/{id}
        """
        network_model = self.network_model_cls
        resource_name = self.resource_name

        update_example = self._create_example_response("update")
        depends_list = self._add_dependencies()

        @self.put(
            "/{id}",
            summary=f"Update {resource_name}",
            description=f"""
            Updates an existing {resource_name}.
            
            Provide the resource ID in the URL path and the updated fields in the request body.
            Only the fields that need to be changed should be included in the request.
            """,
            response_model=network_model.ResponseSingle,
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
            body: network_model.PUT = Body(...),
            manager=Depends(self.manager_factory),
        ):
            """Update an existing resource."""
            try:
                base_manager = self.get_manager(manager)
                update_data = self._extract_body_data(body)

                return network_model.ResponseSingle(
                    **{resource_name: base_manager.update(id, **update_data)}
                )
            except Exception as err:
                self._handle_resource_operation_error(err)

    def _register_batch_update_route(self) -> None:
        """Register the PUT route for batch updating resources.

        Follows the pattern in EP.schema.md:
        - PUT /v1/resource
        - Request body: `{resource_name: {}, target_ids: ["", "", ""]}`
        """
        network_model = self.network_model_cls
        resource_name = self.resource_name
        resource_name_plural = self.resource_name_plural

        batch_update_example = self._create_example_response("batch_update")
        depends_list = self._add_dependencies()

        # Create a dynamic BatchUpdateModel with the resource name
        DynamicBatchUpdateModel = create_model(
            f"{resource_name.capitalize()}BatchUpdateModel",
            **{
                resource_name: (Dict[str, Any], ...),
                "target_ids": (List[str], ...),
            },
        )

        @self.put(
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
            response_model=network_model.ResponsePlural,
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
            manager=Depends(self.manager_factory),
        ):
            """Update multiple resources in a batch."""
            try:
                base_manager = self.get_manager(manager)

                # Extract the update data and target IDs
                update_data = getattr(body, resource_name)
                target_ids = body.target_ids

                # Prepare the items for batch update
                items = [{"id": id, "data": update_data} for id in target_ids]

                # Perform batch update
                updated_items = base_manager.batch_update(items=items)

                return network_model.ResponsePlural(
                    **{resource_name_plural: updated_items}
                )
            except Exception as err:
                self._handle_resource_operation_error(err)

    def _register_delete_route(self) -> None:
        """Register the DELETE route for removing resources.

        Follows the pattern in EP.schema.md:
        - DELETE /v1/resource/{id}
        """
        resource_name = self.resource_name
        depends_list = self._add_dependencies()

        @self.delete(
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
            manager=Depends(self.manager_factory),
        ):
            """Delete a resource."""
            try:
                self.get_manager(manager).delete(id=id)
                return Response(status_code=status.HTTP_204_NO_CONTENT)
            except Exception as err:
                self._handle_resource_operation_error(err)

    def _register_batch_delete_route(self) -> None:
        """Register the DELETE route for batch removing resources.

        Follows the pattern in EP.schema.md:
        - DELETE /v1/resource
        - Request body: `{target_ids: ["", "", ""]}`
        """
        resource_name_plural = self.resource_name_plural

        batch_delete_example = self._create_example_response("batch_delete")
        depends_list = self._add_dependencies()

        @self.delete(
            "",
            summary=f"Batch delete {resource_name_plural}",
            description=f"""
            Deletes multiple {resource_name_plural} in a single request.
            
            Provide a list of resource IDs to delete in the request body.
            This operation is permanent and cannot be undone.
            
            Format: `{{target_ids: ["id1", "id2", "id3"]}}`
            """,
            status_code=status.HTTP_204_NO_CONTENT,
            responses={
                status.HTTP_204_NO_CONTENT: {
                    "description": f"{resource_name_plural.title()} successfully deleted",
                    "content": {"application/json": batch_delete_example},
                },
                status.HTTP_400_BAD_REQUEST: {
                    "description": "Invalid request format",
                },
                status.HTTP_404_NOT_FOUND: {
                    "description": f"One or more {resource_name_plural} not found",
                },
            },
            dependencies=depends_list,
        )
        async def batch_delete_resources(
            body: BatchDeleteModel = Body(...),
            manager=Depends(self.manager_factory),
        ):
            """Delete multiple resources in a batch."""
            try:
                self.get_manager(manager).batch_delete(ids=body.target_ids)
                return Response(status_code=status.HTTP_204_NO_CONTENT)
            except Exception as err:
                self._handle_resource_operation_error(err)

    def create_nested_router(
        self,
        parent_prefix: str,
        parent_param_name: str,
        child_resource_name: str,
        manager_property: str,
        tags: Optional[List[str]] = None,
        routes_to_register: Optional[List[str]] = None,
        example_overrides: Optional[Dict[str, Dict]] = None,
        child_resource_name_plural: Optional[str] = None,
        auth_type: Optional[AuthType] = None,
    ) -> "AbstractEPRouter":
        """
        Create a router for a child resource nested under a parent resource.

        This method enables the creation of nested routes as seen in EP.schema.md:
        - /v1/project/{project_id}/conversation
        - /v1/conversation/{conversation_id}/message
        etc.

        Args:
            parent_prefix: Prefix of the parent router (e.g., "/v1/project")
            parent_param_name: Name of the parent parameter (e.g., "project_id")
            child_resource_name: Name of the child resource (e.g., "conversation")
            manager_property: Property path to access child manager (e.g., "project.conversation")
            tags: OpenAPI tags for documentation (defaults to parent tags)
            routes_to_register: Optional list of routes to register
            example_overrides: Optional dict of example overrides for specific operations
            child_resource_name_plural: Plural form of child resource name
            auth_type: Authentication type to use (defaults to parent auth_type)

        Returns:
            AbstractEPRouter instance for the nested resource
        """
        logger.debug(
            f"Creating nested router for {child_resource_name} under {parent_prefix}"
        )

        # Use parent tags if none provided
        if tags is None:
            tags = self.tags

        # Use parent auth_type if none provided
        if auth_type is None:
            auth_type = self.auth_type

        # Create clean resource names for variables
        clean_child_name = child_resource_name.replace("-", "_")

        # Determine plural form if not provided
        if not child_resource_name_plural:
            child_resource_name_plural = pluralize(clean_child_name)

        # Create the nested router
        nested_router = AbstractEPRouter(
            prefix=f"{parent_prefix}/{{{parent_param_name}}}/{child_resource_name}",
            tags=tags,
            manager_factory=self.manager_factory,
            network_model_cls=self.network_model_cls,
            manager_property=manager_property,
            resource_name=clean_child_name,
            example_overrides=example_overrides,
            routes_to_register=routes_to_register,
            auth_type=auth_type,
            parent_router=self,
            parent_param_name=parent_param_name,
        )

        # Register custom nested routes
        nested_router._register_nested_routes(parent_param_name)

        return nested_router

    def _register_nested_routes(self, parent_param_name: str) -> None:
        """Register routes for nested resources.

        Args:
            parent_param_name: Name of the parent parameter (e.g., "project_id")
        """
        route_mapping = {
            "create": lambda: self._register_nested_create_route(parent_param_name),
            "list": lambda: self._register_nested_list_route(parent_param_name),
            "get": self._register_get_route,
            "update": self._register_update_route,
            "delete": self._register_delete_route,
            "search": lambda: self._register_nested_search_route(parent_param_name),
        }

        # Register only the requested routes
        for route in self.routes_to_register:
            if route in route_mapping:
                logger.debug(
                    f"Registering nested route: {route} for {self.resource_name}"
                )
                route_mapping[route]()

    def _register_nested_create_route(self, parent_param_name: str) -> None:
        """Register the POST route for creating resources under a parent.

        Follows the pattern in EP.schema.md:
        - POST /v1/parent/{parent_id}/resource
        """
        network_model = self.network_model_cls
        resource_name = self.resource_name

        create_example = self._create_example_response("create")
        depends_list = self._add_dependencies()

        parent_name = parent_param_name.replace("_id", "")

        @self.post(
            "",
            summary=f"Create {resource_name} for {parent_name}",
            description=f"""
            Creates a new {resource_name} under the specified {parent_name}.
            
            The {parent_name} ID is specified in the URL path.
            """,
            response_model=network_model.ResponseSingle,
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
            parent_id: str = Path(..., description=f"{parent_name.title()} ID"),
            body: network_model.POST = Body(...),
            manager=Depends(self.manager_factory),
        ):
            """Create a new resource under a parent."""
            try:
                # Get the nested manager
                nested_manager = self.get_manager(manager)

                # Extract data from request body
                item_data = self._extract_body_data(body)

                # Add parent ID to the data
                item_data[parent_param_name] = parent_id

                # Create the resource
                result = nested_manager.create(**item_data)

                return network_model.ResponseSingle(**{resource_name: result})
            except Exception as err:
                self._handle_resource_operation_error(err)

    def _register_nested_list_route(self, parent_param_name: str) -> None:
        """Register the GET route for listing resources under a parent.

        Follows the pattern in EP.schema.md:
        - GET /v1/parent/{parent_id}/resource
        """
        network_model = self.network_model_cls
        resource_name_plural = self.resource_name_plural

        list_example = self._create_example_response("list")
        depends_list = self._add_dependencies()

        parent_name = parent_param_name.replace("_id", "")

        @self.get(
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
            response_model=network_model.ResponsePlural,
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
            parent_id: str = Path(..., description=f"{parent_name.title()} ID"),
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
            manager=Depends(self.manager_factory),
        ):
            """List resources under a parent."""
            try:
                # Get the nested manager
                nested_manager = self.get_manager(manager)

                # Search resources with parent ID filter
                results = nested_manager.search(
                    include=include,
                    fields=fields,
                    offset=offset,
                    limit=limit,
                    sort_by=sort_by,
                    sort_order=sort_order,
                    **{parent_param_name: parent_id},
                )

                return network_model.ResponsePlural(**{resource_name_plural: results})
            except Exception as err:
                self._handle_resource_operation_error(err)

    def _register_nested_search_route(self, parent_param_name: str) -> None:
        """Register the POST /search route for searching resources under a parent.

        Follows the pattern in EP.schema.md but adapted for nested resources:
        - POST /v1/parent/{parent_id}/resource/search
        """
        network_model = self.network_model_cls
        resource_name_plural = self.resource_name_plural

        search_example = self._create_example_response("search")
        depends_list = self._add_dependencies()

        parent_name = parent_param_name.replace("_id", "")

        @self.post(
            "/search",
            summary=f"Search {resource_name_plural} for {parent_name}",
            description=f"""
            Search for {resource_name_plural} under the specified {parent_name} using advanced criteria.
            
            The {parent_name} ID is specified in the URL path.
            Allows complex filtering with field-specific criteria in the request body.
            Also supports pagination, sorting, and field selection via query parameters.
            """,
            response_model=network_model.ResponsePlural,
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
            parent_id: str = Path(..., description=f"{parent_name.title()} ID"),
            criteria: network_model.SEARCH = Body(...),
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
            manager=Depends(self.manager_factory),
        ):
            """Search for resources under a parent using specified criteria."""
            try:
                # Get the nested manager
                nested_manager = self.get_manager(manager)

                # Extract search criteria
                search_data = self._extract_body_data(criteria)

                # Add parent ID to search criteria
                search_data[parent_param_name] = parent_id

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

                return network_model.ResponsePlural(**{resource_name_plural: results})
            except Exception as err:
                self._handle_resource_operation_error(err)

    def create_mirror_router(
        self,
        new_prefix: str,
        routes_to_register: Optional[List[str]] = None,
    ) -> "AbstractEPRouter":
        """
        Create a mirror of this router with a standalone prefix.

        This allows accessing resources both through a parent and directly.
        For example:
        - Original: /v1/project/{project_id}/conversation
        - Mirror: /v1/conversation

        Args:
            new_prefix: The new prefix for the standalone router
            routes_to_register: Optional list of routes to register

        Returns:
            AbstractEPRouter instance with the same routes but different prefix
        """
        logger.debug(f"Creating mirror router with prefix {new_prefix}")

        # Create a new AbstractEPRouter with the same configuration but different prefix
        mirror_router = AbstractEPRouter(
            prefix=new_prefix,
            tags=self.tags,
            manager_factory=self.manager_factory,
            network_model_cls=self.network_model_cls,
            resource_name=self.resource_name,
            example_overrides=self.examples,
            routes_to_register=routes_to_register or self.routes_to_register,
            auth_type=self.auth_type,
        )

        return mirror_router

    def with_custom_route(
        self,
        method: str,
        path: str,
        endpoint: Callable,
        summary: str,
        description: str,
        response_model: Optional[Type] = None,
        status_code: int = status.HTTP_200_OK,
        responses: Optional[Dict] = None,
        dependencies: List = None,
        **kwargs,
    ) -> "AbstractEPRouter":
        """
        Add a custom route to the router.

        This method allows for adding custom endpoints that don't fit the standard CRUD pattern.

        Args:
            method: HTTP method (get, post, put, delete, patch)
            path: URL path
            endpoint: Route handler function
            summary: Short summary of what the endpoint does
            description: Detailed description of the endpoint
            response_model: Pydantic model for response validation
            status_code: HTTP status code for successful response
            responses: Dictionary of possible responses
            dependencies: List of dependencies for the endpoint
            **kwargs: Additional arguments to pass to the route decorator

        Returns:
            Self (for method chaining)
        """
        logger.debug(f"Adding custom {method.upper()} route at {path}")

        # Add auth dependency if not explicitly provided
        if dependencies is None:
            dependencies = []
            if self.auth_dependency:
                dependencies.append(self.auth_dependency)

        # Get the appropriate method from APIRouter
        route_method = getattr(self, method.lower())

        # Register the route
        route_method(
            path,
            summary=summary,
            description=description,
            response_model=response_model,
            status_code=status_code,
            responses=responses or {},
            dependencies=dependencies if dependencies else None,
            **kwargs,
        )(endpoint)

        return self


def create_router_tree(
    base_prefix: str,
    resource_name: str,
    tags: List[str],
    manager_factory: Callable,
    network_model_cls: Any,
    nested_resources: Optional[List[Dict[str, Any]]] = None,
    auth_type: AuthType = AuthType.JWT,
    example_overrides: Optional[Dict[str, Dict]] = None,
) -> Dict[str, AbstractEPRouter]:
    """
    Create a tree of routers for a resource and its nested resources.

    This helper function creates a base router and all its nested routers
    according to the patterns described in EP.schema.md.

    Args:
        base_prefix: Base URL prefix (e.g., "/v1/project")
        resource_name: Name of the resource (e.g., "project")
        tags: OpenAPI tags for documentation
        manager_factory: Function that returns manager instance
        network_model_cls: NetworkModel class with POST, PUT, SEARCH, Response classes
        nested_resources: List of nested resources with their configurations
        auth_type: Authentication type to use
        example_overrides: Optional dictionary of example overrides for specific operations

    Returns:
        Dictionary mapping router names to router instances
    """
    logger.info(f"Creating router tree for {resource_name} at {base_prefix}")

    # Create the base router
    base_router = AbstractEPRouter(
        prefix=base_prefix,
        tags=tags,
        manager_factory=manager_factory,
        network_model_cls=network_model_cls,
        resource_name=resource_name,
        auth_type=auth_type,
        example_overrides=example_overrides,
    )

    routers = {resource_name: base_router}

    # Create nested routers if specified
    if nested_resources:
        for nested in nested_resources:
            nested_name = nested["name"]
            nested_property = nested.get(
                "manager_property", f"{resource_name}.{nested_name}"
            )
            nested_tags = nested.get("tags", tags)
            nested_auth = nested.get("auth_type", auth_type)
            nested_examples = nested.get("example_overrides")

            logger.debug(
                f"Creating nested router for {nested_name} under {resource_name}"
            )

            # Create the nested router
            nested_router = base_router.create_nested_router(
                parent_prefix=base_prefix,
                parent_param_name=f"{resource_name}_id",
                child_resource_name=nested_name,
                manager_property=nested_property,
                tags=nested_tags,
                auth_type=nested_auth,
                example_overrides=nested_examples,
            )

            routers[f"{resource_name}_{nested_name}"] = nested_router

            # Create mirror router if requested
            if nested.get("create_mirror", False):
                mirror_prefix = f"{base_prefix.split('/')[0]}/{nested_name}"
                mirror_router = nested_router.create_mirror_router(mirror_prefix)
                routers[nested_name] = mirror_router

    return routers


def add_custom_routes(
    router: AbstractEPRouter, custom_routes: List[Dict[str, Any]]
) -> None:
    """
    Add custom routes to an existing router.

    Args:
        router: The router to add routes to
        custom_routes: List of route configurations
    """
    logger.info(f"Adding {len(custom_routes)} custom routes to router {router.prefix}")

    for route_config in custom_routes:
        router.with_custom_route(**route_config)
