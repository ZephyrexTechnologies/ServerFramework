import pytest
from faker import Faker

from AbstractTest import SkipReason, TestToSkip
from lib.Environment import env
from logic.AbstractBLLTest import AbstractBLLTest, TestCategory, TestClassConfig
from logic.BLL_Auth import (
    InvitationManager,
    PermissionManager,
    RoleManager,
    TeamManager,
    TeamMetadataManager,
    UserManager,
    UserMetadataManager,
    UserTeamManager,
)

# Set default test configuration for all test classes
AbstractBLLTest.test_config = TestClassConfig(categories=[TestCategory.LOGIC])

# Initialize faker for generating test data once
faker = Faker()


class TestUserManager(AbstractBLLTest):
    class_under_test = UserManager
    create_fields = {
        "email": faker.email,
        "username": faker.user_name,
        "display_name": faker.name,
        "first_name": faker.first_name,
        "last_name": faker.last_name,
        "password": "Test1234!",
    }
    update_fields = {
        "display_name": f"Updated {faker.name()}",
        "first_name": f"Updated {faker.first_name()}",
        "last_name": f"Updated {faker.last_name()}",
    }
    unique_fields = ["username", "email"]

    skip_tests = [
        TestToSkip(
            name="test_batch_update",
            reason=SkipReason.IRRELEVANT,
            details="Password is required for user creation but not supported in batch update",
        ),
        TestToSkip(
            name="test_batch_delete",
            reason=SkipReason.IRRELEVANT,
            details="The only user that can delete a user is themself",
        ),
    ]

    def _generate_unique_value(self, prefix: str = "Test"):
        """Generate a unique email for testing."""
        return faker.email()

    @pytest.mark.depends()
    def test_create(self, admin_a, team_a):
        """Override: Test creating a user entity."""
        # Ensure the base create logic is called with necessary context
        self._create(admin_a.id, team_a.id)
        self._create_assert("create")

    @pytest.mark.depends(on=["test_create"])
    def test_delete(self, admin_a, team_a):
        """Override: Test deleting a user entity."""
        # Ensure a specific entity is created for this delete test
        self._create(admin_a.id, team_a.id, "delete")
        # Call the base delete logic with necessary context
        entity_id = self._delete(self.tracked_entities["delete"].id)
        # Assert deletion using the base assertion logic
        self._delete_assert(
            self.tracked_entities["delete"].id, self.tracked_entities["delete"].id
        )


class TestTeamManager(AbstractBLLTest):
    class_under_test = TeamManager
    create_fields = {
        "name": f"Test Team {faker.word()}",
        "description": faker.sentence(),
    }
    update_fields = {
        "name": f"Updated Team {faker.word()}",
        "description": f"Updated {faker.sentence()}",
    }
    unique_field = "name"


class TestRoleManager(AbstractBLLTest):
    class_under_test = RoleManager
    create_fields = {
        "name": f"Test Role {faker.word()}",
        "friendly_name": f"Test Friendly Role {faker.word()}",
        "mfa_count": 1,
        "password_change_frequency_days": 90,
        "team_id": None,  # This will be replaced in setup
    }
    update_fields = {
        "friendly_name": f"Updated Friendly Role {faker.word()}",
        "mfa_count": 2,
        "password_change_frequency_days": 180,
    }
    unique_field = "name"

    def setup_method(self, method):
        super().setup_method(method)

        # Team ID is required for roles, so we need to create a team first
        if hasattr(self, "team_a") and self.team_a:
            self.create_fields["team_id"] = self.team_a.id


class TestUserMetadataManager(AbstractBLLTest):
    class_under_test = UserMetadataManager
    create_fields = {
        "user_id": None,  # This will be replaced in setup
        "key": f"test_key_{faker.word()}",
        "value": faker.sentence(),
    }
    update_fields = {
        "value": f"Updated {faker.sentence()}",
    }
    unique_field = "key"

    def setup_method(self, method):
        super().setup_method(method)

        # User ID is required for metadata, so we need a user ID
        if hasattr(self, "admin_a") and self.admin_a:
            self.create_fields["user_id"] = self.admin_a.id


class TestTeamMetadataManager(AbstractBLLTest):
    class_under_test = TeamMetadataManager
    create_fields = {
        "team_id": None,  # This will be replaced in setup
        "key": f"test_key_{faker.word()}",
        "value": faker.sentence(),
    }
    update_fields = {
        "value": f"Updated {faker.sentence()}",
    }
    unique_field = "key"

    def setup_method(self, method):
        super().setup_method(method)

        # Team ID is required for metadata, so we need a team ID
        if hasattr(self, "team_a") and self.team_a:
            self.create_fields["team_id"] = self.team_a.id


class TestUserTeamManager(AbstractBLLTest):
    class_under_test = UserTeamManager
    create_fields = {
        "user_id": None,  # This will be replaced in setup
        "team_id": None,  # This will be replaced in setup
        "role_id": None,  # This will be replaced in setup
        "enabled": True,
    }
    update_fields = {
        "enabled": False,
    }

    def setup_method(self, method):
        super().setup_method(method)

        # Set required IDs
        if (
            hasattr(self, "admin_a")
            and self.admin_a
            and hasattr(self, "team_a")
            and self.team_a
        ):
            self.create_fields["user_id"] = self.admin_a.id
            self.create_fields["team_id"] = self.team_a.id
            # For role_id, we'll use the admin role ID
            self.create_fields["role_id"] = env("ADMIN_ROLE_ID")


class TestPermissionManager(AbstractBLLTest):
    class_under_test = PermissionManager
    create_fields = {
        "resource_type": "test_resource",
        "resource_id": faker.uuid4(),
        "user_id": None,  # This will be replaced in setup
        "can_view": True,
        "can_edit": True,
        "can_delete": False,
        "can_share": False,
    }
    update_fields = {
        "can_view": True,
        "can_edit": False,
        "can_delete": True,
        "can_share": True,
    }

    def setup_method(self, method):
        super().setup_method(method)

        # User ID is required for permissions
        if hasattr(self, "admin_a") and self.admin_a:
            self.create_fields["user_id"] = self.admin_a.id


class TestInvitationManager(AbstractBLLTest):
    class_under_test = InvitationManager
    create_fields = {
        "team_id": None,  # This will be replaced in setup
        "role_id": env("ADMIN_ROLE_ID"),
        "code": faker.uuid4()[:8].upper(),
        "max_uses": 5,
    }
    update_fields = {
        "max_uses": 10,
    }

    def setup_method(self, method):
        super().setup_method(method)

        # Team ID is required for invitations
        if hasattr(self, "team_a") and self.team_a:
            self.create_fields["team_id"] = self.team_a.id
