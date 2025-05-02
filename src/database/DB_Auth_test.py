from datetime import datetime, timedelta

import pytest
from faker import Faker

from AbstractTest import ParentEntity
from database.AbstractDBTest import AbstractDBTest
from database.DB_Auth import (
    AuthSession,
    FailedLoginAttempt,
    Invitation,
    InvitationInvitee,
    Permission,
    RateLimitPolicy,
    Role,
    Team,
    TeamMetadata,
    User,
    UserCredential,
    UserMetadata,
    UserRecoveryQuestion,
    UserTeam,
)
from lib.Environment import env

faker = Faker()


class TestUser(AbstractDBTest):
    class_under_test = User
    create_fields = {
        "email": faker.email,
        "display_name": lambda: faker.user_name().upper(),
        "first_name": faker.first_name,
        "last_name": faker.last_name,
    }
    update_fields = {
        "display_name": "Updated User",
        "first_name": "Updated",
        "last_name": "Name",
    }
    unique_field = "email"
    # def test_get_with_permission(self):
    #     """Test retrieving a user entity with explicit permission."""
    #     # User entities have a different permission model than other entities

    #     # Skip specific assertion - User entities have different visibility rules
    #     # that make the "no visibility by default" assertion inappropriate
    #     pytest.skip(
    #         "User entities have team-based visibility rules that differ from other entities"
    #     )

    # def test_user_specific_permissions(self):
    #     """Test User-specific permission behavior that takes into account their unique visibility model."""
    #     # Create a team for this test to isolate permissions
    #     test_team_id = self._create_or_get_team(
    #         f"perm_test_team_{self.test_instance_id}"
    #     )

    #     # Create a user in this team
    #     team_user_data = self._get_unique_entity_data()
    #     team_user = self.create_test_entity(return_type="dict", **team_user_data)
    #     self._setup_team_membership(team_user["id"], test_team_id, "user")

    #     # Create an isolated user not in any team
    #     isolated_user_data = self._get_unique_entity_data()
    #     isolated_user = self.create_test_entity(
    #         return_type="dict", **isolated_user_data
    #     )

    #     # Team user should not be able to see isolated user
    #     # (no team relationship connects them)
    #     team_user_retrieved = self.object_under_test.get(
    #         team_user["id"], self.db, return_type="dict", id=isolated_user["id"]
    #     )

    #     assert (
    #         team_user_retrieved is None
    #     ), f"Team user can see isolated user without permission"

    #     # Grant VIEW permission
    #     self.grant_permission(team_user["id"], isolated_user["id"], PermissionType.VIEW)

    #     # Now team user should be able to see isolated user
    #     team_user_retrieved_with_perm = self.object_under_test.get(
    #         team_user["id"], self.db, return_type="dict", id=isolated_user["id"]
    #     )

    #     assert (
    #         team_user_retrieved_with_perm is not None
    #     ), f"Team user cannot see isolated user with permission"
    #     assert (
    #         team_user_retrieved_with_perm["id"] == isolated_user["id"]
    #     ), f"Retrieved wrong entity"

    # def test_team_based_user_visibility(self):
    #     """Test that users can see other users in their teams."""
    #     # Create users in the same team
    #     team_id = self._create_or_get_team("visibility_test_team")

    #     # Create a user in the team
    #     team_user_data = self._get_unique_entity_data()
    #     team_user = self.create_test_entity(return_type="dict", **team_user_data)

    #     # Add both users to the same team
    #     self._setup_team_membership(team_user["id"], team_id, "user")
    #     self._setup_team_membership(self.other_user_id, team_id, "user")

    #     # The other user should be able to see the team user
    #     other_retrieved = self.object_under_test.get(
    #         self.other_user_id, self.db, return_type="dict", id=team_user["id"]
    #     )

    #     assert (
    #         other_retrieved is not None
    #     ), f"{self.object_under_test.__name__}: Team member cannot see other team members"
    #     assert (
    #         other_retrieved["id"] == team_user["id"]
    #     ), f"{self.object_under_test.__name__}: Retrieved wrong entity"
    @pytest.mark.parametrize("return_type", ["dict", "db", "model"])
    def test_CRUD_create(self, admin_a, return_type):
        self._CRUD_create(return_type)
        self._create_assert("CRUD_create_" + return_type)

    @pytest.mark.xfail(
        reason="Works when inspected in debugger but not when run normally."
    )
    def test_ORM_create(self, admin_a, team_a):
        self._ORM_create()
        self._create_assert("ORM_create")

    @pytest.mark.depends(on=["test_CRUD_create"])
    def test_CRUD_delete(self, admin_a, team_a):
        self._CRUD_create(
            "dict",
            admin_a.id,
            team_a.id,
            "CRUD_delete",
        )
        self._CRUD_delete(self.tracked_entities["CRUD_delete"]["id"])
        self._delete_assert(self.tracked_entities["CRUD_delete"]["id"], "CRUD_delete")

    @pytest.mark.depends(on=["test_CRUD_delete", "test_CRUD_get"])
    def test_CRUD_soft_delete(self, admin_a, team_a):
        self._CRUD_create(
            "dict",
            admin_a.id,
            team_a.id,
            "CRUD_delete",
        )
        self._CRUD_delete(self.tracked_entities["CRUD_delete"]["id"])
        self._CRUD_get("dict", env("ROOT_ID"), None, "CRUD_get_deleted", "CRUD_delete")
        self._get_assert("CRUD_get_deleted")


class TestUserCredential(AbstractDBTest):
    class_under_test = UserCredential
    create_fields = {
        "user_id": None,  # Will be populated in setup
        "password_hash": "test_hash",
        "password_salt": "test_salt",
    }
    update_fields = {
        "password_hash": "updated_hash",
        "password_salt": "updated_salt",
    }


class TestUserRecoveryQuestion(AbstractDBTest):
    class_under_test = UserRecoveryQuestion
    create_fields = {
        "user_id": None,  # Will be populated in setup
        "question": "Test security question?",
        "answer": "Test answer",
    }
    update_fields = {
        "question": "Updated security question?",
        "answer": "Updated answer",
    }


class TestTeam(AbstractDBTest):
    class_under_test = Team
    create_fields = {
        "name": "Test Team",
        "description": "Test team description",
        "encryption_key": "test_key",
    }
    update_fields = {
        "name": "Updated Team",
        "description": "Updated team description",
    }
    unique_field = "name"


class TestTeamMetadata(AbstractDBTest):
    class_under_test = TeamMetadata
    create_fields = {
        "team_id": "",
        "key": "test_key",
        "value": "test_value",
    }
    update_fields = {
        "key": "updated_key",
        "value": "updated_value",
    }


class TestRole(AbstractDBTest):
    class_under_test = Role
    create_fields = {
        "name": "test_role",
        "friendly_name": "Test Role",
        "mfa_count": 1,
        "password_change_frequency_days": 90,
    }
    update_fields = {
        "friendly_name": "Updated Test Role",
        "mfa_count": 2,
        "password_change_frequency_days": 180,
    }
    unique_field = "name"


class TestUserTeam(AbstractDBTest):
    class_under_test = UserTeam
    create_fields = {
        "user_id": "",  # Will be populated in setup
        "team_id": "",  # Will be populated in setup
        "role_id": env("USER_ROLE_ID"),  # Will be populated in setup
        "enabled": True,
    }
    update_fields = {
        "enabled": False,
    }


class TestInvitation(AbstractDBTest):
    class_under_test = Invitation
    create_fields = {
        "team_id": None,  # Will be populated in setup
        "role_id": env("USER_ROLE_ID"),  # Will be populated in setup
        "user_id": None,  # Will be populated in setup
        "code": "test_invitation_code",
        "max_uses": 5,
    }
    update_fields = {
        "code": "updated_invitation_code",
        "max_uses": 10,
    }


class TestInvitationInvitee(AbstractDBTest):
    class_under_test = InvitationInvitee
    parent_entities = [
        ParentEntity(
            name="invitation", foreign_key="invitation_id", test_class=TestInvitation
        )
    ]
    create_fields = {
        "invitation_id": None,  # Will be populated in setup
        "user_id": None,  # Will be populated in setup
        "email": "invitee@example.com",
        "is_accepted": False,
    }
    update_fields = {
        "is_accepted": True,
        "accepted_at": datetime.now(),
    }


class TestPermission(AbstractDBTest):
    class_under_test = Permission
    create_fields = {
        "resource_type": "invitations",
        "resource_id": "",  # Will be populated in setup
        "can_view": True,
        "can_edit": False,
        "can_delete": False,
        "can_share": False,
    }
    update_fields = {
        "can_edit": True,
        "can_share": True,
    }
    parent_entities = [
        ParentEntity(
            name="invitation", foreign_key="resource_id", test_class=TestInvitation
        )
    ]


class TestUserMetadata(AbstractDBTest):
    class_under_test = UserMetadata
    create_fields = {
        "user_id": "",  # Will be populated in setup
        "key": "test_key",
        "value": "test_value",
    }
    update_fields = {
        "key": "updated_key",
        "value": "updated_value",
    }


class TestFailedLoginAttempt(AbstractDBTest):
    class_under_test = FailedLoginAttempt
    create_fields = {
        "user_id": "",  # Will be populated in setup
        "ip_address": "127.0.0.1",
    }
    update_fields = {
        "ip_address": "192.168.1.1",
    }


class TestAuthSession(AbstractDBTest):
    class_under_test = AuthSession
    create_fields = {
        "user_id": "",  # Will be populated in setup
        "session_key": faker.uuid4,
        "jwt_issued_at": datetime.now(),
        "last_activity": datetime.now(),
        "expires_at": datetime.now() + timedelta(days=1),
        "is_active": True,
    }
    update_fields = {
        "refresh_token_hash": "updated_refresh_token",
        "last_activity": datetime.now(),
        "is_active": False,
    }
    unique_field = "session_key"


class TestRateLimitPolicy(AbstractDBTest):
    class_under_test = RateLimitPolicy
    create_fields = {
        "name": "test_rate_limit",
        "resource_pattern": "api/v1/test/*",
        "window_seconds": 60,
        "max_requests": 100,
        "scope": "user",
    }
    update_fields = {
        "window_seconds": 120,
        "max_requests": 200,
        "scope": "ip",
    }
    unique_field = "name"
