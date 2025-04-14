import pytest
from extensions.prompts.DB_Prompts import Prompt
from database.Base import Operation
from AbstractDBTest import AbstractDBTest

class TestPrompts:
    """Test suite for Prompt models using AbstractDBTest."""
    
    def test_create_prompt(self, db_session, test_user):
        """Test creating a prompt."""
        prompt = AbstractDBTest.create_entity(
            db_session=db_session,
            model_class=Prompt,
            requester_id=test_user.id,
            name="Test Create Prompt",
            description="Test prompt description",
            content="This is a test prompt.",
            favourite=False,
            user_id=test_user.id  # Explicitly set user_id in kwargs
        )
        
        assert prompt is not None
        assert prompt.name == "Test Create Prompt"
        assert prompt.user_id == test_user.id
        
        # Verify it exists in the database
        AbstractDBTest.assert_entity_exists(
            db_session=db_session,
            model_class=Prompt, 
            id=prompt.id
        )
    
    def test_get_prompt(self, db_session, test_user, test_prompt):
        """Test getting a prompt."""
        prompt = AbstractDBTest.get_entity(
            db_session=db_session,
            model_class=Prompt,
            requester_id=test_user.id,
            id=test_prompt.id
        )
        
        assert prompt is not None
        assert prompt.id == test_prompt.id
        assert prompt.name == test_prompt.name
    
    def test_update_prompt(self, db_session, test_user, test_prompt):
        """Test updating a prompt."""
        updated_prompt = AbstractDBTest.update_entity(
            db_session=db_session,
            model_class=Prompt,
            requester_id=test_user.id,
            entity_id=test_prompt.id,
            name="Updated Prompt Name",
            description="Updated description"
        )
        
        assert updated_prompt is not None
        assert updated_prompt.id == test_prompt.id
        assert updated_prompt.name == "Updated Prompt Name"
        assert updated_prompt.description == "Updated description"
        
        # Verify update in database
        AbstractDBTest.assert_entity_property(
            db_session=db_session,
            model_class=Prompt,
            property_name="name",
            expected_value="Updated Prompt Name",
            id=test_prompt.id
        )
    
    def test_delete_prompt(self, db_session, test_user):
        """Test soft deleting a prompt."""
        # Create a fresh prompt specifically for this test
        prompt = AbstractDBTest.create_entity(
            db_session=db_session,
            model_class=Prompt,
            requester_id=test_user.id,
            name="Delete Test Prompt",
            description="Prompt to be deleted",
            content="Delete test content",
            favourite=False,
            user_id=test_user.id
        )
        
        # Ensure prompt was created
        assert prompt is not None
        prompt_id = prompt.id
        
        # Delete the prompt
        result = AbstractDBTest.delete_entity(
            db_session=db_session,
            model_class=Prompt,
            requester_id=test_user.id,
            entity_id=prompt_id,
            ignore_deleted=True,
            skip_not_found=True
        )
        
        assert result is True
        
        # Verify soft delete
        deleted_prompt = db_session.query(Prompt).filter(Prompt.id == prompt_id).first()
        assert deleted_prompt is not None  # Entity still exists
        assert deleted_prompt.deleted_at is not None  # But has deleted_at timestamp
        assert deleted_prompt.deleted_by_user_id == test_user.id
    
    def test_list_prompts(self, db_session, test_user, test_prompt):
        """Test listing prompts."""
        # Create a few more prompts
        for i in range(3):
            AbstractDBTest.create_entity(
                db_session=db_session,
                model_class=Prompt,
                requester_id=test_user.id,
                name=f"Test Prompt {i}",
                description=f"Description {i}",
                content=f"Content {i}",
                favourite=False,
                user_id=test_user.id
            )
        
        # List all prompts for this user
        prompts = AbstractDBTest.list_entities(
            db_session=db_session,
            model_class=Prompt,
            requester_id=test_user.id,
            user_id=test_user.id,
            expected_count=4  # test_prompt + 3 new ones
        )
        
        assert len(prompts) == 4
        
        # Test filtering
        filtered_prompts = AbstractDBTest.list_entities(
            db_session=db_session,
            model_class=Prompt,
            requester_id=test_user.id,
            name="Test Prompt 1",
            expected_count=1
        )
        
        assert len(filtered_prompts) == 1
        assert filtered_prompts[0].name == "Test Prompt 1"
    
    def test_permission_checks(self, db_session, test_user, admin_user, team_prompt, team_with_user):
        """Test permission checks for prompts."""
        team, user = team_with_user
        
        # Owner should have read permission
        AbstractDBTest.assert_permission_check(
            db_session=db_session,
            model_class=Prompt,
            requester_id=test_user.id,
            entity_id=team_prompt.id,
            operation=Operation.READ,
            expected_result=True
        )
        
        # Another user should not have permission for team-owned prompt
        AbstractDBTest.assert_permission_check(
            db_session=db_session,
            model_class=Prompt,
            requester_id=admin_user.id,
            entity_id=team_prompt.id,
            operation=Operation.READ,
            expected_result=False
        )
    
    def test_full_crud_cycle(self, db_session, test_user):
        """Test a full CRUD cycle for prompts."""
        AbstractDBTest.test_full_crud_cycle(
            db_session=db_session,
            model_class=Prompt,
            requester_id=test_user.id,
            create_kwargs={
                "name": "CRUD Test Prompt",
                "description": "CRUD test description",
                "content": "CRUD test content",
                "favourite": True,
                "user_id": test_user.id
            },
            update_kwargs={
                "name": "Updated CRUD Prompt",
                "description": "Updated CRUD description" 
            },
            read_check_field="name"
        )
        
    def test_permission_scenarios(self, db_session, test_user, admin_user, test_team):
        """Test permission scenarios for prompts."""
        AbstractDBTest.test_permission_scenarios(
            db_session=db_session,
            model_class=Prompt,
            owner_id=test_user.id,
            other_user_id=admin_user.id,
            create_kwargs={
                "name": "Permission Test Prompt",
                "description": "Permission test description",
                "content": "Permission test content",
                "favourite": False,
                "user_id": test_user.id
            },
            # Adjust these based on your actual permission model:
            expect_owner_read=True,  # Owner can read
            expect_owner_update=False,  # Owner might not have admin access for updates
            expect_owner_delete=False   # Owner might not have admin access for deletes
        )