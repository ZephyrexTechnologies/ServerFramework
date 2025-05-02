# Core Abstractions

This document provides a comprehensive overview of the core abstractions used throughout the framework:

1. [Business Logic Layer Manager](#business-logic-layer-manager-abstractbllmanager)
2. [Business Logic Layer Testing](#business-logic-layer-testing-abstractblltest)
3. [Service Layer](#service-layer-abstractservice)
4. [Service Layer Testing](#service-layer-testing-abstractsvctest)

## Business Logic Layer Manager (`AbstractBLLManager`)

The Business Logic Layer (BLL) in the framework follows a standardized pattern to ensure consistency across different domain entities. Each entity within the system has a corresponding manager class that inherits from `AbstractBLLManager`.

### Core Structure

`AbstractBLLManager` provides a consistent interface for managing entities with CRUD operations, search capabilities, and a hook system for extending functionality.

```python
class AbstractBLLManager:
    Model = TemplateModel  # Reference to the main Pydantic model for this entity
    ReferenceModel = TemplateReferenceModel  # Reference model for relationships
    NetworkModel = TemplateNetworkModel  # Network models for API (POST/PUT/SEARCH/Response)
    DBClass = User  # Default DB class, should be overridden by subclasses

    # Class-level hooks property
    hooks = HooksDescriptor()

    def __init__(
        self,
        requester_id: str,
        target_user_id: Optional[str] = None,
        target_team_id: Optional[str] = None,
        db: Optional[Session] = None,
    ):
        # Initialize manager with context
        pass

    def create(self, **kwargs) -> Any:
        # Create a new entity
        pass

    def get(self, include: Optional[List[str]] = None, fields: Optional[List[str]] = None, **kwargs) -> Any:
        # Get an entity by ID or other fields
        pass

    def list(self, include: Optional[List[str]] = None, fields: Optional[List[str]] = None, 
             sort_by: Optional[str] = None, sort_order: Optional[str] = "asc", 
             filters: Optional[List[Any]] = None, limit: Optional[int] = None, 
             offset: Optional[int] = None, **kwargs) -> List[Any]:
        # List entities with optional filtering and pagination
        pass

    def search(self, include: Optional[List[str]] = None, fields: Optional[List[str]] = None, 
               sort_by: Optional[str] = None, sort_order: Optional[str] = "asc", 
               filters: Optional[List[Any]] = None, limit: Optional[int] = None, 
               offset: Optional[int] = None, **search_params) -> List[Any]:
        # Search entities with complex criteria
        pass

    def update(self, id: str, **kwargs):
        # Update an existing entity
        pass

    def batch_update(self, items: List[Dict[str, Any]]) -> List[Any]:
        # Update multiple entities at once
        pass

    def delete(self, id: str):
        # Delete an entity
        pass

    def batch_delete(self, ids: List[str]):
        # Delete multiple entities at once
        pass

    # Additional helper methods
    def build_search_filters(self, search_params: Dict[str, Any]) -> List:
        # Build database filters from search parameters
        pass

    def _register_search_transformers(self):
        # Register custom search transformers
        pass

    def register_search_transformer(self, field_name: str, transformer: Callable):
        # Register a specific search transformer
        pass

    def createValidation(self, entity):
        # Custom validation before creating an entity
        # Should be overridden by subclasses
        pass
```

### Model Structure

Each BLL manager works with a set of related Pydantic models that define the entity's structure and validation rules:

1. **Main Model**: Defines the entity's fields and validation rules
2. **ReferenceModel**: Used for relationships between entities
3. **NetworkModel**: Used for API interactions

```python
class EntityModel(BaseMixinModel, NameMixinModel):
    description: str = Field(..., description="Entity description")
    
    class ReferenceID:
        entity_id: str = Field(..., description="Foreign key to Entity")
        
        class Optional:
            entity_id: Optional[str] = None
            
        class Search:
            entity_id: Optional[StringSearchModel] = None
    
    class Create(BaseModel, NameMixinModel):
        description: Optional[str] = Field(None, description="Entity description")
    
    class Update(BaseModel, NameMixinModel.Optional):
        description: Optional[str] = Field(None, description="Entity description")
    
    class Search(BaseMixinModel.Search, NameMixinModel.Search):
        description: Optional[StringSearchModel] = None


class EntityReferenceModel(EntityModel.ReferenceID):
    entity: Optional[EntityModel] = None
    
    class Optional(EntityModel.ReferenceID.Optional):
        entity: Optional[EntityModel] = None


class EntityNetworkModel:
    class POST(BaseModel):
        entity: EntityModel.Create
    
    class PUT(BaseModel):
        entity: EntityModel.Update
    
    class SEARCH(BaseModel):
        entity: EntityModel.Search
    
    class ResponseSingle(BaseModel):
        entity: EntityModel
    
    class ResponsePlural(BaseModel):
        entities: List[EntityModel]
```

### Hook System

The BLL Manager includes a hook system that allows extending functionality at specific points in the entity lifecycle:

```python
# Register hooks
hooks = get_hooks_for_manager(EntityManager)

# Create hooks
hooks["create"]["before"].append(create_before_hook)
hooks["create"]["after"].append(create_after_hook)

# Update hooks
hooks["update"]["before"].append(update_before_hook)
hooks["update"]["after"].append(update_after_hook)

# Delete hooks
hooks["delete"]["before"].append(delete_before_hook)
hooks["delete"]["after"].append(delete_after_hook)

# Hook function examples
def create_before_hook(manager, create_args):
    # Modify create args or perform pre-creation logic
    pass

def create_after_hook(manager, entity, create_args):
    # Perform post-creation logic
    pass

def update_before_hook(manager, id, update_args):
    # Modify update args or perform pre-update logic
    pass

def update_after_hook(manager, updated_entity, entity_before, update_args):
    # Perform post-update logic
    pass

def delete_before_hook(manager, id, entity_before):
    # Perform pre-deletion logic
    pass

def delete_after_hook(manager, id, entity_before):
    # Perform post-deletion logic
    pass
```

### Implementation Pattern

```python
# Previous manager (if there is one) would go here.

class EntityModel(BaseMixinModel, NameMixinModel):
    # Entity fields and validation rules
    description: str = Field(..., description="Entity description")
    
    class ReferenceID:
        # Reference ID definitions
        pass
    
    class Create(BaseModel):
        # Create DTO
        pass
    
    class Update(BaseModel):
        # Update DTO
        pass
    
    class Search(BaseMixinModel.Search):
        # Search criteria
        pass

class EntityReferenceModel(EntityModel.ReferenceID):
    # Reference model definitions
    pass

class EntityNetworkModel:
    # Network models for API interactions
    pass

class EntityManager(AbstractBLLManager):
    Model = EntityModel
    ReferenceModel = EntityReferenceModel
    NetworkModel = EntityNetworkModel
    DBClass = Entity  # Database model
    
    def __init__(
        self,
        requester_id: str,
        target_user_id: Optional[str] = None,
        target_team_id: Optional[str] = None,
        db: Optional[Session] = None,
    ):
        super().__init__(
            requester_id=requester_id,
            target_user_id=target_user_id,
            target_team_id=target_team_id,
            db=db,
        )
        # Manager-specific initialization
    
    def _register_search_transformers(self):
        # Register custom search transformers
        self.register_search_transformer("field_name", self._transform_field_search)
    
    def _transform_field_search(self, value):
        # Custom search transformation logic
        pass
    
    def createValidation(self, entity):
        # Custom validation logic
        pass
    
    def create(self, **kwargs):
        # Custom create logic if needed, otherwise use super().create
        pass
    
    def update(self, id: str, **kwargs):
        # Custom update logic if needed, otherwise use super().update
        pass
    
    # Additional custom methods
    def custom_action(self, entity_id: str) -> Any:
        # Custom business logic
        pass
```

## Business Logic Layer Testing (`AbstractBLLTest`)

`AbstractBLLTest` provides a structured framework for testing BLL managers. It defines a consistent approach to test CRUD operations, search functionality, batch processing, and hooks.

### Core Structure

```python
class AbstractBLLTest(AbstractTest):
    """
    Abstract base class for testing BLL managers.

    Provides a structured framework for testing business logic layer managers
    that follow the patterns defined in AbstractBLLManager.
    """

    # These class attributes should be overridden by subclasses
    manager_class: Type[AbstractBLLManager] = None

    # Test data for create operations - must be overridden by subclasses
    valid_create_data: Dict[str, Any] = {}
    invalid_create_data: Dict[str, Any] = {}

    # Test data for update operations - must be overridden by subclasses
    valid_update_data: Dict[str, Any] = {}
    invalid_update_data: Dict[str, Any] = {}

    # Test data for search operations - optional
    search_params: Dict[str, Any] = {}

    @pytest.fixture
    def manager(self, db: Session, requester_id: str) -> AbstractBLLManager:
        # Create and return a manager instance
        pass

    @pytest.fixture
    def created_entity(self, manager: AbstractBLLManager) -> Any:
        # Create a test entity using valid_create_data
        pass

    # Test methods
    def test_create_valid(self, manager: AbstractBLLManager):
        # Test creating with valid data
        pass

    def test_create_invalid(self, manager: AbstractBLLManager):
        # Test creating with invalid data
        pass

    def test_get(self, manager: AbstractBLLManager, created_entity: Any):
        # Test getting an entity
        pass

    def test_get_nonexistent(self, manager: AbstractBLLManager):
        # Test getting a non-existent entity
        pass

    def test_list(self, manager: AbstractBLLManager, created_entity: Any):
        # Test listing entities
        pass

    def test_list_pagination(self, manager: AbstractBLLManager):
        # Test pagination in list operation
        pass

    def test_update(self, manager: AbstractBLLManager, created_entity: Any):
        # Test updating an entity with valid data
        pass

    def test_update_invalid(self, manager: AbstractBLLManager, created_entity: Any):
        # Test updating with invalid data
        pass

    def test_update_nonexistent(self, manager: AbstractBLLManager):
        # Test updating a non-existent entity
        pass

    def test_delete(self, manager: AbstractBLLManager, created_entity: Any):
        # Test deleting an entity
        pass

    def test_delete_nonexistent(self, manager: AbstractBLLManager):
        # Test deleting a non-existent entity
        pass

    def test_search(self, manager: AbstractBLLManager, created_entity: Any):
        # Test searching for entities
        pass

    def test_batch_operations(self, manager: AbstractBLLManager):
        # Test batch create, update, and delete operations
        pass

    def test_hooks(self, manager: AbstractBLLManager):
        # Test hook functionality
        pass
```

### Implementation Pattern

When creating a test class for a specific BLL manager, configure these attributes:

```python
from logic.BLL_Providers import ProviderManager 
from logic.AbstractBLLTest import AbstractBLLTest

class ProviderBLLTest(AbstractBLLTest):
    # The BLL Manager class to test
    manager_class = ProviderManager

    # Valid data for creating an entity via manager.create()
    valid_create_data = {
        "name": "Test Provider",
        "description": "Provider for testing BLL"
    }
    
    # Invalid data expected to raise an exception during manager.create()
    invalid_create_data = {
        "name": None # Assuming name is required
    }

    # Valid data for updating an entity via manager.update()
    valid_update_data = {
        "description": "Updated provider description"
    }
    
    # Invalid data expected to raise an exception during manager.update()
    invalid_update_data = {
        # Example: Data violating a unique constraint or validation rule
    }

    # Optional: Parameters for testing manager.search()
    search_params = {
        "name": "Test Provider"
    }

    # Optionally skip tests (inherited from AbstractTest)
    skip_tests = [
        # SkippedTest(name="test_hooks", reason="Hooks not implemented for this manager")
    ]
    
    # Custom test methods for manager-specific functionality
    def test_provider_specific_action(self, manager):
        test_name = "test_provider_specific_action"
        if self.reason_to_skip_test(test_name):
            return

        # Create an provider using the manager fixture
        provider = manager.create(**self.valid_create_data)

        # Call a method specific to ProviderManager
        result = manager.perform_provider_action(provider.id)

        # Assert expected outcome
        assert result is True
```

### Using Fixtures

For managers that require more complex setup or dependencies, use pytest fixtures:

```python
class UserCredentialManagerTest(AbstractBLLTest):
    manager_class = UserCredentialManager

    @pytest.fixture
    def user_id(self, manager):
        user_manager = UserManager(
            requester_id=manager.requester.id,
            db=manager.db
        )
        user = user_manager.create(
            email="cred_test@example.com",
            username="creduser",
            password="SecurePassword123!"
        )
        return user.id

    @pytest.fixture
    def valid_create_data(self, user_id):
        return {
            "user_id": user_id,
            "password": "SecurePassword123!"
        }

    @pytest.fixture
    def invalid_create_data(self):
        return {
            "user_id": str(uuid4()),  # Non-existent user
            "password": "short"
        }

    @pytest.fixture
    def valid_update_data(self):
        return {
            "password": "UpdatedSecurePassword123!"
        }

    @pytest.fixture
    def invalid_update_data(self):
        return {
            "password": "short"
        }

    @pytest.fixture
    def created_entity(self, manager, valid_create_data):
        return manager.create(**valid_create_data)
```

## Service Layer (`AbstractService`)

Services in framework represent long-running background processes or tasks that operate independently of direct API requests. They often perform periodic actions, maintenance, or interact with external systems asynchronously.

### Core Structure

`AbstractService` provides a standardized structure and lifecycle management for services:

```python
class AbstractService(ABC):
    """
    Abstract base class for all service components.

    Services are background tasks that run periodically, typically used for
    scheduled operations, monitoring, or other ongoing tasks that need to
    execute in the background.
    """

    def __init__(
        self,
        requester_id: str,
        db: Optional[Session] = None,
        interval_seconds: int = 60,
        max_failures: int = 3,
        retry_delay_seconds: int = 5,
        **kwargs,
    ):
        """Initialize the service."""
        pass

    def _configure_service(self, **kwargs) -> None:
        """
        Configure service-specific settings.
        Override this method in subclasses.
        """
        pass

    @property
    def db(self) -> Session:
        """Property that returns an active database session."""
        pass

    def start(self) -> None:
        """Start the service running in the background."""
        pass

    def stop(self) -> None:
        """Stop the service from running."""
        pass

    def pause(self) -> None:
        """Pause the service temporarily."""
        pass

    def resume(self) -> None:
        """Resume a paused service."""
        pass

    def _handle_failure(self, error: Exception) -> bool:
        """
        Handle a failure and determine if retrying is appropriate.
        """
        pass

    def _reset_failures(self) -> None:
        """Reset the failure counter after a successful execution."""
        pass

    async def run_service_loop(self) -> None:
        """
        Main service loop that runs update() at the configured interval.
        """
        pass

    @abstractmethod
    async def update(self) -> None:
        """
        Main method to perform the service's work.
        This method should be implemented by all service subclasses.
        """
        pass

    def cleanup(self) -> None:
        """
        Perform necessary cleanup when the service is being shut down.
        """
        pass
```

### Key Components

- **`__init__(...)`**: Initializes the service, setting up essential attributes like the run interval, failure thresholds, database session handling.
- **`requester_id`**: Services operate under a specific user context, typically the `SYSTEM_ID` or a dedicated service user ID.
- **`db` Property**: Provides access to a SQLAlchemy database session.
- **`interval_seconds`**: Defines how often the service's main logic (`update` method) should run.
- **`max_failures` / `retry_delay_seconds`**: Control the service's resilience.
- **`running` / `paused` Flags**: Control the service's execution state.
- **`_configure_service()`**: For subclasses to perform one-time setup during initialization.
- **`update()`**: An abstract async method containing the core logic.
- **`run_service_loop()`**: The main async loop that manages the service's execution.
- **Lifecycle Methods**: `start()`, `stop()`, `pause()`, `resume()`, `cleanup()` for controlling the service's state.
- **Error Handling**: Catches exceptions, logs them, and implements retry/max failure logic.

### Implementation Pattern

```python
import asyncio
import logging
from sqlalchemy.orm import Session

from services.AbstractService import AbstractService

logger = logging.getLogger(__name__)

class ExampleService(AbstractService):
    """An example background service."""

    def _configure_service(self) -> None:
        """Perform one-time setup for the service."""
        logger.info(f"Configuring ExampleService")
        # Example: Load configuration, initialize clients, etc.
        self.some_client = ...

    async def update(self) -> None:
        """Core logic performed by the service periodically."""
        logger.debug(f"ExampleService executing update...")
        
        # Use self.db for database operations
        # session = self.db
        # items = session.query(SomeModel).filter(...).all()

        # Perform actions...
        # await self.some_client.process(items)
        
        # Simulate work
        await asyncio.sleep(0.5)

        logger.debug(f"ExampleService update finished.")

    def cleanup(self) -> None:
        """Perform cleanup when the service stops."""
        super().cleanup() # Ensure parent cleanup runs
        logger.info(f"Cleaning up ExampleService")
        # Example: Close connections, release resources
        # if self.some_client:
        #     self.some_client.close()
```

### Service Registry

Services can be registered in a central `ServiceRegistry` for management:

```python
# Register a service
service = ExampleService(requester_id="system")
ServiceRegistry.register("example_service", service)

# Start all registered services
ServiceRegistry.start_all()

# Get a specific service
example_service = ServiceRegistry.get("example_service")

# Stop all services
ServiceRegistry.stop_all()

# Clean up all services
ServiceRegistry.cleanup_all()
```

## Service Layer Testing (`AbstractSVCTest`)

`AbstractSVCTest` provides a framework for testing services that implement the `AbstractService` interface, with tests for lifecycle management, execution, error handling, and other service-specific functionality.

### Core Structure

```python
class AbstractSVCTest(AbstractTest):
    """
    Abstract base class for testing service components.
    """

    # Class to be tested
    service_class: Type[T] = None

    # Default service initialization parameters
    service_init_params: Dict[str, Any] = {
        "interval_seconds": 1,
        "max_failures": 3,
        "retry_delay_seconds": 1,
    }

    # Mock initialization parameters
    mock_init_params: Dict[str, Any] = {}

    @pytest.fixture
    def service(self, db: Session, requester_id: str) -> AbstractService:
        """Create a service instance for testing."""
        pass

    @pytest.fixture
    def mocked_service(self, db: Session, requester_id: str) -> AbstractService:
        """Create a service instance with mocked dependencies."""
        pass

    def _get_mocks(self) -> Dict[str, MagicMock]:
        """Get mocks for service dependencies. Override this method for specific mocks."""
        return {}

    async def test_service_lifecycle(self, mocked_service):
        """Test the service lifecycle methods (start, stop, pause, resume)."""
        pass

    async def test_run_service_loop(self, mocked_service):
        """Test the service loop execution."""
        pass

    async def _run_service_loop_for_time(self, service, seconds):
        """Run the service loop for a specified number of seconds."""
        pass

    async def test_error_handling(self, mocked_service):
        """Test service error handling and retry logic."""
        pass

    async def test_max_failures(self, mocked_service):
        """Test that service stops after reaching max failures."""
        pass

    async def test_pause_resume(self, mocked_service):
        """Test that paused service doesn't call update."""
        pass

    async def test_cleanup(self, mocked_service):
        """Test service cleanup."""
        pass

    def test_db_property(self, service, db):
        """Test that db property returns an active session."""
        pass

    def test_reset_failures(self, service):
        """Test that _reset_failures resets the failure counter."""
        pass

    def test_handle_failure(self, service):
        """Test that _handle_failure increments failure count."""
        pass

    def test_configure_service(self):
        """Test that _configure_service is called during initialization."""
        pass
```

### Implementation Pattern

When creating a test class for a specific service:

```python
from services.SVC_Example import ExampleService 
from logic.AbstractSVCTest import AbstractSVCTest
from unittest.mock import MagicMock

class ExampleServiceTest(AbstractSVCTest):
    # The Service class to test
    service_class = ExampleService

    # Default parameters for initializing the service in tests
    service_init_params = {
        "interval_seconds": 0.1, # Use short interval for testing
        "max_failures": 3,
        "retry_delay_seconds": 0.1,
        # Add any other required init params for ExampleService
    }

    # Optional: Parameters only for the mocked_service fixture
    mock_init_params = {
        "mock_dependency": MagicMock()
    }

    # Optional: Override to provide specific mocks for mocked_service
    def _get_mocks(self) -> Dict[str, MagicMock]:
        return {
            "external_api_call": MagicMock(return_value=True)
        }
        
    # Custom test for service-specific logic
    async def test_example_update_logic(self, service):
        test_name = "test_example_update_logic"
        if self.reason_to_skip_test(test_name):
            return

        # Setup initial state in the database if needed
        # ...

        # Call the actual update method
        await service.update()

        # Assert that the expected changes occurred
        # e.g., check database state, check mock calls
        # ...
```

### Testing Actual Service Logic

To test the actual logic within your service's `update` method:

1. Add custom test methods to your specific service test class.
2. Use the standard `service` fixture (not the `mocked_service`).
3. Call `await service.update()` directly within your test method.
4. Assert the expected side effects (database changes, interactions with external systems via mocks).

The standard tests using `mocked_service` focus on the `AbstractService` framework itself, while custom tests using the `service` fixture focus on the service's specific business logic.

## Best Practices

### BLL Managers

1. **Keep Managers Focused**: Each manager should focus on a specific entity or closely related group of entities.
2. **Validate Inputs**: Use `createValidation` and similar methods to validate inputs before operations.
3. **Use Hooks for Cross-Cutting Concerns**: Hooks provide a clean way to add behavior without modifying core logic.
4. **Implement Search Transformers**: Custom search transformers make the search API powerful and flexible.
5. **Follow Naming Conventions**: Maintain consistent naming across models, managers, and methods.
6. **Use Transactions**: For operations that involve multiple database changes, use transactions.
7. **Handle Errors Gracefully**: Provide meaningful error messages when operations fail.

### Services

1. **Idempotency**: Design the `update` logic to be idempotent where possible.
2. **Error Handling**: Catch specific exceptions within `update` if custom handling is needed.
3. **Resource Management**: Use the `db` property for database access and ensure proper cleanup.
4. **Configuration**: Load service-specific configuration during `_configure_service`.
5. **Logging**: Implement clear and informative logging to aid debugging and monitoring.
6. **Concurrency**: Be mindful of potential race conditions with data modified by other services or API requests.
7. **Interval**: Choose a reasonable `interval_seconds` based on the task's requirements and expected load.

### Testing

1. **Use Fixtures for Complex Setup**: For entities with dependencies, use fixtures to set up the test environment.
2. **Mock External Dependencies**: When testing services, mock external dependencies to isolate the service logic.
3. **Test Edge Cases**: Include tests for error conditions, empty results, and boundary values.
4. **Use Skip Mechanism**: Use the `skip_tests` mechanism for tests that don't apply to specific managers or services.
5. **Keep Tests Independent**: Each test should run independently and not rely on the state from previous tests.
6. **Test Custom Methods**: Add tests for manager-specific or service-specific methods.
7. **Verify Side Effects**: When testing hooks or service updates, verify that the expected side effects occurred. 