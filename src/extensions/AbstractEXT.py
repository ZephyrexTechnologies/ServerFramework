import importlib
import inspect
import logging
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel
from database.Base import Base
    level=getenv("LOG_LEVEL"),
)
class ExtensionDependency(BaseModel):
    """
    Represents a dependency of an extension.
    optional: bool = Field(False, description="Whether this dependency is optional")
    semver: Optional[str] = Field(
        None, description="Semantic version requirement (e.g., '>=1.0.0')"
    )
        """
        Check if this dependency is satisfied.
        Args:
            loaded_extensions: Dict mapping extension names to their versions
        Returns:
        """
        # Check if the extension is loaded
        if self.name not in loaded_extensions:
        # If semver is specified, check version compatibility
        if self.semver:
                return semver.match(loaded_extensions[self.name], self.semver)
            except ValueError:
                # If semver matching fails, log a warning
                logging.warning(
                    f"Invalid semver requirement '{self.semver}' for dependency '{self.name}'"
                )
        # Extension is loaded but no semver specified
        return True
class AbstractExtension(ABC):
    """
    Abstract base class for all extensions.
    This class defines the common interface and functionality that all extensions should implement.
    Extensions serve as the bridge between the business logic layer and extension providers.
    """
    # Extension metadata
    name: str = "abstract"
    description: str = "Abstract extension base class"
    # Dependencies
    db_tables: List[Type[Base]] = []
    # Hooks registered by this extension
    registered_hooks: Dict[str, List[callable]] = {}
    def __init__(
        self,
        agent_name: str = "",
        agent_config: Optional[Dict[str, Any]] = None,
        conversation_name: str = "",
        conversation_id: Optional[str] = None,
        ApiClient: Any = None,
        user: str = env("DEFAULT_USER"),
        **kwargs,
        """
        Initialize the extension with common configuration parameters.
            agent_name: Name of the agent using the extension
            agent_id: ID of the agent using the extension
            conversation_name: Name of the conversation
            conversation_id: ID of the conversation
            ApiClient: API client for making requests
            api_key: API key
            user: User ID
            **kwargs: Additional extension-specific settings
        """
        self.agent_name = agent_name
        self.agent_id = agent_id
        self.agent_config = (
            agent_config if agent_config else {"settings": {}, "commands": {}}
        )
        self.conversation_name = conversation_name
        self.conversation_id = conversation_id
        self.api_key = api_key
        self.user = user
        self.settings = kwargs
        self.provider = None
        self.commands = {}
        self.bll_managers = {}
        self.ep_routers = {}
        # Initialize extension-specific providers and settings
        self._initialize_extension()
    @abstractmethod
    def _initialize_extension(self) -> None:
        """
        Initialize the extension-specific settings and providers.
        Should be implemented by each specific extension.
        """
        pass
    @classmethod
    def get_dependencies(cls) -> List[ExtensionDependency]:
        """
        Get the list of dependencies for this extension.
        Returns:
            List of ExtensionDependency objects
        """
        return cls.dependencies
    @classmethod
    def check_dependencies(cls, loaded_extensions: Dict[str, str]) -> Dict[str, bool]:
        Check if all required dependencies are loaded and version compatible.
        Args:
        Returns:
            Dictionary mapping dependency names to whether they are satisfied
        """
        dependency_status = {}
        for dependency in cls.dependencies:
            is_satisfied = dependency.is_satisfied(loaded_extensions)
            dependency_status[dependency.name] = is_satisfied
                logging.warning(
                    f"Required dependency '{dependency.name}' for extension '{cls.name}' is not satisfied."
                )
        return dependency_status
    def get_db_tables(cls) -> List[Type[Base]]:
        """
        Get the database tables defined by this extension.
        Returns:
        """
        return cls.db_tables
    @classmethod
    def get_table_by_name(cls, table_name: str) -> Optional[Type[Base]]:
        Get a database table by name.
        Args:
        Returns:
            SQLAlchemy model class or None if not found
        """
        for table in cls.db_tables:
                return table
        return None
    @classmethod
        """
        Load database tables from the extension's DB_*.py files.
        """
        extension_module = cls.__module__
        try:
            db_module_name = f"{base_module}.DB_{cls.name}"
            db_module = importlib.import_module(db_module_name)
            # Find all Base subclasses in the module
            for name, obj in inspect.getmembers(db_module):
                    inspect.isclass(obj)
                    and issubclass(obj, Base)
                    and obj != Base
                    and obj not in cls.db_tables
                    cls.db_tables.append(obj)
                    logging.debug(
                        f"Extension {cls.name} loaded DB table: {obj.__tablename__}"
                    )
            logging.debug(f"No DB tables found for extension {cls.name}: {str(e)}")
    @classmethod
        """
        Load business logic managers from the extension's BLL_*.py files.
        Returns:
            Dictionary mapping manager names to manager classes
        """
        extension_module = cls.__module__
        base_module = ".".join(extension_module.split(".")[:-1])
        try:
            # Look for BLL_*.py files in the same package
            bll_module_name = f"{base_module}.BLL_{cls.name}"
            bll_module = importlib.import_module(bll_module_name)
            # Import AbstractBLLManager to check inheritance
            from logic.AbstractBLLManager import AbstractBLLManager
            # Find all AbstractBLLManager subclasses in the module
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, AbstractBLLManager)
                    and obj != AbstractBLLManager
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
        try:
            # Look for BLL_Domain_*.py files in the same package
            domain_module_name = f"{base_module}.BLL_Domain_{cls.name}"
            domain_module = importlib.import_module(domain_module_name)
            if hasattr(domain_module, "domain_injections"):
                injections = domain_module.domain_injections
                logging.debug(
                    f"Extension {cls.name} loaded domain injections: {list(injections.keys())}"
                )
        except (ImportError, AttributeError) as e:
                f"No domain injections found for extension {cls.name}: {str(e)}"
            )
        return injections
    @classmethod
        """
        Load endpoint routers from the extension's EP_*.py files.
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
            from endpoints.AbstractEPRouter import AbstractEPRouter
            for name, obj in inspect.getmembers(ep_module):
                    inspect.isclass(obj)
                    and issubclass(obj, AbstractEPRouter)
                    and obj != AbstractEPRouter
                ):
                    logging.debug(f"Extension {cls.name} loaded EP router: {name}")
        except (ImportError, AttributeError) as e:
            logging.debug(f"No EP routers found for extension {cls.name}: {str(e)}")
        return routers
    @classmethod
    def load_provider(cls) -> Union[Type, None]:
        Load provider from the extension's PRV_*.py file.
        Returns:
            Provider class or None if not found
        """
        base_module = ".".join(extension_module.split(".")[:-1])
        provider = None
        try:
            # Look for PRV_*.py file in the same package
            prv_module_name = f"{base_module}.PRV_{cls.name}"
            prv_module = importlib.import_module(prv_module_name)
            # Import AbstractProvider to check inheritance
            from providers.AbstractPRV import AbstractProvider
            # Find the AbstractProvider subclass in the module
            for name, obj in inspect.getmembers(prv_module):
                    inspect.isclass(obj)
                    and obj != AbstractProvider
                ):
                    provider = obj
                    logging.debug(f"Extension {cls.name} loaded provider: {name}")
        except (ImportError, AttributeError) as e:
            logging.debug(f"No provider found for extension {cls.name}: {str(e)}")
        return provider
    @staticmethod
    def register_hook(hook_name: str, handler: callable) -> None:
        """
        Args:
            hook_name: Name of the hook point
            handler: Function to call when the hook is triggered
        """
            AbstractExtension.registered_hooks[hook_name] = []
        AbstractExtension.registered_hooks[hook_name].append(handler)
    @staticmethod
    def trigger_hook(hook_name: str, *args, **kwargs) -> List[Any]:
        """
        Trigger all handlers for a specific hook point.
        Args:
            hook_name: Name of the hook point
            *args, **kwargs: Arguments to pass to the hook handlers
        Returns:
            List of results from all hook handlers
        """
        results = []
            for handler in AbstractExtension.registered_hooks[hook_name]:
                    result = handler(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    logging.error(f"Error in hook handler for '{hook_name}': {str(e)}")
    def get_available_commands(self) -> List[Dict[str, Any]]:
        """
        Get the list of available commands for this extension.
        Returns:
            List of available command dictionaries
        """
            return []
        available_commands = []
        for command_name, command_function in self.commands.items():
            # Check if the command is enabled in the agent configuration
                self.agent_config["commands"][command_name] = "false"
            if str(self.agent_config["commands"][command_name]).lower() == "true":
                command_args = self._get_command_args(command_function)
                available_commands.append(
                    {
                        "friendly_name": command_name,
                        "name": command_function.__name__,
                        "args": command_args,
                        "enabled": True,
                    }
                )
        return available_commands
    def get_enabled_commands(self) -> List[Dict[str, Any]]:
        """
        Returns:
        """
        return [
            command for command in self.get_available_commands() if command["enabled"]
        ]
        """
        Extract command arguments from a function.
        Args:
            command_function: The function to extract arguments from
        Returns:
            Dictionary of argument names and default values
        params = {}
        sig = signature(command_function)
            if name == "self":
                continue
            if param.default == Parameter.empty:
                params[name] = ""
                params[name] = param.default
        return params
    async def execute_command(
    ) -> str:
        """
        Execute a command with the given arguments.
        Args:
            command_args: Arguments for the command
        Returns:
            Result of the command execution
        """
        if command_args is None:
            command_args = {}
        if command_name not in self.commands:
        command_function = self.commands[command_name]
        valid_args = self._get_command_args(command_function)
        filtered_args = {}
        for arg_name in valid_args:
                filtered_args[arg_name] = command_args[arg_name]
            else:
                filtered_args[arg_name] = valid_args[arg_name]
        try:
            return await command_function(**filtered_args)
            logging.error(f"Error executing command '{command_name}': {str(e)}")
            return f"Error executing command '{command_name}': {str(e)}"
    @classmethod
    def discover_extensions(cls) -> List[Type["AbstractExtension"]]:
        """
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
                try:
                    module = importlib.import_module(f"extensions.{module_name}")
                    # Find the AbstractExtension subclass in the module
                    for name, obj in inspect.getmembers(module):
                            inspect.isclass(obj)
                            and issubclass(obj, AbstractExtension)
                            and obj != AbstractExtension
                        ):
                            extensions.append(obj)
                            logging.debug(
                            )
                            break
                except Exception as e:
        return extensions
