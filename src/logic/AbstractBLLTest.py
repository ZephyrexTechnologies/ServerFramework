import inspect
import uuid
from typing import Any, Dict, List, Optional, Type, TypeVar

import pytest
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from logic.AbstractBLLManager import AbstractBLLManager

# Type variables for the manager class and its models
T = TypeVar('T', bound=AbstractBLLManager)
ModelT = TypeVar('ModelT', bound=BaseModel)


class AbstractBLLTest:
    """
    Abstract base class for testing BLL managers.
    
    Provides common test fixtures and methods for testing standard CRUD operations
    and validations on any BLL manager that inherits from AbstractBLLManager.
    """
    
    # These class variables should be overridden by subclasses
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
        """
        Create a manager instance for testing.
        
        Args:
            db: Database session from pytest fixture
            requester_id: ID of the requesting user from pytest fixture
            
        Returns:
            An instance of the manager class being tested
        """
        if not self.manager_class:
            pytest.skip("manager_class not defined, test cannot run")
            
        # Initialize the manager with the current requester ID and DB session
        return self.manager_class(
            requester_id=requester_id,
            db=db
        )
    
    @pytest.fixture
    def created_entity(self, manager: AbstractBLLManager) -> Any:
        """
        Create a test entity in the database.
        
        Args:
            manager: Manager instance from fixture
            
        Returns:
            The created test entity
        """
        if not self.valid_create_data:
            pytest.skip("valid_create_data not defined, test cannot run")
            
        return manager.create(**self.valid_create_data)
    
    def test_create_valid(self, manager: AbstractBLLManager):
        """Test creating an entity with valid data"""
        if not self.valid_create_data:
            pytest.skip("valid_create_data not defined, test cannot run")
            
        entity = manager.create(**self.valid_create_data)
        assert entity is not None
        assert entity.id is not None
        
        # Check that all provided fields were correctly set
        for key, value in self.valid_create_data.items():
            if hasattr(entity, key):
                assert getattr(entity, key) == value
    
    def test_create_invalid(self, manager: AbstractBLLManager):
        """Test creating an entity with invalid data expects an exception"""
        if not self.invalid_create_data:
            pytest.skip("invalid_create_data not defined, test cannot run")
            
        with pytest.raises((ValueError, HTTPException)):
            manager.create(**self.invalid_create_data)
    
    def test_get(self, manager: AbstractBLLManager, created_entity: Any):
        """Test retrieving an entity by ID"""
        retrieved = manager.get(id=created_entity.id)
        assert retrieved is not None
        assert retrieved.id == created_entity.id
    
    def test_get_nonexistent(self, manager: AbstractBLLManager):
        """Test retrieving a non-existent entity should return None or raise an exception"""
        nonexistent_id = str(uuid.uuid4())
        
        # AbstractBLLManager may either return None or raise HttpException for non-existent entities
        try:
            result = manager.get(id=nonexistent_id)
            assert result is None
        except HTTPException as e:
            assert e.status_code == 404
    
    def test_list(self, manager: AbstractBLLManager, created_entity: Any):
        """Test listing entities"""
        results = manager.list()
        assert isinstance(results, list)
        assert any(x.id == created_entity.id for x in results)
    
    def test_update(self, manager: AbstractBLLManager, created_entity: Any):
        """Test updating an entity"""
        if not self.valid_update_data:
            pytest.skip("valid_update_data not defined, test cannot run")
            
        updated = manager.update(id=created_entity.id, **self.valid_update_data)
        assert updated is not None
        
        # Check that fields were updated correctly
        for key, value in self.valid_update_data.items():
            if hasattr(updated, key):
                assert getattr(updated, key) == value
    
    def test_update_invalid(self, manager: AbstractBLLManager, created_entity: Any):
        """Test updating an entity with invalid data expects an exception"""
        if not self.invalid_update_data:
            pytest.skip("invalid_update_data not defined, test cannot run")
            
        with pytest.raises((ValueError, HTTPException)):
            manager.update(id=created_entity.id, **self.invalid_update_data)
    
    def test_delete(self, manager: AbstractBLLManager, created_entity: Any):
        """Test deleting an entity"""
        manager.delete(id=created_entity.id)
        
        # Entity should no longer exist
        try:
            result = manager.get(id=created_entity.id)
            assert result is None
        except HTTPException as e:
            assert e.status_code == 404
    
    def test_search(self, manager: AbstractBLLManager, created_entity: Any):
        """Test searching for entities"""
        if not self.search_params:
            pytest.skip("search_params not defined, test cannot run")
            
        results = manager.search(**self.search_params)
        assert isinstance(results, list)
    
    @staticmethod
    def get_required_fields(model_class) -> List[str]:
        """
        Helper method to get required fields from a pydantic model class.
        
        Args:
            model_class: A pydantic BaseModel class
            
        Returns:
            List of required field names
        """
        return [
            field_name for field_name, field in model_class.__annotations__.items()
            if not getattr(field, "__origin__", None) == Optional
        ]
    
    @staticmethod
    def generate_field_data(field_name: str, field_type: Any) -> Any:
        """
        Generate test data for a field based on its name and type.
        
        Args:
            field_name: Name of the field
            field_type: Type of the field
            
        Returns:
            Generated test value for the field
        """
        # Generate test values based on common field names and types
        if field_name == 'id':
            return str(uuid.uuid4())
        elif field_name in ('name', 'title'):
            return f'Test {field_name}'
        elif field_name in ('description', 'content'):
            return f'Test {field_name} content'
        elif field_name == 'email':
            return 'test@example.com'
        elif field_type == bool:
            return True
        elif field_type == int:
            return 1
        elif field_type == float:
            return 1.0
        elif field_type == str:
            return f'Test {field_name}'
        elif field_type == list or getattr(field_type, "__origin__", None) == list:
            return []
        elif field_type == dict or getattr(field_type, "__origin__", None) == dict:
            return {}
            
        # Default fallback
        return None