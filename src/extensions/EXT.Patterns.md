# Extensions
Extensions are the way to extend the functionality of the server. They have the ability to define new database tables, logic managers and endpoint routers, as well as mutate and extend the ones provided with the base system. 
## Dependencies
Each extension defines a `name`, and a list of dependencies, each with a `name: str` and `optional: bool` property. Non-optional dependencies will prevent the extension from being loaded. Optional dependencies are extensions such as `labels`, which is a very common optional dependency that when present allows labels to be applied to the new entities provided with the extension. 
Each extension can extend existing tables by adding new fields or references, and can override / extend the functionality of existing controllers. Functionality in extensions can also be triggered by hook calls from the core system.
## Providers
## Creating an Extension
A typical extension will include one or more of the following files:
- `BLL_Name.py` defines business logic managers, implementing `AbstractBLLManager`.
- `BLL_Domain_Name.py` defines injection logic for system domain managers.
- `PRV_Name.py` defines the abstract provider for the extension, implementing `AbstractPRV`.
in addition to the required:
- `EXT_Name.py` defines the extension, implementing `AbstractEXT`.
