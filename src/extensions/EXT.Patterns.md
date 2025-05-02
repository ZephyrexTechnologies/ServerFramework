# Extensions
Extensions are the way to extend the functionality of the server. They have the ability to define new database tables, logic managers and endpoint routers, as well as mutate and extend the ones provided with the base system. 

## Extension Structure
Each extension inherits from `AbstractExtension` and must define the following properties:
- `name`: A unique identifier for the extension
- `version`: The extension version (semantic versioning recommended)
- `description`: A description of what the extension does
- `friendly_name`: A human-readable name for the extension

## Dependencies
Extensions can declare different types of dependencies:
- `ext_dependencies`: Other extensions this extension depends on
- `pip_dependencies`: Python packages required by this extension
- `apt_dependencies`: System packages required by this extension

Each dependency type follows the `Dependency` model structure, specifying:
- `name`: The name of the dependency
- `friendly_name`: A human-readable name
- `optional`: Whether this dependency is optional (defaults to False)
- `reason`: The reason this extension is required or what it adds if optional
- `semver`: Optional semver version constraint (for ext_dependencies)

Non-optional dependencies will prevent the extension from being loaded if they are not available. Optional dependencies are extensions such as `labels`, which is a very common optional dependency that when present allows labels to be applied to the new entities provided with the extension.

## Hooks
Extensions can register hooks to modify or extend behavior in the core system. Hooks are registered using decorators:

- `@AbstractExtension.bll_hook(domain, entity, function, time)`: Business logic layer hooks
- `@AbstractExtension.ep_hook(domain, entity, function, time)`: Endpoint layer hooks
- `@AbstractExtension.db_hook(domain, entity, function, time)`: Database layer hooks

Each hook specifies when it should be triggered (before/after) a specific operation in a specific layer.

## Abilities
Extensions can also define abilities, which are callable functions that can be executed by name. Abilities are registered using the `@AbstractExtension.ability(name, enabled)` decorator.

## Providers
Each extension can define provider classes that implement specific service integrations. These providers inherit from `AbstractProvider` and are instantiated by the extension.

## Extension Components
A typical extension will include one or more of the following files:
- `BLL_Name.py` defines business logic managers, implementing `AbstractBLLManager`.
- `BLL_Domain_Name.py` defines injection logic for system domain managers.
- `PRV_Name.py` defines the abstract provider for the extension, implementing `AbstractProvider`.
- `DB_Name.py` defines database models/tables for the extension.
- `EP_Name.py` defines endpoint routers for the extension.

In addition to the required:
- `EXT_Name.py` defines the extension, implementing `AbstractExtension`.

## Extension Loading
Extensions are discovered and loaded at system startup. The loading order is determined by dependency resolution, ensuring that dependencies are loaded before the extensions that depend on them.
