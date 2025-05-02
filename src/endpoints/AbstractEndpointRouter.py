import logging
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar, Union

from fastapi import APIRouter, status
from pluralizer import Pluralizer  # Add import
from pydantic import BaseModel, Field

from endpoints.StaticExampleFactory import ExampleGenerator
from lib.Pydantic2FastAPI import (
    AuthType,
    RouterConfig,
    create_example_response,
    create_router,
    extract_body_data,
    get_auth_dependency,
    get_manager,
    handle_resource_operation_error,
    register_batch_delete_route,
    register_batch_update_route,
    register_create_route,
    register_delete_route,
    register_get_route,
    register_list_route,
    register_nested_create_route,
    register_nested_list_route,
    register_nested_search_route,
    register_search_route,
    register_update_route,
)

# Set up logging
logger = logging.getLogger(__name__)

# Instantiate Pluralizer
pluralizer = Pluralizer()  # Add instance

# Generic type variables for network models
T = TypeVar("T", bound=BaseModel)
ResponseSingleT = TypeVar("ResponseSingleT", bound=BaseModel)
ResponsePluralT = TypeVar("ResponsePluralT", bound=BaseModel)


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

        # Create router config for Pydantic2FastAPI
        router_config = RouterConfig(
            prefix=prefix,
            tags=tags,
            manager_factory=manager_factory,
            network_model_cls=network_model_cls,
            manager_property=manager_property,
            resource_name=resource_name,
            example_overrides=example_overrides,
            routes_to_register=routes_to_register or self._get_default_routes(),
            auth_type=auth_type,
            parent_router=parent_router,
            parent_param_name=parent_param_name,
        )

        # Use Pydantic2FastAPI to create the base router
        base_router = create_router(router_config)

        # Initialize as an APIRouter with the same parameters as base_router
        super().__init__(
            prefix=base_router.prefix,
            tags=base_router.tags,
            responses=base_router.responses,
        )

        # Copy relevant attributes from router_config
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
        self.resource_name_plural = pluralizer.plural(resource_name)

        # Configure auth dependency based on auth_type
        self.auth_dependency = get_auth_dependency(self.auth_type)

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
        return get_auth_dependency(self.auth_type)

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
        """Get the appropriate manager (base or nested property)."""
        return get_manager(manager, self.manager_property)

    def _extract_body_data(
        self, body: Any, attribute_name: Optional[str] = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Extract data from a request body object."""
        if not attribute_name:
            attribute_name = self.resource_name

        return extract_body_data(body, attribute_name, self.resource_name_plural)

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
        """Handle resource operation errors and raise appropriate HTTP exceptions."""
        handle_resource_operation_error(err)

    def _create_example_response(self, operation: str) -> Optional[Dict[str, Any]]:
        """Create an example response for documentation."""
        return create_example_response(self.examples, operation)

    def _register_create_route(self) -> None:
        """Register the POST route for creating resources."""
        register_create_route(
            router=self,
            resource_name=self.resource_name,
            resource_name_plural=self.resource_name_plural,
            network_model_cls=self.network_model_cls,
            manager_factory=self.manager_factory,
            examples=self.examples,
            auth_dependency=self.auth_dependency,
        )

    def _register_get_route(self) -> None:
        """Register the GET route for retrieving a single resource."""
        register_get_route(
            router=self,
            resource_name=self.resource_name,
            network_model_cls=self.network_model_cls,
            manager_factory=self.manager_factory,
            examples=self.examples,
            manager_property=self.manager_property,
            auth_dependency=self.auth_dependency,
        )

    def _register_list_route(self) -> None:
        """Register the GET route for listing resources."""
        register_list_route(
            router=self,
            resource_name=self.resource_name,
            resource_name_plural=self.resource_name_plural,
            network_model_cls=self.network_model_cls,
            manager_factory=self.manager_factory,
            examples=self.examples,
            manager_property=self.manager_property,
            auth_dependency=self.auth_dependency,
        )

    def _register_search_route(self) -> None:
        """Register the POST /search route for searching resources."""
        register_search_route(
            router=self,
            resource_name=self.resource_name,
            resource_name_plural=self.resource_name_plural,
            network_model_cls=self.network_model_cls,
            manager_factory=self.manager_factory,
            examples=self.examples,
            manager_property=self.manager_property,
            auth_dependency=self.auth_dependency,
        )

    def _register_update_route(self) -> None:
        """Register the PUT route for updating resources."""
        register_update_route(
            router=self,
            resource_name=self.resource_name,
            network_model_cls=self.network_model_cls,
            manager_factory=self.manager_factory,
            examples=self.examples,
            manager_property=self.manager_property,
            auth_dependency=self.auth_dependency,
        )

    def _register_delete_route(self) -> None:
        """Register the DELETE route for removing resources."""
        register_delete_route(
            router=self,
            resource_name=self.resource_name,
            manager_factory=self.manager_factory,
            manager_property=self.manager_property,
            auth_dependency=self.auth_dependency,
        )

    def _register_batch_update_route(self) -> None:
        """Register the PUT route for batch updating resources."""
        register_batch_update_route(
            router=self,
            resource_name=self.resource_name,
            resource_name_plural=self.resource_name_plural,
            network_model_cls=self.network_model_cls,
            manager_factory=self.manager_factory,
            examples=self.examples,
            manager_property=self.manager_property,
            auth_dependency=self.auth_dependency,
        )

    def _register_batch_delete_route(self) -> None:
        """Register the DELETE route for batch removing resources."""
        register_batch_delete_route(
            router=self,
            resource_name=self.resource_name,
            resource_name_plural=self.resource_name_plural,
            examples=self.examples,
            manager_factory=self.manager_factory,
            manager_property=self.manager_property,
            auth_dependency=self.auth_dependency,
        )

    def create_nested_router(
        self,
        parent_prefix: str,
        parent_param_name: str,
        child_resource_name: str,
        manager_property: str,
        child_network_model_cls: Optional[Any] = None,
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
            child_network_model_cls: Optional network model class for the child resource
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
            child_resource_name_plural = pluralizer.plural(clean_child_name)

        # Use child model class if provided, otherwise fallback (though fallback is likely wrong)
        model_cls_to_use = child_network_model_cls or self.network_model_cls

        # Create the nested router
        nested_router = AbstractEPRouter(
            prefix=f"{parent_prefix}/{{{parent_param_name}}}/{child_resource_name}",
            tags=tags,
            manager_factory=self.manager_factory,
            network_model_cls=model_cls_to_use,
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
        """Register the POST route for creating resources under a parent."""
        register_nested_create_route(
            router=self,
            resource_name=self.resource_name,
            parent_param_name=parent_param_name,
            network_model_cls=self.network_model_cls,
            manager_factory=self.manager_factory,
            examples=self.examples,
            manager_property=self.manager_property,
            auth_dependency=self.auth_dependency,
        )

    def _register_nested_list_route(self, parent_param_name: str) -> None:
        """Register the GET route for listing resources under a parent."""
        register_nested_list_route(
            router=self,
            resource_name=self.resource_name,
            resource_name_plural=self.resource_name_plural,
            parent_param_name=parent_param_name,
            network_model_cls=self.network_model_cls,
            manager_factory=self.manager_factory,
            examples=self.examples,
            manager_property=self.manager_property,
            auth_dependency=self.auth_dependency,
        )

    def _register_nested_search_route(self, parent_param_name: str) -> None:
        """Register the POST /search route for searching resources under a parent."""
        register_nested_search_route(
            router=self,
            resource_name=self.resource_name,
            resource_name_plural=self.resource_name_plural,
            parent_param_name=parent_param_name,
            network_model_cls=self.network_model_cls,
            manager_factory=self.manager_factory,
            examples=self.examples,
            manager_property=self.manager_property,
            auth_dependency=self.auth_dependency,
        )

    def create_mirror_router(
        self,
        new_prefix: str,
        routes_to_register: Optional[List[str]] = None,
        network_model_cls: Optional[Any] = None,
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
            network_model_cls: Optional network model class to use for the mirror

        Returns:
            AbstractEPRouter instance with the same routes but different prefix
        """
        logger.debug(f"Creating mirror router with prefix {new_prefix}")

        # Use provided model class or default to self's
        model_cls_to_use = network_model_cls or self.network_model_cls

        # Create a new AbstractEPRouter with the same configuration but different prefix
        mirror_router = AbstractEPRouter(
            prefix=new_prefix,
            tags=self.tags,
            manager_factory=self.manager_factory,
            network_model_cls=model_cls_to_use,
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
            # Get the child's network model class from the nested config
            child_model_cls = nested.get("network_model_cls")
            if not child_model_cls:
                # Fallback or raise error if child model not specified
                # For now, let's log a warning and use the parent's, although this is likely incorrect.
                logger.warning(
                    f"Network model class not specified for nested resource '{nested_name}'. Falling back to parent's model class '{network_model_cls.__name__ if network_model_cls else 'None'}'."
                )
                child_model_cls = network_model_cls

            logger.debug(
                f"Creating nested router for {nested_name} under {resource_name}"
            )

            # Create the nested router
            nested_router = base_router.create_nested_router(
                parent_prefix=base_prefix,
                parent_param_name=f"{resource_name}_id",
                child_resource_name=nested_name,
                manager_property=nested_property,
                child_network_model_cls=child_model_cls,
                tags=nested_tags,
                auth_type=nested_auth,
                example_overrides=nested_examples,
            )

            routers[f"{resource_name}_{nested_name}"] = nested_router

            # Create mirror router if requested
            if nested.get("create_mirror", False):
                mirror_prefix = f"/v1/{nested_name}"
                # Mirror router should use the child's model class
                mirror_router = nested_router.create_mirror_router(
                    mirror_prefix, network_model_cls=child_model_cls
                )
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
