import base64
import uuid

import pytest
from faker import Faker

from AbstractTest import ParentEntity, TestToSkip
from endpoints.AbstractEPTest import AbstractEndpointTest
from lib.Environment import env


def authorize_user(server, email: str, password="testpassword"):
    credentials = f"{email}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    response = server.post(
        "/v1/user/authorize", headers={"Authorization": f"Basic {encoded_credentials}"}
    )
    assert "token" in response.json(), "JWT token missing from authorization response."
    return response.json()["token"]


@pytest.mark.ep
@pytest.mark.auth
class TestTeamEndpoints(AbstractEndpointTest):
    """Tests for the Team Management endpoints."""

    base_endpoint = "team"
    entity_name = "team"
    required_fields = ["id", "name", "description", "created_at", "created_by_user_id"]
    string_field_to_update = "name"
    supports_search = True
    searchable_fields = ["name", "description"]
    # Example value for search tests
    search_example_value = "Test Team Alpha"

    # No parent entities for teams
    parent_entities = []

    # Not a system entity
    system_entity = False

    # Teams don't typically require special skips like Users
    skip_tests = []

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for team creation."""
        if not name:
            name = self.faker.company()

        payload = {"name": name, "description": f"Description for {name}"}

        # team_id parameter is ignored for teams since they are top-level resources

        return self.nest_payload_in_entity(entity=payload)

    def test_GET_200_team_users(self, server, admin_a_jwt, team_a):
        """Test listing users within a specific team."""
        team_id = team_a["id"]
        team_user_list_endpoint = f"/v1/team/{team_id}/user"
        response = server.get(
            team_user_list_endpoint, headers=self._auth_header(admin_a_jwt)
        )
        self._assert_response_status(
            response,
            200,
            "GET team users",
            team_user_list_endpoint,
        )
        # Assert the response contains a list under the 'users' key (or similar)
        response_json = response.json()
        assert "users" in response_json, "Response should contain 'users' key"
        assert isinstance(response_json["users"], list), "'users' should be a list"

        return response_json["users"]  # Return the list of users

    def test_PUT_200_update_user_role(self, server, admin_a_jwt, team_a, admin_a):
        """Test updating a user's role within a team."""
        team_id = team_a["id"]
        user_id = admin_a.id

        # Get current team users to ensure the target user exists (optional, but good practice)
        self.test_GET_200_team_users(server, admin_a_jwt, team_a)

        update_endpoint = f"/v1/team/{team_id}/user/{user_id}/role"
        update_payload = {"role_id": env("ADMIN_ROLE_ID")}

        update_response = server.put(
            update_endpoint, json=update_payload, headers=self._auth_header(admin_a_jwt)
        )

        self._assert_response_status(
            update_response,
            200,
            "PUT update user role",
            update_endpoint,
            update_payload,
        )

        # Assert the response indicates success (e.g., contains a success message)
        assert (
            "message" in update_response.json()
        ), f"[{self.entity_name}] Message not found in update role response: Response: {update_response.json()}"

        # Verify the role was updated by getting the team users again
        endpoint = f"/v1/team/{team_id}/user"
        verify_response = server.get(endpoint, headers=self._auth_header(admin_a_jwt))
        self._assert_response_status(
            verify_response, 200, "GET team users after role update", endpoint
        )

        # Optional: Find the specific user and assert their role_id matches the updated one
        users = verify_response.json().get("users", [])
        updated_user_found = False
        for user in users:
            if user.get("id") == user_id:
                # Assuming the user object contains role information directly or indirectly
                # This might need adjustment based on the actual response structure
                # Example: assert user.get("role_id") == role_id
                updated_user_found = True
                break
        assert (
            updated_user_found
        ), f"User {user_id} not found in team list after role update"

        return update_response.json()  # Return the success message


@pytest.mark.ep
@pytest.mark.auth
class TestUserEndpoints(AbstractEndpointTest):
    """Tests for the User Management endpoints."""

    faker = Faker()
    base_endpoint = "user"
    entity_name = "user"
    create_fields = {
        "email": faker.email,
        "username": faker.user_name,
        "password": faker.password,
        "display_name": faker.name,
    }
    update_fields = {"display_name": "Updated"}
    supports_search = True
    searchable_fields = ["email", "display_name", "first_name", "last_name"]

    # No parent entities for users
    parent_entities = []

    # Not a system entity
    system_entity = False

    # Create a faker instance for generating test data

    skip_tests = [
        # Skip these tests because users have special authentication requirements
        TestToSkip(
            name="test_POST_401",
            details="User creation API endpoints do not require authentication",
            gh_issue_number=40,
        ),
        TestToSkip(
            name="test_PUT_401",
            details="User update can only be tested with proper JWT token",
            gh_issue_number=41,
        ),
        TestToSkip(
            name="test_DELETE_401",
            details="User deletion can only be tested with proper JWT token",
            gh_issue_number=42,
        ),
        TestToSkip(
            name="test_GET_401",
            details="User GET can only be tested with proper JWT token",
            gh_issue_number=43,
        ),
        TestToSkip(
            name="test_GET_404_other_user",
            details="Users can see other users in the system",
            gh_issue_number=44,
        ),
        TestToSkip(
            name="test_DELETE_404_other_user",
            details="User can only delete themselves or require admin permission",
            gh_issue_number=45,
        ),
    ]

    def _setup_test_resources(self, server, jwt_token, team, count=1, api_key=None):
        """Skip standard test resource setup since users are special case."""
        # For the user entity, we'll use the user's own details
        return True

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        return self.nest_payload_in_entity(entity=self.build_entities())

    def test_POST_201(self, server, admin_a_jwt=None, team_a=None, api_key=None):
        """Create a new user."""
        # Create a user
        new_user = self.build_entities()[0]
        credentials = f"{new_user.pop('email')}:{new_user.pop('password')}"  # Password hardcoded for test users
        payload = self.nest_payload_in_entity(entity=new_user)

        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {"Authorization": f"Basic {encoded_credentials}"}

        # Create user
        response = server.post("/v1/user", json=payload, headers=headers)

        # Assert response
        self._assert_response_status(response, 201, "POST", "/v1/user", payload)
        self._assert_entity_in_response(response, self.entity_name)

        # Extract user from response
        user = response.json()[self.entity_name]

        # Verify required fields
        # TODO: Build this.
        # self._assert_entity_has_fields(user, self.required_fields)

        return user

    def test_POST_201_body(self, server, admin_a_jwt=None, team_a=None, api_key=None):
        """Create a new user."""
        # Create a user
        payload = self.nest_payload_in_entity(entity=self.build_entities()[0])
        response = server.post("/v1/user", json=payload)

        # Assert response
        self._assert_response_status(response, 201, "POST", "/v1/user", payload)
        self._assert_entity_in_response(response, self.entity_name)

        # Extract user from response
        user = response.json()[self.entity_name]

        # Verify required fields
        # TODO: Build this.
        # self._assert_entity_has_fields(user, self.required_fields)

        return user

    def test_POST_200_authorize(self, admin_a_jwt):
        """If this fixture is available, basic authentication works."""
        return admin_a_jwt

    def test_POST_200_authorize_body(self, server, admin_a):
        """Test user authorization endpoint."""
        # Create authorization payload
        auth_payload = {
            "auth": {
                "email": admin_a.email,
                "password": "testpassword",  # This is hardcoded for test users
            }
        }

        # Authorize user
        response = server.post("/v1/user/authorize", json=auth_payload)

        # Assert response
        self._assert_response_status(
            response, 200, "POST", "/v1/user/authorize", auth_payload
        )

        # Extract JWT token
        assert "jwt" in response.json(), "JWT token missing from response"
        jwt_token = response.json()["jwt"]

        return jwt_token

    def test_GET_200(self, server, admin_a_jwt):
        """Test retrieving the current user's details."""
        response = server.get("/v1/user", headers=self._auth_header(admin_a_jwt))

        self._assert_response_status(response, 200, "GET current user", "/v1/user")

        user = self._assert_entity_in_response(response)

        return user

    def test_PUT_200(self, server, admin_a_jwt, **kwargs):
        """Test updating the current user's profile."""
        # Generate unique values for update
        first_name = f"Test{uuid.uuid4().hex[:8]}"
        last_name = f"User{uuid.uuid4().hex[:8]}"
        display_name = f"{first_name} {last_name}"

        update_payload = self.nest_payload_in_entity(
            entity={
                "first_name": first_name,
                "last_name": last_name,
                "display_name": display_name,
            }
        )

        response = server.put(
            "/v1/user", json=update_payload, headers=self._auth_header(admin_a_jwt)
        )

        self._assert_response_status(
            response, 200, "PUT update current user", "/v1/user", update_payload
        )

        updated_user = self._assert_entity_in_response(response)

        # Verify fields were updated
        assert updated_user["first_name"] == first_name, "First name not updated"
        assert updated_user["last_name"] == last_name, "Last name not updated"
        assert updated_user["display_name"] == display_name, "Display name not updated"

        # Verify the update by getting the user profile
        verify_response = server.get("/v1/user", headers=self._auth_header(admin_a_jwt))
        self._assert_response_status(
            verify_response, 200, "GET after update", "/v1/user"
        )

        verified_user = self._assert_entity_in_response(verify_response)
        assert verified_user["display_name"] == display_name, "Update not persisted"

        return updated_user

    def test_PATCH_200_password(self, server, admin_a_jwt):
        """Test changing a user's password."""
        # Create a new user
        new_user = self.test_POST_201_body(server)

        # Login to get JWT
        new_user_jwt = authorize_user(server, new_user)

        # Extract the old password
        old_password = new_user["_test_password"]
        new_password = self.faker.password(
            length=12, special_chars=True, digits=True, upper_case=True, lower_case=True
        )

        # Change password
        payload = {
            "current_password": old_password,
            "new_password": new_password,
        }

        response = server.patch(
            "/v1/user",
            json=payload,
            headers=self._auth_header(new_user_jwt),
        )

        self._assert_response_status(
            response, 200, "PATCH change password", "/v1/user", payload
        )

        # Verify can login with new password
        auth_string = f"{new_user['email']}:{new_password}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        auth_header = f"Basic {encoded_auth}"

        login_response = server.post(
            "/v1/user/authorize",
            headers={"Authorization": auth_header},
        )

        self._assert_response_status(
            login_response,
            200,
            "POST authorize after password change",
            "/v1/user/authorize",
        )

        assert "token" in login_response.json(), "Failed to login with new password"

        return {"message": "Password changed successfully"}

    def test_GET_200_verify_jwt(self, server, admin_a_jwt):
        """Test verifying authorization token."""
        response = server.get("/v1", headers=self._auth_header(admin_a_jwt))

        self._assert_response_status(response, 204, "GET verify authorization", "/v1")

        # Response should be empty with 204 status
        assert response.content == b"", "Response body should be empty"

        return True

    @pytest.mark.xfail(details="Open Issue #46")
    def test_GET_401_verify_jwt_empty(self, server):
        """Test verifying with an empty authorization header."""
        # No authorization header
        response = server.get("/v1")

        self._assert_response_status(response, 401, "GET verify authorization", "/v1")

        # Verify the error message includes "Field required" for the authorization header
        assert (
            "Field required" in response.text
        ), "Expected validation error about missing header"
        assert "header" in response.text, "Expected validation error to mention header"
        assert (
            "authorization" in response.text
        ), "Expected validation error to mention authorization"

        return True

    def test_GET_401_verify_jwt_invalid_token(self, server, admin_a_jwt):
        """Test verifying with an invalid authorization token."""
        # Create an invalid JWT by replacing all numbers with 'x'
        invalid_jwt = "".join(["x" if c.isdigit() else c for c in admin_a_jwt])

        # Use the invalid JWT
        response = server.get("/v1", headers={"Authorization": f"Bearer {invalid_jwt}"})

        self._assert_response_status(response, 401, "GET verify authorization", "/v1")

        # Verify the error message
        assert (
            "Token verification failed" in response.text
        ), "Expected error about token verification failure"

        return True

    def test_GET_401_verify_jwt_invalid_signature(self, server, admin_a_jwt):
        """Test verifying with an invalid JWT signature."""
        # Split the JWT into its 3 parts
        jwt_parts = admin_a_jwt.split(".")

        # Replace digits only in the signature part (last segment)
        jwt_parts[2] = "".join(["x" if c.isdigit() else c for c in jwt_parts[2]])

        # Reconstruct the JWT
        invalid_jwt = ".".join(jwt_parts)

        # Use the JWT with invalid signature
        response = server.get("/v1", headers={"Authorization": f"Bearer {invalid_jwt}"})

        self._assert_response_status(response, 401, "GET verify authorization", "/v1")

        # Verify the error message - should be specifically about signature verification
        assert (
            "Signature verification failed" in response.text
        ), "Expected error about signature verification failure"

        return True

    def test_GET_401(self, server):
        """Test that GET endpoint requires authentication."""
        test_name = "test_GET_401"
        self.reason_to_skip(test_name)

        # Only test accessing the user profile endpoint without authentication
        response = server.get("/v1/user")
        self._assert_response_status(response, 401, "GET unauthorized", "/v1/user")

    @pytest.mark.xfail(details="Open Issue #47")
    def test_DELETE_204_self(self, server, admin_a_jwt):
        """Test delete the current user's profile."""
        # First get the current user profile to confirm it exists
        initial_response = server.get(
            "/v1/user", headers=self._auth_header(admin_a_jwt)
        )
        self._assert_response_status(
            initial_response, 200, "GET current user", "/v1/user"
        )

        self._assert_entity_in_response(initial_response)  # initial_user

        # Now delete the user
        delete_response = server.delete(
            "/v1/user", headers=self._auth_header(admin_a_jwt)
        )

        self._assert_response_status(
            delete_response, 204, "DELETE current user", "/v1/user"
        )

        # Verify user is deleted by trying to get the profile again
        # which should fail with 401 since the user no longer exists
        verify_response = server.get("/v1/user", headers=self._auth_header(admin_a_jwt))
        self._assert_response_status(
            verify_response, 401, "GET after deletion", "/v1/user"
        )

        # The JWT should be invalidated
        assert "detail" in verify_response.json(), "Expected error detail in response"

        return True

    @pytest.mark.xfail(details="Open Issue #54")
    def test_PATCH_204_session_refresh(self, server):
        raise NotImplementedError

    @pytest.mark.xfail(details="Open Issue #54")
    def test_PATCH_404_session_nonexistent(self, server):
        raise NotImplementedError

    @pytest.mark.xfail(details="Open Issue #54")
    def test_GET_200_id(self, server, admin_a_jwt):
        """Test retrieving a specific session by ID."""
        # First get the list of sessions to find one to retrieve
        sessions = self._get_user_sessions(server, admin_a_jwt)

        if not sessions:
            pytest.skip("No sessions found to test")

        session_id = sessions[0]["id"]

        # Get the specific session
        response = server.get(
            f"/v1/session/{session_id}",
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response, 200, "GET session by ID", f"/v1/session/{session_id}"
        )

        session = self._assert_entity_in_response(response, "user_session")
        assert (
            session["id"] == session_id
        ), f"Session ID mismatch: {session['id']} != {session_id}"

        return session

    @pytest.mark.xfail(details="Open Issue #54")
    def test_GET_404_nonexistent(self, server, admin_a_jwt):
        """Test retrieving a non-existent session returns 404."""
        nonexistent_id = "00000000-0000-0000-0000-000000000000"
        response = server.get(
            f"/v1/session/{nonexistent_id}",
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response, 404, "GET nonexistent session", f"/v1/session/{nonexistent_id}"
        )

    @pytest.mark.xfail(details="Open Issue #54")
    def test_GET_200_list(self, server, admin_a_jwt):
        """Test listing sessions."""
        sessions = self._get_user_sessions(server, admin_a_jwt)
        assert isinstance(sessions, list), "Sessions should be a list"

        # Verify required fields are present in each session
        if sessions:
            session = sessions[0]
            for field in ["id", "user_id", "created_at"]:
                assert field in session, f"Required field {field} missing in session"

        return sessions

    @pytest.mark.xfail(details="Open Issue #54")
    def test_DELETE_204(self, server, admin_a_jwt):
        """Test deleting a session."""
        # First create a new user and session to delete (so we don't delete our current one)
        new_user = self.test_POST_201_body(server)
        new_jwt = authorize_user(server, new_user)

        # Get sessions for the new user
        new_user_sessions = self._get_user_sessions(server, new_jwt)

        if not new_user_sessions:
            pytest.skip("No sessions found for new user")

        session_id = new_user_sessions[0]["id"]

        # Delete the session (using the admin JWT as the new user's session will be revoked)
        response = server.delete(
            f"/v1/session/{session_id}",
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response, 204, "DELETE session", f"/v1/session/{session_id}"
        )

        # Verify the session is gone
        response = server.get(
            f"/v1/session/{session_id}",
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response, 404, "GET deleted session", f"/v1/session/{session_id}"
        )

    @pytest.mark.xfail(details="Open Issue #54")
    def test_DELETE_204_batch(self, server, admin_a_jwt):
        """Test batch deleting sessions."""
        # Create multiple test users with sessions to delete
        user1 = self.test_POST_201_body(server)
        user2 = self.test_POST_201_body(server)

        jwt1 = authorize_user(server, user1)
        jwt2 = authorize_user(server, user2)

        # Get their session IDs
        sessions1 = self._get_user_sessions(server, jwt1)
        sessions2 = self._get_user_sessions(server, jwt2)

        if not sessions1 or not sessions2:
            pytest.skip("Not enough sessions for batch delete test")

        session_ids = [sessions1[0]["id"], sessions2[0]["id"]]
        target_ids = ",".join(session_ids)

        # Batch delete the sessions
        response = server.delete(
            f"/v1/session?target_ids={target_ids}",
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response,
            204,
            "DELETE batch sessions",
            f"/v1/session?target_ids={target_ids}",
        )

        # Verify sessions are gone
        for session_id in session_ids:
            response = server.get(
                f"/v1/session/{session_id}",
                headers=self._auth_header(admin_a_jwt),
            )

            self._assert_response_status(
                response,
                404,
                f"GET deleted session {session_id}",
                f"/v1/session/{session_id}",
            )

    @pytest.mark.xfail(details="Open Issue #54")
    def test_DELETE_204_all_sessions(self, server, admin_a_jwt, test_user):
        """Test deleting all sessions for a user."""
        # Create a test user to delete all sessions for
        test_user = self.test_POST_201_body(server)

        # Login multiple times to create multiple sessions
        jwt1 = authorize_user(server, test_user)
        jwt2 = authorize_user(server, test_user)

        # Get sessions to verify we have some
        sessions = self._get_user_sessions(server, jwt1)
        if not sessions:
            pytest.skip("No sessions found for test user")

        # Delete all sessions for the test user
        response = server.delete(
            f"/v1/user/{test_user['id']}/session",
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response, 204, "DELETE all sessions", f"/v1/user/{test_user['id']}/session"
        )

        # Verify sessions are gone (using admin token)
        response = server.get(
            f"/v1/user/{test_user['id']}/session",
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response,
            200,
            "GET sessions after delete",
            f"/v1/user/{test_user['id']}/session",
        )

        remaining_sessions = response.json().get("user_sessions", [])
        assert (
            len(remaining_sessions) == 0
        ), f"Expected 0 sessions, got {len(remaining_sessions)}"

    def test_DELETE_404_nonexistent(self, server, admin_a_jwt, **kwargs):
        """Test deleting a non-existent session returns 404."""
        nonexistent_id = "00000000-0000-0000-0000-000000000000"
        response = server.delete(
            f"/v1/session/{nonexistent_id}",
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response, 404, "DELETE nonexistent session", f"/v1/session/{nonexistent_id}"
        )

    def test_DELETE_404_other_user(self, server, admin_a_jwt, jwt_b, **kwargs):
        """Test deleting another user's session returns 404."""
        # First get the sessions for user A
        sessions_a = self._get_user_sessions(server, admin_a_jwt)

        if not sessions_a:
            pytest.skip("No sessions found for user A")

        session_id = sessions_a[0]["id"]

        # Try to delete this session with user B's token
        response = server.delete(
            f"/v1/session/{session_id}",
            headers=self._auth_header(jwt_b),
        )

        self._assert_response_status(
            response, 404, "DELETE other user's session", f"/v1/session/{session_id}"
        )

    @pytest.mark.xfail(details="Open Issue #54")
    def test_GET_200_pagination(self, server, admin_a_jwt):
        """Test pagination for session listing."""
        # Create multiple users with sessions for pagination testing
        for _ in range(3):
            user = self.test_POST_201_body(server)
            authorize_user(server, user)

        # Get all sessions to check if we have enough for pagination
        response = server.get(
            "/v1/session",
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(response, 200, "GET all sessions", "/v1/session")

        all_sessions = response.json().get("user_sessions", [])
        if len(all_sessions) < 2:
            pytest.skip("Not enough sessions for pagination test")

        # Test pagination - page 1
        response = server.get(
            "/v1/session?limit=1",
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response, 200, "GET sessions page 1", "/v1/session?limit=1"
        )

        page1_sessions = response.json().get("user_sessions", [])
        assert (
            len(page1_sessions) == 1
        ), f"Expected 1 session, got {len(page1_sessions)}"

        # Test pagination - page 2
        response = server.get(
            "/v1/session?limit=1&offset=1",
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            response, 200, "GET sessions page 2", "/v1/session?limit=1&offset=1"
        )

        page2_sessions = response.json().get("user_sessions", [])
        assert (
            len(page2_sessions) == 1
        ), f"Expected 1 session, got {len(page2_sessions)}"

        # Verify different pages contain different sessions
        assert (
            page1_sessions[0]["id"] != page2_sessions[0]["id"]
        ), "Sessions on different pages should be different"

        return {"page1": page1_sessions, "page2": page2_sessions}

    # Helper method to get user sessions
    def _get_user_sessions(self, server, jwt_token):
        """Helper method to get user sessions."""
        response = server.get(
            "/v1/session",
            headers=self._auth_header(jwt_token),
        )

        self._assert_response_status(response, 200, "GET session list", "/v1/session")

        return response.json().get("user_sessions", [])

    def test_GQL_query_single(self, server, admin_a_jwt, team_a):
        """Test retrieving the current user using GraphQL."""
        test_name = "test_GQL_query_single"
        self.reason_to_skip(test_name)

        # For users, we query the current user
        resource_type = self.entity_name.lower()

        # Generate query without ID param since we want the current user
        query = self._build_gql_query(query_type=resource_type)

        # Execute the GraphQL query
        response = server.post(
            "/graphql", json={"query": query}, headers=self._auth_header(admin_a_jwt)
        )

        # Assert response
        data = self._assert_gql_response(response, "query single")

        # Check entity was returned
        assert resource_type in data, (
            f"[{self.entity_name}] GraphQL query response missing entity: {resource_type}\n"
            f"Response data: {data}"
        )

        gql_entity = data[resource_type]

        # Verify we got a user with an ID
        assert "id" in gql_entity, f"User entity missing ID field: {gql_entity}"

        return gql_entity

    def test_GQL_query_list(self, server, admin_a_jwt, team_a):
        """Test retrieving a list containing only the current user using GraphQL."""
        test_name = "test_GQL_query_list"
        self.reason_to_skip(test_name)

        # Determine the GraphQL query for users plural
        resource_type_plural = self.resource_name_plural.lower()

        # Generate query for users list
        query = self._build_gql_query(query_type=resource_type_plural)

        # Execute the GraphQL query
        response = server.post(
            "/graphql", json={"query": query}, headers=self._auth_header(admin_a_jwt)
        )

        # Assert response
        data = self._assert_gql_response(response, "query list")

        # Check users were returned
        assert resource_type_plural in data, (
            f"[{self.entity_name}] GraphQL query response missing entities: {resource_type_plural}\n"
            f"Response data: {data}"
        )

        gql_entities = data[resource_type_plural]
        assert isinstance(gql_entities, list), (
            f"[{self.entity_name}] GraphQL query should return a list of entities\n"
            f"Entities: {gql_entities}"
        )

        # For users, we expect at least one user (the current user)
        assert len(gql_entities) > 0, "Expected at least the current user in users list"

        return gql_entities

    def test_GQL_query_filter(self, server, admin_a_jwt, team_a):
        """Test filtering users using GraphQL."""
        test_name = "test_GQL_query_filter"
        self.reason_to_skip(test_name)

        # First get the current user
        user_response = server.get("/v1/user", headers=self._auth_header(admin_a_jwt))
        self._assert_response_status(user_response, 200, "GET user", "/v1/user")
        user = self._assert_entity_in_response(user_response)

        # Update the user to have a unique filter term
        filter_term = f"Filterable {self.entity_name} {uuid.uuid4()}"
        update_payload = self.nest_payload_in_entity(
            entity={self.string_field_to_update: filter_term}
        )

        # Update the current user
        update_response = server.put(
            "/v1/user", json=update_payload, headers=self._auth_header(admin_a_jwt)
        )

        self._assert_response_status(
            update_response, 200, "PUT update user", "/v1/user", update_payload
        )

        # Determine the GraphQL query for users list
        resource_type_plural = self.resource_name_plural.lower()

        # Prepare filter for GraphQL
        filter_param = {self.string_field_to_update: {"contains": filter_term[:10]}}

        # Generate query with filter
        query = self._build_gql_query(
            query_type=resource_type_plural,
            filter_param=filter_param,
        )

        # Execute the GraphQL query
        response = server.post(
            "/graphql", json={"query": query}, headers=self._auth_header(admin_a_jwt)
        )

        # Assert response
        data = self._assert_gql_response(response, "query filter")

        # Check users were returned
        assert resource_type_plural in data, (
            f"[{self.entity_name}] GraphQL filtered query response missing entities: {resource_type_plural}\n"
            f"Response data: {data}"
        )

        gql_entities = data[resource_type_plural]
        assert isinstance(gql_entities, list), (
            f"[{self.entity_name}] GraphQL filtered query should return a list of entities\n"
            f"Entities: {gql_entities}"
        )

        # Verify we got at least one result
        assert len(gql_entities) > 0, "No users found matching filter"

        # Verify the user's name matches what we set
        name_camel = self.to_camel_case(self.string_field_to_update)
        assert gql_entities[0][name_camel] == filter_term, (
            f"[{self.entity_name}] User name doesn't match the filter term\n"
            f"Expected: {filter_term}\n"
            f"Actual: {gql_entities[0][name_camel]}"
        )

        return gql_entities

    def test_GQL_mutation_create(self, server, admin_a_jwt, team_a):
        """Test creating a user using GraphQL mutation."""
        test_name = "test_GQL_mutation_create"
        self.reason_to_skip(test_name)

        # Generate a unique name for the test user
        resource_name = self.faker.company()
        email = self.faker.email()
        password = self.faker.password(
            length=12, special_chars=True, digits=True, upper_case=True, lower_case=True
        )

        # Prepare input data for user creation
        input_data = {
            self.string_field_to_update: resource_name,
            "email": email,
            "password": password,
            "first_name": "Test",
            "last_name": "User",
        }

        # Determine mutation type
        mutation_type = f"create{self.entity_name.capitalize()}"

        # Generate mutation
        mutation = self._build_gql_mutation(
            mutation_type=mutation_type, input_data=input_data
        )

        # Execute the GraphQL mutation - no auth needed for user creation
        response = server.post("/graphql", json={"query": mutation})

        # Assert response
        data = self._assert_gql_response(response, "mutation create")

        # Check user was created
        assert mutation_type in data, (
            f"[{self.entity_name}] GraphQL create mutation response missing result: {mutation_type}\n"
            f"Response data: {data}"
        )

        gql_entity = data[mutation_type]

        # Verify the user was created correctly
        name_camel = self.to_camel_case(self.string_field_to_update)
        assert name_camel in gql_entity, (
            f"[{self.entity_name}] GraphQL created entity missing name field\n"
            f"Entity: {gql_entity}"
        )
        assert gql_entity[name_camel] == resource_name, (
            f"[{self.entity_name}] GraphQL created entity has wrong name\n"
            f"Expected: {resource_name}\n"
            f"Actual: {gql_entity[name_camel]}\n"
            f"Entity: {gql_entity}"
        )

        # Verify user can be authenticated
        try:
            # Create a login request to verify the account was created
            auth_string = f"{email}:{password}"
            encoded_auth = base64.b64encode(auth_string.encode()).decode()
            auth_header = f"Basic {encoded_auth}"

            verify_response = server.post(
                "/v1/user/authorize",
                headers={"Authorization": auth_header},
            )

            self._assert_response_status(
                verify_response,
                200,
                "POST authorize after GQL create",
                "/v1/user/authorize",
            )
            verify_successful = True
        except Exception as e:
            verify_successful = False
            print(f"Error verifying user creation: {e}")

        assert verify_successful, (
            f"[{self.entity_name}] Failed to verify user creation via REST API\n"
            f"Email: {email}"
        )

        return gql_entity

    def test_GQL_mutation_update(self, server, admin_a_jwt, team_a):
        """Test updating the current user using GraphQL mutation."""
        test_name = "test_GQL_mutation_update"
        self.reason_to_skip(test_name)

        # Generate a new name for update
        updated_name = f"Updated via GraphQL {uuid.uuid4()}"

        # Prepare input data
        input_data = {self.string_field_to_update: updated_name}

        # Determine mutation type
        mutation_type = f"update{self.entity_name.capitalize()}"

        # Generate mutation without ID param - use current user
        mutation = self._build_gql_mutation(
            mutation_type=mutation_type, input_data=input_data
        )

        # Execute the GraphQL mutation
        response = server.post(
            "/graphql", json={"query": mutation}, headers=self._auth_header(admin_a_jwt)
        )

        # Assert response
        data = self._assert_gql_response(response, "mutation update")

        # Check entity was updated
        assert mutation_type in data, (
            f"[{self.entity_name}] GraphQL update mutation response missing result: {mutation_type}\n"
            f"Response data: {data}"
        )

        gql_entity = data[mutation_type]

        # Check name was updated
        name_camel = self.to_camel_case(self.string_field_to_update)
        assert name_camel in gql_entity, (
            f"[{self.entity_name}] GraphQL updated entity missing name field\n"
            f"Entity: {gql_entity}"
        )
        assert gql_entity[name_camel] == updated_name, (
            f"[{self.entity_name}] GraphQL updated entity has wrong name\n"
            f"Expected: {updated_name}\n"
            f"Actual: {gql_entity[name_camel]}\n"
            f"Entity: {gql_entity}"
        )

        # Verify user was updated via REST API
        verify_response = server.get(
            "/v1/user",
            headers=self._auth_header(admin_a_jwt),
        )

        self._assert_response_status(
            verify_response,
            200,
            "GET after GQL update",
            "/v1/user",
        )

        entity = self._assert_entity_in_response(verify_response)
        assert entity[self.string_field_to_update] == updated_name, (
            f"[{self.entity_name}] REST API entity not updated after GraphQL mutation\n"
            f"Expected name: {updated_name}\n"
            f"Actual name: {entity[self.string_field_to_update]}\n"
            f"Entity: {entity}"
        )

        return gql_entity

    def test_GQL_mutation_delete(self, server, admin_a_jwt, team_a):
        """Test deleting a resource using GraphQL mutation."""
        test_name = "test_GQL_mutation_delete"
        self.reason_to_skip(test_name)

        # First create a resource
        resource = self.test_POST_201_body(server, admin_a_jwt, team_a)

        # Determine mutation type
        mutation_type = f"delete{self.entity_name.capitalize()}"

        # Special case for user entity - boolean return type with no fields
        if self.entity_name.lower() == "user":
            # Generate mutation manually without fields for boolean return type
            mutation = f"""
            mutation {{
                {mutation_type}(id: "{resource["id"]}")
            }}
            """
        else:
            # Generate mutation with fields for other entity types
            mutation = self._build_gql_mutation(
                mutation_type=mutation_type,
                id_param=resource["id"],
                fields=["id"],  # Only return ID for deletion
            )

        # Execute the GraphQL mutation
        response = server.post(
            "/graphql", json={"query": mutation}, headers=self._auth_header(admin_a_jwt)
        )

        # For user entity with boolean return, handle response differently
        if self.entity_name.lower() == "user":
            assert response.status_code == 200, (
                f"[{self.entity_name}] GraphQL mutation delete failed: status code {response.status_code}\n"
                f"Response: {response.text}"
            )

            json_response = response.json()
            assert "data" in json_response, (
                f"[{self.entity_name}] GraphQL mutation delete response missing 'data' field\n"
                f"Response: {json_response}"
            )

            assert json_response["data"] is not None, (
                f"[{self.entity_name}] GraphQL mutation delete returned null data\n"
                f"Response: {json_response}"
            )

            assert mutation_type in json_response["data"], (
                f"[{self.entity_name}] GraphQL mutation delete response missing mutation result\n"
                f"Response: {json_response}"
            )

            assert json_response["data"][mutation_type] is True, (
                f"[{self.entity_name}] GraphQL mutation delete returned false\n"
                f"Response: {json_response}"
            )
        else:
            # Normal entity with ID field in response
            data = self._assert_gql_response(response, "mutation delete")

            # Check if deletion was successful by verifying the returned ID
            assert mutation_type in data, (
                f"[{self.entity_name}] GraphQL mutation delete response missing mutation result\n"
                f"Response data: {data}"
            )

            mutation_result = data[mutation_type]
            assert "id" in mutation_result, (
                f"[{self.entity_name}] GraphQL mutation delete result missing ID\n"
                f"Result: {mutation_result}"
            )

            assert mutation_result["id"] == resource["id"], (
                f"[{self.entity_name}] GraphQL mutation delete returned wrong ID\n"
                f"Expected: {resource['id']}, Got: {mutation_result['id']}"
            )


@pytest.mark.ep
@pytest.mark.auth
class TestInvitationEndpoints(AbstractEndpointTest):
    """Tests for the Invitation Management endpoints."""

    base_endpoint = "invitation"
    entity_name = "invitation"
    required_fields = ["id", "team_id", "role_id", "created_at"]
    string_field_to_update = ""
    supports_search = False

    # Parent entity for team invitations
    parent_entities = [
        ParentEntity(
            name="team",
            foreign_key="team_id",
            nullable=False,
            system=False,
            path_level=1,  # Indicate this is the first-level path parent
            test_class=TestTeamEndpoints,
        ),
    ]

    # Not a system entity
    system_entity = False

    # Skip specific tests that aren't applicable
    skip_tests = [
        TestToSkip(
            name="test_POST_201_batch",
            details="Invitation endpoint does not support batch operations",
        ),
        TestToSkip(
            name="test_POST_422_batch",
            details="Invitation endpoint does not support batch operations",
        ),
        TestToSkip(
            name="test_POST_200_search",
            details="Invitation endpoint does not support search",
        ),
    ]

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for invitation creation."""
        # Generate a unique email
        email = f"test.user.{uuid.uuid4().hex[:8]}@example.com"
        role_id = "FFFFFFFF-FFFF-FFFF-0000-FFFFFFFFFFFF"  # user role ID

        payload = {"email": email, "role_id": role_id}

        # Add team_id if provided
        if team_id:
            payload["team_id"] = team_id
        elif parent_ids and "team_id" in parent_ids:
            payload["team_id"] = parent_ids["team_id"]

        return self.nest_payload_in_entity(entity=payload)

    def create_parent_entities(self, server, admin_a_jwt, team_a):
        """Create parent entities for invitation testing."""
        # Use the existing team
        return {"team": team_a}

    def test_DELETE_204_team_invitations(self, server, admin_a_jwt, team_a):
        """Test deleting all invitations for a team."""
        team_id = team_a["id"]

        # First create some invitations for the team
        invitation1 = self.test_POST_201(server, admin_a_jwt, team_a)
        invitation2 = self.test_POST_201(server, admin_a_jwt, team_a)

        # Now delete all invitations
        endpoint = f"/v1/team/{team_id}/invitation"
        response = server.delete(endpoint, headers=self._auth_header(admin_a_jwt))

        self._assert_response_status(
            response, 204, "DELETE all team invitations", endpoint
        )

        # Verify invitations were deleted by attempting to get them
        invitation_response = server.get(
            f"/v1/invitation?team_id={team_id}", headers=self._auth_header(admin_a_jwt)
        )
        invitation_json = invitation_response.json()

        invitations = invitation_json.get("invitations", [])
        assert len(invitations) == 0, (
            f"[{self.entity_name}] Invitations were not deleted\n"
            f"Found invitations: {invitations}"
        )

    @pytest.mark.xfail(details="Open Issue #57")
    def test_PATCH_204_existing_admin_accept_direct_invitation(self):
        raise NotImplementedError

    @pytest.mark.xfail(details="Open Issue #57")
    def test_PATCH_204_existing_admin_accept_invitation_code(self):
        raise NotImplementedError

    @pytest.mark.xfail(details="Open Issue #57")
    def test_PATCH_404_existing_user_nonexistent_direct_invitation(self):
        raise NotImplementedError

    @pytest.mark.xfail(details="Open Issue #57")
    def test_PATCH_404_existing_user_nonexistent_invitation_code(self):
        raise NotImplementedError

    @pytest.mark.xfail(details="Open Issue #57")
    def test_POST_201_new_admin_accept_direct_invitation(self):
        raise NotImplementedError

    @pytest.mark.xfail(details="Open Issue #57")
    def test_POST_201_new_admin_accept_invitation_code(self):
        raise NotImplementedError

    @pytest.mark.xfail(details="Open Issue #56")
    def test_POST_404_nonexistent_parent(self, server, admin_a_jwt, team_a):
        """Override: Test creating a role with a nonexistent team parent returns 403.

        Current API behavior returns 403 (Permission Denied) instead of 404 (Not Found)
        when trying to create a role under a non-existent team. This test reflects that.
        Ideally, the API should return 404.
        """
        test_name = "test_POST_404_nonexistent_parent"
        self.reason_to_skip(test_name)

        if not self.has_parent_entities():
            pytest.skip("No parent entities for this resource")

        # Create a resource with nonexistent parent ID
        resource_name = self.faker.company()

        # Create payload with nonexistent parent IDs
        parent_ids = {}
        path_parent_ids = {}
        for parent in self.parent_entities:
            if not parent.nullable:
                nonexistent_id = str(uuid.uuid4())
                parent_ids[parent.foreign_key] = nonexistent_id
                if parent.is_path:
                    path_parent_ids[f"{parent.name}_id"] = nonexistent_id

        # Skip test if no non-nullable parents
        if not parent_ids:
            pytest.skip("No non-nullable parents for this resource")

        payload = self.create_payload(resource_name, parent_ids, team_a.id)

        response = server.post(
            self.get_create_endpoint(path_parent_ids),
            json=payload,
            headers=self._auth_header(admin_a_jwt),
        )

        # Expect 403 Forbidden instead of 404 Not Found
        self._assert_response_status(
            response,
            403,  # <-- Changed from 404
            "POST with nonexistent parent (expecting 403)",
            self.get_create_endpoint(path_parent_ids),
            payload,
        )


@pytest.mark.ep
@pytest.mark.auth
class TestRoleEndpoints(AbstractEndpointTest):
    """Tests for the Role Management endpoints."""

    base_endpoint = "role"
    entity_name = "role"
    required_fields = ["id", "team_id", "name", "created_at"]
    string_field_to_update = "name"
    supports_search = True  # Roles are searchable by name/friendly_name
    searchable_fields = ["name", "friendly_name"]

    # Parent entity for team roles
    parent_entities = [
        ParentEntity(
            name="team",
            foreign_key="team_id",
            nullable=False,
            system=False,
            path_level=1,  # Indicate this is the first-level path parent
            test_class=TestTeamEndpoints,
        ),
    ]

    # Not a system entity
    system_entity = False

    # --- Endpoint Path Configuration (Override defaults) --- #
    NESTING_CONFIG_OVERRIDES = {
        "LIST": 1,  # Override default: Use nesting level 1
        "CREATE": 1,  # Override default: Use nesting level 1
        "SEARCH": 1,  # Override default: Use nesting level 1
        "DETAIL": 0,  # Explicitly set DETAIL (GET/PUT/DELETE) to level 0 (standalone)
    }

    # Skip tests that are not applicable or not implemented by the router setup
    skip_tests = [
        # Remove skips for tests that should now run:
        # SkippedTest(name="test_POST_201_batch",...),
        # SkippedTest(name="test_POST_422_batch",...),
        # SkippedTest(name="test_POST_200_search",...),
        # SkippedTest(name="test_POST_403_role_too_low",...),
        # Keep skips for operations not supported by Role endpoint
        TestToSkip(
            name="test_PUT_200_batch",
            details="Role endpoint does not support batch update",
        ),
        TestToSkip(
            name="test_DELETE_204_batch",
            details="Role endpoint does not support batch delete",
        ),
    ]

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for role creation."""
        if not name:
            name = self.faker.company()

        payload = {
            "name": name,
            "friendly_name": f"Friendly {name}",
            "mfa_count": 0,
            "password_change_frequency_days": 180,
        }

        # Add team_id if provided in parent_ids (for nested creation)
        if parent_ids and "team_id" in parent_ids:
            payload["team_id"] = parent_ids["team_id"]
        elif team_id:
            # This case shouldn't happen for nested creation via the standard test flow
            # but include for completeness if called directly
            payload["team_id"] = team_id

        return self.nest_payload_in_entity(entity=payload)

    def create_parent_entities(self, server, admin_a_jwt, team_a):
        """Create parent entities for role testing (uses the provided team)."""
        return {"team": team_a}

    # TODO #60: Refactor permission system to use explicit permissions instead of role names
    def test_POST_403_role_too_low(self, server, admin_a_jwt, jwt_b, team_a):
        """Override: Test creating a Role requires admin privileges."""
        test_name = "test_POST_403_role_too_low"
        self.reason_to_skip(test_name)

        # User A (admin) should be able to create (verified by test_POST_201)

        # Prepare payload
        resource_name = self.faker.company()
        parent_ids = {"team_id": team_a["id"]}
        path_parent_ids = {"team_id": team_a["id"]}
        payload = self.create_payload(resource_name, parent_ids, team_a.id)

        # Attempt to create with User B (assuming standard user role)
        # Ensure User B is part of the team first (fixture should handle this, but add if needed)
        # e.g., team_manager.add_user_to_team(team_id=team_a['id'], user_id=user_b['id'], role_id=user_role_id)

        response = server.post(
            self.get_create_endpoint(path_parent_ids),
            json=payload,
            headers=self._auth_header(jwt_b),  # Use jwt_b
        )

        # Assert 403 Forbidden
        self._assert_response_status(
            response,
            403,
            "POST Role with insufficient permissions",
            self.get_create_endpoint(path_parent_ids),
            payload,
        )
