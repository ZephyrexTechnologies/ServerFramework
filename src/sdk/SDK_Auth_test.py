import json
import unittest

from .AbstractSDKTest import AbstractSDKTest
from .SDK_Auth import AuthSDK


class TestAuthSDK(AbstractSDKTest):
    """Tests for the AuthSDK module."""

    def setUp(self):
        """Set up the test environment."""
        super().setUp()

        # Create AuthSDK instance
        self.auth_sdk = AuthSDK(
            base_url=self.base_url,
            token=self.default_token,
            api_key=self.default_api_key,
        )

    def test_login(self):
        """Test login method."""
        # Set up mock response
        login_response = {
            "id": "user-123",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "display_name": "Test User",
            "token": "new_token_123",
            "teams": [
                {
                    "id": "team-123",
                    "name": "Test Team",
                    "role_id": "role-123",
                    "role_name": "admin",
                }
            ],
        }
        self.mock_response_json(login_response)

        # Call login method
        result = self.auth_sdk.login("test@example.com", "password123")

        # Verify requests call
        self.mock_request.assert_called_once()
        call_args = self.mock_request.call_args[1]

        self.assertEqual(call_args["method"], "POST")
        self.assertEqual(call_args["url"], f"{self.base_url}/v1/user/authorize")

        # Verify Authorization header contains Basic auth
        headers = call_args["headers"]
        self.assertTrue("Authorization" in headers)
        self.assertTrue(headers["Authorization"].startswith("Basic "))

        # Verify response and token update
        self.assertEqual(result, login_response)
        self.assertEqual(self.auth_sdk.token, "new_token_123")

    def test_register(self):
        """Test register method."""
        # Set up mock response
        register_response = {
            "user": {
                "id": "user-123",
                "email": "new@example.com",
                "first_name": "New",
                "last_name": "User",
                "display_name": "New User",
                "token": "new_user_token",
            }
        }
        self.mock_response_json(register_response)

        # Call register method
        result = self.auth_sdk.register(
            email="new@example.com",
            password="password123",
            first_name="New",
            last_name="User",
            display_name="New User",
        )

        # Verify requests call
        self.mock_request.assert_called_once()
        call_args = self.mock_request.call_args[1]

        self.assertEqual(call_args["method"], "POST")
        self.assertEqual(call_args["url"], f"{self.base_url}/v1/user")

        # Verify request data
        request_data = json.loads(call_args["data"])
        self.assertEqual(request_data["user"]["email"], "new@example.com")
        self.assertEqual(request_data["user"]["password"], "password123")
        self.assertEqual(request_data["user"]["first_name"], "New")
        self.assertEqual(request_data["user"]["last_name"], "User")
        self.assertEqual(request_data["user"]["display_name"], "New User")

        # Verify response
        self.assertEqual(result, register_response)

    def test_verify_token_valid(self):
        """Test verify_token method with valid token."""
        # Set up mock response for successful verification
        self.mock_response.status_code = 204
        self.mock_response.content = b""

        # Call verify_token method
        result = self.auth_sdk.verify_token()

        # Verify requests call
        self.mock_request.assert_called_once()
        call_args = self.mock_request.call_args[1]

        self.assertEqual(call_args["method"], "GET")
        self.assertEqual(call_args["url"], f"{self.base_url}/v1")

        # Verify response
        self.assertTrue(result)

    def test_verify_token_invalid(self):
        """Test verify_token method with invalid token."""
        # Set up mock response for failed verification
        self.mock_response.ok = False
        self.mock_response.status_code = 401

        # Call verify_token method
        result = self.auth_sdk.verify_token()

        # Verify requests call
        self.mock_request.assert_called_once()

        # Verify response
        self.assertFalse(result)

    def test_change_password(self):
        """Test change_password method."""
        # Set up mock response
        password_response = {"message": "Password changed successfully"}
        self.mock_response_json(password_response)

        # Call change_password method
        result = self.auth_sdk.change_password("old_password", "new_password")

        # Verify requests call
        self.mock_request.assert_called_once()
        call_args = self.mock_request.call_args[1]

        self.assertEqual(call_args["method"], "PATCH")
        self.assertEqual(call_args["url"], f"{self.base_url}/v1/user")

        # Verify request data
        request_data = json.loads(call_args["data"])
        self.assertEqual(request_data["current_password"], "old_password")
        self.assertEqual(request_data["new_password"], "new_password")

        # Verify response
        self.assertEqual(result, password_response)

    def test_get_current_user(self):
        """Test get_current_user method."""
        # Set up mock response
        user_response = {
            "user": {
                "id": "user-123",
                "email": "test@example.com",
                "display_name": "Test User",
                "first_name": "Test",
                "last_name": "User",
                "created_at": "2022-01-01T00:00:00Z",
            }
        }
        self.mock_response_json(user_response)

        # Call get_current_user method
        result = self.auth_sdk.get_current_user()

        # Verify requests call
        self.mock_request.assert_called_once()
        call_args = self.mock_request.call_args[1]

        self.assertEqual(call_args["method"], "GET")
        self.assertEqual(call_args["url"], f"{self.base_url}/v1/user")

        # Verify response
        self.assertEqual(result, user_response)

    def test_create_team(self):
        """Test create_team method."""
        # Set up mock response
        team_response = {
            "team": {
                "id": "team-123",
                "name": "New Team",
                "description": "Team description",
                "created_at": "2022-01-01T00:00:00Z",
            }
        }
        self.mock_response_json(team_response)

        # Call create_team method
        result = self.auth_sdk.create_team(
            name="New Team",
            description="Team description",
            image_url="https://example.com/image.png",
        )

        # Verify requests call
        self.mock_request.assert_called_once()
        call_args = self.mock_request.call_args[1]

        self.assertEqual(call_args["method"], "POST")
        self.assertEqual(call_args["url"], f"{self.base_url}/v1/team")

        # Verify request data
        request_data = json.loads(call_args["data"])
        self.assertEqual(request_data["team"]["name"], "New Team")
        self.assertEqual(request_data["team"]["description"], "Team description")
        self.assertEqual(
            request_data["team"]["image_url"], "https://example.com/image.png"
        )

        # Verify response
        self.assertEqual(result, team_response)

    def test_get_team_users(self):
        """Test get_team_users method."""
        # Set up mock response
        team_users_response = {
            "user_teams": [
                {
                    "id": "user-team-123",
                    "user_id": "user-123",
                    "team_id": "team-123",
                    "role_id": "role-123",
                    "user": {
                        "id": "user-123",
                        "email": "user1@example.com",
                        "display_name": "User One",
                    },
                },
                {
                    "id": "user-team-456",
                    "user_id": "user-456",
                    "team_id": "team-123",
                    "role_id": "role-456",
                    "user": {
                        "id": "user-456",
                        "email": "user2@example.com",
                        "display_name": "User Two",
                    },
                },
            ]
        }
        self.mock_response_json(team_users_response)

        # Call get_team_users method
        result = self.auth_sdk.get_team_users("team-123")

        # Verify requests call
        self.mock_request.assert_called_once()
        call_args = self.mock_request.call_args[1]

        self.assertEqual(call_args["method"], "GET")
        self.assertEqual(call_args["url"], f"{self.base_url}/v1/team/team-123/user")

        # Verify response
        self.assertEqual(result, team_users_response)

    def test_create_invitation(self):
        """Test create_invitation method."""
        # Set up mock response
        invitation_response = {
            "invitation": {
                "id": "invitation-123",
                "team_id": "team-123",
                "role_id": "role-123",
                "email": "invite@example.com",
                "code": "ABC123",
                "max_uses": 1,
                "created_at": "2022-01-01T00:00:00Z",
            }
        }
        self.mock_response_json(invitation_response)

        # Call create_invitation method
        result = self.auth_sdk.create_invitation(
            team_id="team-123",
            role_id="role-123",
            email="invite@example.com",
            max_uses=1,
        )

        # Verify requests call
        self.mock_request.assert_called_once()
        call_args = self.mock_request.call_args[1]

        self.assertEqual(call_args["method"], "POST")
        self.assertEqual(call_args["url"], f"{self.base_url}/v1/invitation")

        # Verify request data
        request_data = json.loads(call_args["data"])
        self.assertEqual(request_data["invitation"]["team_id"], "team-123")
        self.assertEqual(request_data["invitation"]["role_id"], "role-123")
        self.assertEqual(request_data["invitation"]["email"], "invite@example.com")
        self.assertEqual(request_data["invitation"]["max_uses"], 1)

        # Verify response
        self.assertEqual(result, invitation_response)

    def test_revoke_all_invitations(self):
        """Test revoke_all_invitations method."""
        # Set up mock response for successful deletion
        self.mock_response.status_code = 204
        self.mock_response.content = b""

        # Call revoke_all_invitations method
        self.auth_sdk.revoke_all_invitations("team-123")

        # Verify requests call
        self.mock_request.assert_called_once()
        call_args = self.mock_request.call_args[1]

        self.assertEqual(call_args["method"], "DELETE")
        self.assertEqual(
            call_args["url"], f"{self.base_url}/v1/team/team-123/invitation"
        )

    def test_get_sessions(self):
        """Test get_sessions method."""
        # Set up mock response
        sessions_response = {
            "user_sessions": [
                {
                    "id": "session-123",
                    "user_id": "user-123",
                    "session_key": "key-123",
                    "device_type": "web",
                    "browser": "Chrome",
                    "last_activity": "2022-01-01T00:00:00Z",
                },
                {
                    "id": "session-456",
                    "user_id": "user-123",
                    "session_key": "key-456",
                    "device_type": "mobile",
                    "browser": "Safari",
                    "last_activity": "2022-01-02T00:00:00Z",
                },
            ]
        }
        self.mock_response_json(sessions_response)

        # Call get_sessions method
        result = self.auth_sdk.get_sessions(offset=0, limit=10)

        # Verify requests call
        self.mock_request.assert_called_once()
        call_args = self.mock_request.call_args[1]

        self.assertEqual(call_args["method"], "GET")
        self.assertEqual(
            call_args["url"], f"{self.base_url}/v1/session?offset=0&limit=10"
        )

        # Verify response
        self.assertEqual(result, sessions_response)


if __name__ == "__main__":
    unittest.main()
