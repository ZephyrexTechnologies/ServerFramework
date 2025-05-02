import importlib
import inspect
import logging
import os
import sys
from abc import ABC
from inspect import Parameter, signature
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, Union

import semver
from pydantic import BaseModel, Field

from database.Base import Base
from extensions import AbstractProvider
from lib.Import import scoped_import


class Dependency(BaseModel):
    name: str = Field(..., description="Name of the extension this depends on.")
    friendly_name: str = Field(..., description="The friendly name of the dependency.")
    optional: bool = Field(False, description="Whether this dependency is optional.")
    reason: str = Field(
        "None specified.",
        description="The reason this extension is required and what it adds if optional.",
    )
    semver: Optional[str] = Field(
        None, description="Semantic version requirement (e.g., '>=1.0.0')"
    )


class EXT_Dependency(Dependency):
    """
    Represents a dependency of an extension.
    """

    def is_satisfied(self, loaded_extensions: Dict[str, str]) -> bool:
        """
        Check if this dependency is satisfied.

        Args:
            loaded_extensions: Dict mapping extension names to their versions

        Returns:
            bool: True if the dependency is satisfied
        """
        # Check if the extension is loaded
        if self.name not in loaded_extensions:
            return self.optional

        # If semver is specified, check version compatibility
        if self.semver:
            try:
                return semver.match(loaded_extensions[self.name], self.semver)
            except ValueError:
                # If semver matching fails, log a warning
                logging.warning(
                    f"Invalid semver requirement '{self.semver}' for dependency '{self.name}'"
                )
                return False

        # Extension is loaded but no semver specified
        return True


class APT_Dependency(Dependency):
    pass


class PIP_Dependency(Dependency):
    pass


# Define type for hook structure
HookPath = Tuple[str, str, str, str, str]  # layer, domain, entity, function, time
HookRegistry = Dict[HookPath, List[Callable]]


class AbstractExtension(ABC):
    """
    Abstract base class for all extensions.
    This class defines the common interface and functionality that all extensions should implement.
    Extensions serve as the bridge between the business logic layer and extension extensions.
    """

    # Extension metadata
    name: str = "abstract"
    version: str = "0.1.0"
    description: str = "Abstract extension base class"

    # Dependencies
    ext_dependencies: List[EXT_Dependency] = []
    pip_dependencies: List[PIP_Dependency] = []
    apt_dependencies: List[APT_Dependency] = []

    # Hooks registered by this extension
    registered_hooks: HookRegistry = {}

    # For extension component tracking
    db_tables: List[Type] = []

    # Extension registry for tracking instances
    extension_registry: Dict[str, "AbstractExtension"] = {}

    def __init__(
        self,
        **kwargs,
    ):
        self.ProviderCLS = (
            AbstractProvider  # The Provider abstraction for this extension's providers.
        )
        self.providers = (
            []
        )  # Things the extension can connect to (through a standard interface).
        self.abilities = {}  # Things the extension can do.
        self.db_classes = []
        self.bll_managers = {}
        self.ep_routers = {}

        # Store settings from kwargs
        self.settings = kwargs

        # Store metadata if provided
        self.metadata = kwargs.get("metadata", {})

        # Dynamically load all components
        self._load_providers()
        self._load_db_classes()
        self._load_bll_managers()
        self._load_ep_routers()

        # Discover and register hook methods
        self.__class__.discover_hooks(self.__class__)

        # Discover and register abilities
        self.discover_abilities()

        # Initialize extension-specific providers and settings
        self._initialize_extension()

        # Set attributes from kwargs for direct property access in tests
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_capabilities(self) -> Set[str]:
        """
        Get the capabilities of this extension.

        Returns:
            A set of capabilities supported by this extension
        """
        return {"base_capability"}

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get a specific metadata value.

        Args:
            key: The metadata key to retrieve
            default: Default value if key doesn't exist

        Returns:
            The metadata value or default
        """
        return self.metadata.get(key, default)

    @classmethod
    def get_extension_by_id(cls, extension_id: str) -> Optional["AbstractExtension"]:
        """
        Get an extension instance by its ID.

        Args:
            extension_id: The ID of the extension to retrieve

        Returns:
            The extension instance or None if not found
        """
        return cls.extension_registry.get(extension_id)

    @classmethod
    def get_extension_by_name(cls, name: str) -> Optional["AbstractExtension"]:
        """
        Get an extension instance by its name.

        Args:
            name: The name of the extension to retrieve

        Returns:
            The extension instance or None if not found
        """
        for extension in cls.extension_registry.values():
            if extension.name == name:
                return extension
        return None

    def on_initialize(self) -> bool:
        """
        Lifecycle method called when the extension is initialized.

        Returns:
            True if initialization was successful, False otherwise
        """
        return True

    def on_start(self) -> bool:
        """
        Lifecycle method called when the extension is started.

        Returns:
            True if start was successful, False otherwise
        """
        return True

    def on_stop(self) -> bool:
        """
        Lifecycle method called when the extension is stopped.

        Returns:
            True if stop was successful, False otherwise
        """
        return True

    @classmethod
    def check_dependencies(cls, loaded_extensions: Dict[str, str]) -> Dict[str, bool]:
        """
        Check if all required dependencies are loaded and version compatible.

        Args:
            loaded_extensions: Dict mapping extension names to their versions

        Returns:
            Dictionary mapping dependency names to whether they are satisfied
        """
        dependency_status = {}

        for dependency in cls.ext_dependencies:
            is_satisfied = dependency.is_satisfied(loaded_extensions)
            dependency_status[dependency.name] = is_satisfied

            if not is_satisfied and not dependency.optional:
                logging.warning(
                    f"Required dependency '{dependency.name}' for extension '{cls.name}' is not satisfied."
                )

        return dependency_status

    @classmethod
    def resolve_dependencies(
        cls, available_extensions: Dict[str, "AbstractExtension"]
    ) -> List[str]:
        """
        Resolve dependencies and determine the correct loading order.

        Args:
            available_extensions: Dict mapping extension names to extension classes

        Returns:
            List of extension names in the order they should be loaded
        """
        # Create dependency graph
        dependency_graph = {}
        for ext_name, ext_cls in available_extensions.items():
            dependencies = [
                dep.name for dep in ext_cls.ext_dependencies if not dep.optional
            ]
            dependency_graph[ext_name] = dependencies

        # Topological sort to determine correct loading order
        result = []
        visited = set()
        temp_visited = set()

        def visit(node):
            if node in temp_visited:
                raise ValueError(f"Circular dependency detected involving {node}")
            if node in visited:
                return

            temp_visited.add(node)

            for dependency in dependency_graph.get(node, []):
                if dependency in available_extensions:
                    visit(dependency)

            temp_visited.remove(node)
            visited.add(node)
            result.append(node)

        for ext_name in available_extensions:
            if ext_name not in visited:
                visit(ext_name)

        return result

    @classmethod
    def load_db_tables(cls) -> None:
        """
        Load database tables from the extension's DB_*.py files.
        """
        extension_module = cls.__module__
        base_module = ".".join(extension_module.split(".")[:-1])

        try:
            # Look for DB_*.py files in the same package
            db_module_name = f"{base_module}.DB_{cls.name}"
            db_module = importlib.import_module(db_module_name)

            # Find all Base subclasses in the module
            for name, obj in inspect.getmembers(db_module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, Base)
                    and obj != Base
                    and obj not in cls.db_tables
                ):
                    cls.db_tables.append(obj)
                    logging.debug(
                        f"Extension {cls.name} loaded DB table: {obj.__tablename__}"
                    )
        except (ImportError, AttributeError) as e:
            logging.debug(f"No DB tables found for extension {cls.name}: {str(e)}")

    @classmethod
    def load_bll_managers(cls) -> Dict[str, Type]:
        """
        Load business logic managers from the extension's BLL_*.py files.

        Returns:
            Dictionary mapping manager names to manager classes
        """
        extension_module = cls.__module__
        base_module = ".".join(extension_module.split(".")[:-1])
        managers = {}

        try:
            # Look for BLL_*.py files in the same package
            bll_module_name = f"{base_module}.BLL_{cls.name}"
            bll_module = importlib.import_module(bll_module_name)

            # Import AbstractBLLManager to check inheritance
            from logic.AbstractLogicManager import AbstractBLLManager

            # Find all AbstractBLLManager subclasses in the module
            for name, obj in inspect.getmembers(bll_module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, AbstractBLLManager)
                    and obj != AbstractBLLManager
                ):
                    managers[name] = obj
                    logging.debug(f"Extension {cls.name} loaded BLL manager: {name}")
        except (ImportError, AttributeError) as e:
            logging.debug(f"No BLL managers found for extension {cls.name}: {str(e)}")

        return managers

    @classmethod
    def load_domain_injections(cls) -> Dict[str, Dict[str, Any]]:
        """
        Load domain injections from the extension's BLL_Domain_*.py files.

        Returns:
            Dictionary mapping domain names to injection configurations
        """
        extension_module = cls.__module__
        base_module = ".".join(extension_module.split(".")[:-1])
        injections = {}

        try:
            # Look for BLL_Domain_*.py files in the same package
            domain_module_name = f"{base_module}.BLL_Domain_{cls.name}"
            domain_module = importlib.import_module(domain_module_name)

            # Find all domain injection configurations
            if hasattr(domain_module, "domain_injections"):
                injections = domain_module.domain_injections
                logging.debug(
                    f"Extension {cls.name} loaded domain injections: {list(injections.keys())}"
                )
        except (ImportError, AttributeError) as e:
            logging.debug(
                f"No domain injections found for extension {cls.name}: {str(e)}"
            )

        return injections

    @classmethod
    def load_ep_routers(cls) -> Dict[str, Type]:
        """
        Load endpoint routers from the extension's EP_*.py files.

        Returns:
            Dictionary mapping router names to router classes
        """
        extension_module = cls.__module__
        base_module = ".".join(extension_module.split(".")[:-1])
        routers = {}

        try:
            # Look for EP_*.py files in the same package
            ep_module_name = f"{base_module}.EP_{cls.name}"
            ep_module = importlib.import_module(ep_module_name)

            # Import AbstractEPRouter to check inheritance
            from endpoints.AbstractEndpointRouter import AbstractEPRouter

            # Find all AbstractEPRouter subclasses in the module
            for name, obj in inspect.getmembers(ep_module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, AbstractEPRouter)
                    and obj != AbstractEPRouter
                ):
                    routers[name] = obj
                    logging.debug(f"Extension {cls.name} loaded EP router: {name}")
        except (ImportError, AttributeError) as e:
            logging.debug(f"No EP routers found for extension {cls.name}: {str(e)}")

        return routers

    @classmethod
    def load_provider(cls) -> Union[Type, None]:
        """
        Load provider from the extension's PRV_*.py file.

        Returns:
            Provider class or None if not found
        """
        extension_module = cls.__module__
        base_module = ".".join(extension_module.split(".")[:-1])
        provider = None

        try:
            # Look for PRV_*.py file in the same package
            prv_module_name = f"{base_module}.PRV_{cls.name}"
            prv_module = importlib.import_module(prv_module_name)

            # Import AbstractProvider to check inheritance
            from extensions.AbstractProvider import AbstractProvider

            # Find the AbstractProvider subclass in the module
            for name, obj in inspect.getmembers(prv_module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, AbstractProvider)
                    and obj != AbstractProvider
                ):
                    provider = obj
                    logging.debug(f"Extension {cls.name} loaded provider: {name}")
                    break
        except (ImportError, AttributeError) as e:
            logging.debug(f"No provider found for extension {cls.name}: {str(e)}")

        return provider

    @staticmethod
    def hook(
        layer: str,  # "EP" || "BLL" || "DB"
        domain: str,  # The name of the file after the layer
        entity: str,  # The name of the entity / manager / router
        function: str,  # The name of the function - get/update/delete/etc for database
        time: str,  # "before" || "after"
    ) -> Callable:
        """
        Decorator to mark a method as a hook handler for a specific hook point.

        Usage:
            @AbstractExtension.hook("BLL", "Auth", "User", "get", "before")
            def handle_user_get(self, *args, **kwargs):
                # Hook implementation
                pass

        Args:
            layer: Layer identifier ("EP", "BLL", "DB")
            domain: Domain identifier (name of file after layer)
            entity: Entity identifier (name of entity/manager/router)
            function: Function identifier (function name or endpoint path)
            time: Timing identifier ("before" or "after")

        Returns:
            Decorator function that will mark the method as a hook handler
        """

        def decorator(method: Callable) -> Callable:
            # Store hook information directly on the method
            if not hasattr(method, "_hook_info"):
                method._hook_info = []

            hook_path = (layer, domain, entity, function, time)
            method._hook_info.append(hook_path)

            logging.debug(f"Decorated method {method.__name__} as hook for {hook_path}")
            return method

        return decorator

    @staticmethod
    def bll_hook(
        domain: str,
        entity: str,
        function: str = "get",
        time: str = "before",
    ) -> Callable:
        """
        Convenience decorator for business logic layer hooks.

        Usage:
            @AbstractExtension.bll_hook("Auth", "User", "create", "after")
            def after_user_create(self, user, **kwargs):
                # Hook implementation
                pass

        Args:
            domain: Domain identifier (name of file after BLL_)
            entity: Entity identifier (name of manager class)
            function: Function identifier (method name, defaults to "get")
            time: Timing identifier ("before" or "after", defaults to "before")

        Returns:
            Decorator function that will mark the method as a BLL hook handler
        """
        return AbstractExtension.hook("BLL", domain, entity, function, time)

    @staticmethod
    def ep_hook(
        domain: str,
        entity: str,
        function: str,
        time: str = "before",
    ) -> Callable:
        """
        Convenience decorator for endpoint layer hooks.

        Usage:
            @AbstractExtension.ep_hook("Auth", "User", "/users/{id}", "before")
            def before_get_user(self, request, **kwargs):
                # Hook implementation
                pass

        Args:
            domain: Domain identifier (name of file after EP_)
            entity: Entity identifier (name of router class)
            function: Function identifier (endpoint path)
            time: Timing identifier ("before" or "after", defaults to "before")

        Returns:
            Decorator function that will mark the method as an EP hook handler
        """
        return AbstractExtension.hook("EP", domain, entity, function, time)

    @staticmethod
    def db_hook(
        domain: str,
        entity: str,
        function: str = "update",
        time: str = "before",
    ) -> Callable:
        """
        Convenience decorator for database layer hooks.

        Usage:
            @AbstractExtension.db_hook("Auth", "User", "delete", "before")
            def before_delete_user(self, user_id, **kwargs):
                # Hook implementation
                pass

        Args:
            domain: Domain identifier (name of file after DB_)
            entity: Entity identifier (name of database model)
            function: Function identifier (operation type, defaults to "update")
            time: Timing identifier ("before" or "after", defaults to "before")

        Returns:
            Decorator function that will mark the method as a DB hook handler
        """
        return AbstractExtension.hook("DB", domain, entity, function, time)

    @classmethod
    def discover_hooks(cls, extension_class: Type["AbstractExtension"]) -> None:
        """
        Discover and register all hook methods in an extension class.

        This examines all methods in the class (and its parent classes) for methods
        that have been decorated with @AbstractExtension.hook and automatically
        registers them.

        Args:
            extension_class: The extension class to inspect for hook methods
        """
        for name, method in inspect.getmembers(
            extension_class, predicate=inspect.isfunction
        ):
            if hasattr(method, "_hook_info"):
                for hook_path in method._hook_info:
                    # Get an unbound method reference
                    if hook_path not in AbstractExtension.registered_hooks:
                        AbstractExtension.registered_hooks[hook_path] = []

                    # If this is a class method, we need to pass the class instance
                    # This wrapper will properly handle both instance methods and static/class methods
                    def create_handler(method_ref, class_ref):
                        def handler(*args, **kwargs):
                            if (
                                inspect.ismethod(method_ref)
                                and hasattr(method_ref, "__self__")
                                and method_ref.__self__ is class_ref
                            ):
                                # This is a class method (bound to the class)
                                return method_ref(*args, **kwargs)
                            elif inspect.isfunction(method_ref):
                                # This is an instance method (needs self) or a static method
                                if args and isinstance(args[0], class_ref):
                                    # Instance method with self already provided
                                    return method_ref(*args, **kwargs)
                                else:
                                    # Static method
                                    return method_ref(*args, **kwargs)
                            else:
                                raise TypeError(
                                    f"Unsupported method type for {method_ref}"
                                )

                        # Preserve the original method's metadata
                        handler.__name__ = method_ref.__name__
                        handler.__doc__ = method_ref.__doc__
                        return handler

                    handler = create_handler(method, extension_class)
                    AbstractExtension.registered_hooks[hook_path].append(handler)
                    logging.debug(
                        f"Discovered and registered hook {hook_path} -> {method.__name__}"
                    )

    @staticmethod
    def register_hook(
        layer: str,  # "EP" || "BLL" || "DB"
        domain: str,  # The name of the file after the layer
        entity: str,  # The name of the entity / manager / router
        function: str,  # The name of the function - get/update/delete/etc for database
        time: str,  # "before" || "after"
        handler: callable,
    ) -> None:
        """
        Register a hook handler for a specific hook point.

        Args:
            layer: Layer identifier ("EP", "BLL", "DB")
            domain: Domain identifier (name of file after layer)
            entity: Entity identifier (name of entity/manager/router)
            function: Function identifier (function name or endpoint path)
            time: Timing identifier ("before" or "after")
            handler: Function to call when the hook is triggered
        """
        hook_path = (layer, domain, entity, function, time)

        if hook_path not in AbstractExtension.registered_hooks:
            AbstractExtension.registered_hooks[hook_path] = []

        AbstractExtension.registered_hooks[hook_path].append(handler)
        logging.debug(f"Registered hook handler for {hook_path}")

    @staticmethod
    def trigger_hook(
        layer: str, domain: str, entity: str, function: str, time: str, *args, **kwargs
    ) -> List[Any]:
        """
        Trigger all handlers for a specific hook point.

        Args:
            layer: Layer identifier ("EP", "BLL", "DB")
            domain: Domain identifier (name of file after layer)
            entity: Entity identifier (name of entity/manager/router)
            function: Function identifier (function name or endpoint path)
            time: Timing identifier ("before" or "after")
            *args, **kwargs: Arguments to pass to the hook handlers

        Returns:
            List of results from all hook handlers
        """
        hook_path = (layer, domain, entity, function, time)
        results = []

        if hook_path in AbstractExtension.registered_hooks:
            for handler in AbstractExtension.registered_hooks[hook_path]:
                try:
                    result = handler(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    logging.error(f"Error in hook handler for {hook_path}: {str(e)}")

        return results

    def get_available_abilities(self) -> List[Dict[str, Any]]:
        """
        Get the list of available abilities for this extension.

        Returns:
            List of available ability dictionaries
        """
        if not self.abilities:
            return []

        available_abilities = []
        for ability_name, ability_function in self.abilities.items():
            # Check if the ability is enabled in the agent configuration
            if ability_name not in self.agent_config["abilities"]:
                self.agent_config["abilities"][ability_name] = "false"

            if str(self.agent_config["abilities"][ability_name]).lower() == "true":
                # Get ability arguments from the function signature
                ability_args = self._get_ability_args(ability_function)
                available_abilities.append(
                    {
                        "friendly_name": ability_name,
                        "name": ability_function.__name__,
                        "args": ability_args,
                        "enabled": True,
                    }
                )

        return available_abilities

    def _get_ability_args(self, ability_function: callable) -> Dict[str, Any]:
        """
        Extract ability arguments from a function.

        Args:
            ability_function: The function to extract arguments from

        Returns:
            Dictionary of argument names and default values
        """
        params = {}
        sig = signature(ability_function)
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if param.default == Parameter.empty:
                params[name] = ""
            else:
                params[name] = param.default
        return params

    async def execute_ability(
        self, ability_name: str, ability_args: Dict[str, Any] = None
    ) -> str:
        """
        Execute a ability with the given arguments.

        Args:
            ability_name: Name of the ability to execute
            ability_args: Arguments for the ability

        Returns:
            Result of the ability execution
        """
        if ability_args is None:
            ability_args = {}

        if ability_name not in self.abilities:
            return f"ability '{ability_name}' not found"

        ability_function = self.abilities[ability_name]

        # Prepare arguments
        valid_args = self._get_ability_args(ability_function)
        filtered_args = {}
        for arg_name in valid_args:
            if arg_name in ability_args:
                filtered_args[arg_name] = ability_args[arg_name]
            else:
                filtered_args[arg_name] = valid_args[arg_name]

        try:
            return await ability_function(**filtered_args)
        except Exception as e:
            logging.error(f"Error executing ability '{ability_name}': {str(e)}")
            return f"Error executing ability '{ability_name}': {str(e)}"

    def _load_providers(self) -> None:
        """
        Dynamically load all provider classes from PRV_*.py files in the extension's directory.
        """
        extension_module = self.__class__.__module__
        base_module = ".".join(extension_module.split(".")[:-1])

        try:
            # Using scoped_import to load all provider modules
            provider_scope = f"extensions.{self.__class__.name}"
            imported_modules, errors = scoped_import("PRV", [provider_scope])

            if errors:
                for file_path, error in errors:
                    logging.error(f"Error loading provider from {file_path}: {error}")

            # For each imported module, find AbstractProvider subclasses
            for module_name in imported_modules:
                module = sys.modules.get(module_name)
                if not module:
                    continue

                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, AbstractProvider)
                        and obj != AbstractProvider
                    ):
                        # Store the provider class
                        self.ProviderCLS = obj
                        logging.debug(
                            f"Extension {self.__class__.name} loaded provider class: {name}"
                        )

                        # Create an instance of the provider
                        try:
                            provider_instance = obj(extension_id=self.__class__.name)
                            self.providers.append(provider_instance)
                            logging.debug(
                                f"Extension {self.__class__.name} initialized provider: {name}"
                            )
                        except Exception as e:
                            logging.error(f"Failed to initialize provider {name}: {e}")
        except Exception as e:
            logging.error(
                f"Error loading providers for extension {self.__class__.name}: {e}"
            )

    def _load_db_classes(self) -> None:
        """
        Dynamically load all database classes from DB_*.py files in the extension's directory.
        """
        try:
            # Call the class method to load DB tables
            self.__class__.load_db_tables()
            # Store reference to the loaded tables
            self.db_classes = self.__class__.db_tables
        except Exception as e:
            logging.error(
                f"Error loading DB classes for extension {self.__class__.name}: {e}"
            )

    def _load_bll_managers(self) -> None:
        """
        Dynamically load all business logic managers from BLL_*.py files in the extension's directory.
        """
        try:
            # Call the class method to load BLL managers
            self.bll_managers = self.__class__.load_bll_managers()
        except Exception as e:
            logging.error(
                f"Error loading BLL managers for extension {self.__class__.name}: {e}"
            )

    def _load_ep_routers(self) -> None:
        """
        Dynamically load all endpoint routers from EP_*.py files in the extension's directory.
        """
        try:
            # Call the class method to load EP routers
            self.ep_routers = self.__class__.load_ep_routers()
        except Exception as e:
            logging.error(
                f"Error loading EP routers for extension {self.__class__.name}: {e}"
            )

    @classmethod
    def discover_extensions(cls) -> List[Type["AbstractExtension"]]:
        """
        Discover all extension classes in the extensions directory.

        Returns:
            List of extension classes
        """
        extensions = []
        extensions_dir = os.path.join(os.getcwd(), "extensions")

        if not os.path.isdir(extensions_dir):
            logging.warning(f"Extensions directory not found: {extensions_dir}")
            return extensions

        # Find all EXT_*.py files
        for filename in os.listdir(extensions_dir):
            if filename.startswith("EXT_") and filename.endswith(".py"):
                module_name = filename[:-3]  # Remove .py extension
                try:
                    # Import the module
                    module = importlib.import_module(f"extensions.{module_name}")

                    # Find the AbstractExtension subclass in the module
                    for name, obj in inspect.getmembers(module):
                        if (
                            inspect.isclass(obj)
                            and issubclass(obj, AbstractExtension)
                            and obj != AbstractExtension
                        ):
                            extensions.append(obj)
                            logging.debug(
                                f"Discovered extension: {obj.name} ({module_name})"
                            )
                            break
                except Exception as e:
                    logging.error(f"Error loading extension from {filename}: {str(e)}")

        return extensions

    @staticmethod
    def ability(name: Optional[str] = None, enabled: bool = True) -> Callable:
        """
        Decorator to mark a method as an extension ability.

        Usage:
            @AbstractExtension.ability(name="translate_text")
            async def translate(self, text, target_language="en"):
                # Ability implementation
                return translated_text

        Args:
            name: Optional friendly name for the ability (defaults to method name)
            enabled: Whether the ability is enabled by default

        Returns:
            Decorator function that will mark the method as an ability
        """

        def decorator(method: Callable) -> Callable:
            # Store ability information directly on the method
            ability_name = name or method.__name__

            method._ability_info = {"name": ability_name, "enabled": enabled}

            logging.debug(
                f"Decorated method {method.__name__} as ability '{ability_name}'"
            )
            return method

        return decorator

    def discover_abilities(self) -> None:
        """
        Discover and register all ability methods in the extension instance.

        This examines all methods in the class for methods that have been
        decorated with @AbstractExtension.ability and automatically
        registers them as abilities.
        """
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(method, "_ability_info"):
                ability_info = method._ability_info
                ability_name = ability_info["name"]

                # Register the ability
                self.abilities[ability_name] = method

                # Initialize ability configuration if not present
                if not hasattr(self, "agent_config"):
                    self.agent_config = {"abilities": {}}
                elif "abilities" not in self.agent_config:
                    self.agent_config["abilities"] = {}

                # Set default enabled state
                if ability_name not in self.agent_config["abilities"]:
                    self.agent_config["abilities"][ability_name] = str(
                        ability_info["enabled"]
                    ).lower()

                logging.debug(
                    f"Discovered and registered ability {ability_name} -> {method.__name__}"
                )

    def _initialize_extension(self) -> None:
        """
        Initialize the extension-specific providers and settings.

        This method is called after all components have been loaded and hooks and abilities
        have been discovered. Override this method in subclasses to perform extension-specific
        initialization.

        By default, it initializes the first provider if one is available.
        """
        # Default implementation - just initialize the first provider if available
        if self.providers and hasattr(self, "settings"):
            provider = self.providers[0]
            try:
                # Pass all settings to the provider
                logging.debug(
                    f"Initializing {self.__class__.name} provider {provider.__class__.__name__}"
                )

                # No additional initialization needed, provider is already instantiated
                logging.debug(
                    f"{self.__class__.name} provider {provider.__class__.__name__} initialized successfully"
                )
            except Exception as e:
                logging.error(
                    f"Error initializing {self.__class__.name} provider: {str(e)}"
                )
