# Testing Framework

This document provides an overview of the testing philosophy, structure, and conventions used within the project. The framework aims for completeness, consistency, efficiency, maintainability, and comprehensive coverage across all layers of the application.

## Core Philosophy

- **Layered Testing**: Each architectural layer (Database, BLL, Endpoints, Services, Extensions, Providers) has its own dedicated abstract test class and testing patterns.
- **Abstraction**: Common testing utilities and patterns are centralized in base abstract classes (`AbstractTest`, `AbstractDBTest`, `AbstractBLLTest`, etc.) to reduce boilerplate code.
- **Fixture-Based Setup**: Pytest fixtures (`conftest.py`) manage the setup and teardown of resources like database connections, test clients, and common test entities (users, teams).
- **Configuration Driven**: Tests are configured using class attributes within the specific test class (e.g., defining the model/manager to test, required fields, parent entities).
- **Comprehensive Coverage**: Tests cover standard CRUD operations, batch processing, error handling, validation, permissions, and layer-specific features (e.g., endpoint routing, BLL search, service lifecycle).

## Base Test Class: `AbstractTest`

Located in `src/AbstractTest.py`, this class serves as the foundation for all other abstract test classes. It provides:

- **Test Categories**: Enum-based categorization (unit, integration, functional, etc.) for organization and selective execution.
- **Test Configuration**: Configurable timeout, parallel execution, CI environment handling.
- **`SkippedTest` Model**: A standard Pydantic model for defining tests to skip with a reason and optional JIRA ticket reference.
- **`skip_tests` Attribute**: A class attribute (list of `SkippedTest` objects) to be overridden by subclasses to specify tests that should not run for that particular component.
- **`reason_to_skip_test` Method**: A helper method used within test methods to check if the current test should be skipped based on the `skip_tests` list.
- **Lifecycle Hooks**: Setup and teardown methods for test classes and individual test methods.
- **Common Assertions**: Methods for validating objects and audit fields consistently.

All specific abstract test classes (`AbstractEPTest`, `AbstractBLLTest`, etc.) inherit from `AbstractTest`.

## Test Utilities (`helptest.py`)

The `helptest.py` file provides common test utilities for generating test data and validating entities:

- **`TestDataGenerator`**: Utilities for generating test data based on field types and names:
  - Type-specific generation (strings, integers, booleans, dates, UUIDs, etc.)
  - Smart context-aware generation (emails, names, URLs, etc.)
  - Pydantic model-based test data generation
  - Support for nested structures (lists, dictionaries, optionals)

- **`TestValidator`**: Utilities for validating entities and test data:
  - Required field validation
  - Field value matching
  - Audit field validation

- **Basic Test Data Generation**: Simple functions for emails, passwords, etc.

## Test Setup and Fixtures (`conftest.py`)

`conftest.py` is crucial for setting up the test environment and providing shared resources:

- **Environment Configuration**: Sets environment variables for testing (e.g., SQLite database, `SEED_DATA=true`).
- **Database Setup**: Manages the creation, seeding, and cleanup of the test database (`db` fixture). Ensures migrations are run.
- **Test Client**: Provides a FastAPI `TestClient` instance (`server` fixture) for making API requests.
- **Core Entities**: Creates standard test entities like users (`admin_a`, `user_b`), JWT tokens (`admin_a_jwt`, `jwt_b`), and teams (`team_a`, `team_b`) available session-wide.
- **Common IDs**: Provides function-scoped fixtures for standard IDs used in testing (`requester_id`, `test_user_id`, `test_team_id`).

## Layer-Specific Testing

Each architectural layer has its own abstract test class and accompanying documentation detailing its specific testing patterns:

- **Database Layer**: See `DB.Test.md` and `AbstractDBTest.py`
- **Business Logic Layer**: See `BLL.Test.md` and `AbstractBLLTest.py`
- **Endpoint Layer**: See `EP.Test.md` and `AbstractEPTest.py`
- **Service Layer**: See `SVC.Test.md` and `AbstractSVCTest.py`
- **Extension Layer**: See `EXT.Test.md` and `AbstractEXTTest.py`
- **Provider Layer**: See `PRV.Test.md` and `AbstractPRVTest.py`

## Running Tests

Tests are run using `pytest` from the project root directory. Pytest automatically discovers test files (following the `*_test.py` convention) and fixtures. 