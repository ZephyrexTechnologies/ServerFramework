# Providers
Providers are the method extensions use to connect to and standardize the interface of various services. Each extension comes with an abstract provider class that extends `AbstractProvider`. Providers define the interface and functionality for interacting with external services or implementing specific capabilities.

## Provider Architecture
- **AbstractProvider**: Base class for all providers, providing common functionality
- **AbstractAPIProvider**: Extension of AbstractProvider with API-specific functionality for API-based services

## Provider Properties
Each provider has:
- `friendly_name`: Human-readable name for the provider
- `extension_id`: Optional ID of the extension this provider belongs to
- `unsupported_capabilities`: Set of capabilities the provider claims to not support
- `abilities`: Dictionary of callable functions registered by the provider
- `WORKING_DIRECTORY`: Directory for provider file operations

## API Providers
API providers extend the base provider with API-specific properties:
- `api_key`: Authentication key for the service
- `api_uri`: Base URL for the API
- `WAIT_BETWEEN_REQUESTS`: Time to wait between API requests
- `WAIT_AFTER_FAILURE`: Time to wait after a failed request

## Provider Features
Providers implement various features:
- **Service Discovery**: Determine what services/capabilities are available
- **Ability Registration**: Register callable functions as abilities
- **File Operations**: Safe file path handling with base directory protection
- **Error Handling**: Track failures and decide on retry behavior
- **Extension Integration**: Connect with their parent extension

## Provider Instances
Providers are then connected to user accounts via a `ProviderInstance`. This allows multiple accounts of the same provider to be linked (for example multiple GMail accounts).

## Creating a Provider
When creating a custom provider, extend either `AbstractProvider` or `AbstractAPIProvider`:

```python
from extensions.AbstractProvider import AbstractAPIProvider

class ExampleProvider(AbstractAPIProvider):
    def __init__(
        self, 
        extension_id=None,
        api_key="",
        api_uri="https://api.example.com", 
        **kwargs
    ):
        super().__init__(
            extension_id=extension_id,
            api_key=api_key,
            api_uri=api_uri,
            **kwargs
        )
        self.friendly_name = "Example Provider"
        
    def _configure_provider(self, **kwargs):
        # Provider-specific initialization
        self.timeout = kwargs.get("timeout", 30)
        
    def has_ability(self, ability: str) -> bool:
        # Override to implement custom ability detection
        return ability in ["example_ability", "other_ability"]
```