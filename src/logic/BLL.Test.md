# BLL Testing Documentation

## Overview

This document describes the testing framework for Business Logic Layer (BLL) managers. The BLL testing system provides comprehensive test coverage for all BLL components, ensuring their correct functionality, data integrity, and proper permission handling.

## Test Framework Architecture

### AbstractBLLTest Base Class

The `AbstractBLLTest` class provides a standardized framework for testing BLL managers. It inherits from `AbstractTest` and adds BLL-specific functionality.

Key features:
- Automatic test data generation
- CRUD operation testing
- Permission testing
- Parent dependency handling
- Custom validation testing
- Batch operation testing

### Test Structure

Each BLL manager test class follows this pattern:

```python
class TestManagerName(AbstractBLLTest):
    manager_class = ManagerClass
    create_model_class = ModelClass.Create
    update_model_class = ModelClass.Update
    search_model_class = ModelClass.Search
    
    string_field_to_update = "field_name"
    required_fields = ["id", "field1", "field2", ...]
    parent_dependencies = [(ParentManager, "field_name"), ...]
    
    # Custom test methods...
```

## Test Categories

### 1. CRUD Tests (`test_CRUD_logic`)

The base test that validates all basic operations:
- Create entity with user A
- Read entity with user A
- Attempt read with user B (expect failure)
- Count entities for both users
- Confirm existence/non-existence
- Update entity with user A
- Attempt update with user B (expect failure)
- Create second entity
- List all entities
- Delete entities with proper permissions

### 2. Validation Tests

Tests for custom validation logic:
- Required field validation
- Data format validation
- Business rule validation
- Parent relationship validation

### 3. Permission Tests

Tests for access control:
- User-specific access
- Team-based access
- Role-based permissions
- System entity restrictions

### 4. Batch Operation Tests

Tests for bulk operations:
- Batch create
- Batch update
- Batch delete

### 5. Search Tests

Tests for search functionality:
- Basic search
- Filter operations
- Custom search transformers
- Pagination

## Module-Specific Tests

### Auth Module Tests

- **UserManager**: Tests user creation with metadata, password handling
- **UserCredentialManager**: Tests password changes, credential creation
- **TeamManager**: Tests team creation with metadata, parent relationships
- **RoleManager**: Tests role hierarchy, system roles
- **UserTeamManager**: Tests user-team relationships
- **PermissionManager**: Tests permission validation
- **InvitationManager**: Tests invitation creation, code generation
- **UserSessionManager**: Tests session management, revocation

### Providers Module Tests

- **ProviderManager**: Tests provider validation, runtime provider listing
- **ProviderInstanceManager**: Tests instance creation, validation
- **ProviderInstanceUsageManager**: Tests usage tracking, validation
- **ProviderInstanceSettingManager**: Tests settings management
- **RotationManager**: Tests rotation creation, validation
- **RotationProviderInstanceManager**: Tests rotation-instance relationships

### Extensions Module Tests

- **ExtensionManager**: Tests extension creation, runtime extension listing
- **AbilityManager**: Tests ability creation, extension relationships

## Test Execution

### Running Tests

Run all BLL tests:
```bash
pytest -v BLL_*_test.py
```

Run specific module tests:
```bash
pytest -v BLL_Auth_test.py
pytest -v BLL_Providers_test.py
pytest -v BLL_Extensions_test.py
```

Run specific test class:
```bash
pytest -v BLL_Auth_test.py::TestUserManager
```

### Test Configuration

Tests can be configured through:
- Test class attributes
- Environment variables
- Fixture parameters

## Common Test Patterns

### Parent Dependency Handling

Tests that require parent entities:

```python
class TestChildManager(AbstractBLLTest):
    parent_dependencies = [(ParentManager, "parent_id")]
    
    def create_parent_entities(self, manager_class, field_name):
        """Create parent entities for testing."""
        # Custom parent creation logic if needed
        return super().create_parent_entities(manager_class, field_name)
```

### Custom Validation Testing

```python
def test_custom_validation(self, db, requester_id):
    """Test custom validation logic."""
    manager = self.get_manager(requester_id)
    
    with pytest.raises(HTTPException) as exc_info:
        manager.create(invalid_field="value")
    
    assert exc_info.value.status_code == 400
    assert "validation error" in exc_info.value.detail
```

### Permission Testing

```python
def test_permissions(self, db, requester_id):
    """Test permission handling."""
    manager_a = self.get_manager(requester_id)
    manager_b = self.get_manager(str(uuid.uuid4()))
    
    # Create with user A
    entity = manager_a.create(**test_data)
    
    # Attempt access with user B
    with pytest.raises(HTTPException):
        manager_b.get(id=entity.id)
```

## Best Practices

1. **Test Independence**: Each test should be independent and not rely on other tests
2. **Cleanup**: Always clean up created entities to prevent test pollution
3. **Meaningful Assertions**: Include descriptive error messages in assertions
4. **Edge Cases**: Test both normal and edge cases
5. **Error Testing**: Verify proper error handling and status codes

## Extending the Framework

To add tests for new BLL managers:

1. Create a test class inheriting from `AbstractBLLTest`
2. Configure class attributes for the manager
3. Implement custom test methods as needed
4. Handle parent dependencies if required
5. Add validation tests for business logic

## Troubleshooting

Common issues and solutions:

1. **Permission Errors**: Ensure proper requester_id is used
2. **Missing Parents**: Check parent_dependencies configuration
3. **Validation Failures**: Verify test data matches model requirements
4. **Database Conflicts**: Clean up entities after tests

## Contributing

When adding new tests:
1. Follow existing patterns
2. Document special cases
3. Include meaningful test names
4. Add comments for complex logic
5. Update this documentation as needed