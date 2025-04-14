import base64
import secrets
import uuid

import pytest

from endpoints.AbstractEPTest import AbstractEndpointTest, ParentEntity, SkippedTest
from helptest import generate_secure_password, generate_test_email


@pytest.mark.ep
@pytest.mark.auth
class TestTeamEndpoints(AbstractEndpointTest):
    """Tests for the Team Management endpoints."""

    base_endpoint = "team"
    entity_name = "team"
    required_fields = ["id", "name", "created_at"]
    string_field_to_update = "name"
    supports_search = True
    searchable_fields = ["name", "description"]

    # No parent entities for teams
    parent_entities = []

    # Not a system entity
    system_entity = False

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for team creation."""
        if not name:
            name = self.generate_name()

        payload = {"name": name, "description": f"Description for {name}"}

        # team_id parameter is ignored for teams since they are top-level resources

        return self.nest_payload_in_entity(entity=payload)

    def test_PUT_200_update_user_role(self, server, jwt_a, team_a):
        """Test updating a user's role in a team."""
        # First get the team members to find a user to update
        team_id = team_a["id"]

        # Get team users
        users = self.test_GET_200_team_users(server, jwt_a, team_a)

        if not users:
            pytest.skip("No users found in team to update role")

        user_id = users[0]["id"]

        # Update the user's role
        role_id = "FFFFFFFF-FFFF-FFFF-AAAA-FFFFFFFFFFFF"  # admin role

        update_endpoint = f"/v1/team/{team_id}/user/{user_id}/role"
        update_payload = {"role_id": role_id}

        update_response = server.put(
            update_endpoint, json=update_payload, headers=self._auth_header(jwt_a)
        )

        self._assert_response_status(
            update_response,
            200,
            "PUT update user role",
            update_endpoint,
            update_payload,
        )

        # The endpoint returns a message
        assert "message" in update_response.json(), (
            f"[{self.entity_name}] Message not found in update role response\n"
            f"Response: {update_response.json()}"
        )

        # Verify the role was updated by getting the team members again
        endpoint = f"/v1/team/{team_id}/user"
        verify_response = server.get(endpoint, headers=self._auth_header(jwt_a))

        self._assert_response_status(
            verify_response, 200, "GET team users after role update", endpoint
        )
        verify_json = verify_response.json()

        # Return the response, full verification would require checking roles
        # which may be beyond the scope of this test
        return verify_json

    def test_DELETE_204_team_invitations(self, server, jwt_a, team_a):
        """Test deleting all invitations for a team."""
        team_id = team_a["id"]

        # First create some invitations for the team
        invitation_test = TestInvitationEndpoints()
        invitation1 = invitation_test.test_POST_201(server, jwt_a, team_a)
        invitation2 = invitation_test.test_POST_201(server, jwt_a, team_a)

        # Now delete all invitations
        endpoint = f"/v1/team/{team_id}/invitation"
        response = server.delete(endpoint, headers=self._auth_header(jwt_a))

        self._assert_response_status(
            response, 200, "DELETE all team invitations", endpoint
        )

        json_response = response.json()
        assert "message" in json_response, (
            f"[{self.entity_name}] Message not found in delete response\n"
            f"Response: {json_response}"
        )
        assert "count" in json_response, (
            f"[{self.entity_name}] Count not found in delete response\n"
            f"Response: {json_response}"
        )

        # Verify invitations were deleted by attempting to get them
        invitation_response = server.get(
            f"/v1/invitation?team_id={team_id}", headers=self._auth_header(jwt_a)
        )
        invitation_json = invitation_response.json()

        invitations = invitation_json.get("invitations", [])
        assert len(invitations) == 0, (
            f"[{self.entity_name}] Invitations were not deleted\n"
            f"Found invitations: {invitations}"
        )

        return json_response


@pytest.mark.ep
@pytest.mark.auth
class TestUserEndpoints(AbstractEndpointTest):
    """Tests for the User Management endpoints."""

    base_endpoint = "user"
    entity_name = "user"
    required_fields = ["id", "email", "display_name", "created_at"]
    string_field_to_update = "display_name"
    supports_search = True
    searchable_fields = ["email", "display_name", "first_name", "last_name"]

    # No parent entities for users
    parent_entities = []

    # Not a system entity
    system_entity = False

    skip_tests = [
        SkippedTest(
            name="test_GET_200_id", reason="Getting Users by ID is unsupported."
        ),
        SkippedTest(
            name="test_GET_200_list", reason="Listing of Users is unsupported."
        ),
        SkippedTest(
            name="test_POST_201_batch",
            reason="User endpoint does not support batch operations",
        ),
        SkippedTest(
            name="test_POST_422_batch",
            reason="User endpoint does not support batch operations",
        ),
        SkippedTest(
            name="test_DELETE_404_other_user",
            reason="User deletion not implemented in standard tests",
        ),
        SkippedTest(
            name="test_DELETE_404_nonexistent",
            reason="User deletion not implemented in standard tests",
        ),
        SkippedTest(
            name="test_GET_200_pagination",
            reason="User endpoint does not support multiple users.",
        ),
        SkippedTest(
            name="test_PUT_200_batch",
            reason="User endpoint does not support batch operations",
        ),
        SkippedTest(
            name="test_DELETE_204_batch",
            reason="User endpoint does not support batch operations",
        ),
        SkippedTest(
            name="test_POST_200_search",
            reason="User endpoint does not support search",
        ),
        SkippedTest(
            name="test_PUT_404_other_user",
            reason="User endpoint does not support update by ID",
        ),
        SkippedTest(
            name="test_PUT_404_nonexistent",
            reason="User endpoint does not support update by ID",
        ),
        SkippedTest(
            name="test_GET_404_other_user",
            reason="User endpoint does not support update by ID",
        ),
        SkippedTest(
            name="test_GET_404_nonexistent",
            reason="User endpoint does not support update by ID",
        ),
        SkippedTest(
            name="test_POST_401",
            reason="User creation can be done entirely with body.",
        ),
        SkippedTest(
            name="test_DELETE_204",
            reason="Endpoint not implemented.",  # TODO Implement a self-deletion endpoint for users. This isn't high priority. Test override commented out below.
        ),
    ]

    def _setup_test_resources(self, server, jwt_token, team, count=1, api_key=None):
        """Set up test resources for user tests.

        Args:
            server: Test server fixture
            jwt_token: JWT token for authentication
            team: Team information
            count: Number of resources to create
            api_key: Optional API key for system entities

        Returns:
            list: A list of tuples (resource, parent_ids, path_parent_ids, headers)
        """
        resources = []
        results = []

        for i in range(count):
            resource = self.test_POST_201(server, jwt_token, team, api_key)
            resources.append(resource)

            # Empty dictionaries since users don't have parent entities
            parent_ids = {}
            path_parent_ids = {}

            # Get appropriate headers
            headers = self._get_appropriate_headers(jwt_token, api_key)

            results.append((resource, parent_ids, path_parent_ids, headers))

        return results

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for user creation."""
        email = generate_test_email()
        password = generate_secure_password()

        if not name:
            name = f"Test User {uuid.uuid4()}"

        payload = {
            "email": email,
            "display_name": name,
            "first_name": "Test",
            "last_name": "User",
            "password": password,
        }

        # Store password for later authentication tests
        self._last_password = password

        # team_id parameter is ignored for users

        return self.nest_payload_in_entity(entity=payload)

    def test_POST_201(self, server, jwt_a=None, team_a=None, api_key=None):
        """Test user registration."""
        # Generate a unique email and secure password
        email = generate_test_email()
        password = generate_secure_password()
        display_name = f"Test User {uuid.uuid4()}"

        # Create the payload
        payload = self.nest_payload_in_entity(
            entity={
                "email": email,
                "display_name": display_name,
                "first_name": "Test",
                "last_name": "User",
                "password": password,
            }
        )

        # Register using the POST to /v1/user endpoint - no auth required
        response = server.post("/v1/user", json=payload)

        self._assert_response_status(
            response, 201, "POST create user", "/v1/user", payload
        )

        user = self._assert_entity_in_response(response)

        # Store credentials for login tests
        user["_test_password"] = password

        return user

    def test_POST_200_authorize(self, server, user_a):
        """Test user login with basic auth."""
        # Extract stored password or use default if not available
        password = user_a.get("_test_password", "Password1!")

        auth_string = f"{user_a['email']}:{password}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        auth_header = f"Basic {encoded_auth}"

        response = server.post(
            "/v1/user/authorize",
            headers={"Authorization": auth_header},
        )

        self._assert_response_status(
            response, 200, "POST authorize", "/v1/user/authorize"
        )

        # Extract token from login response
        login_data = response.json()
        token = login_data.get("token")
        assert token, "Token missing in login response"

        return token

    def test_GET_200(self, server, jwt_a):
        """Test retrieving the current user's details."""
        response = server.get("/v1/user", headers=self._auth_header(jwt_a))

        self._assert_response_status(response, 200, "GET current user", "/v1/user")

        user = self._assert_entity_in_response(response)

        # Verify required fields
        for field in self.required_fields:
            assert field in user, f"Required field {field} missing in user response"

        return user

    def test_PUT_200(self, server, jwt_a):
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
            "/v1/user", json=update_payload, headers=self._auth_header(jwt_a)
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
        verify_response = server.get("/v1/user", headers=self._auth_header(jwt_a))
        self._assert_response_status(
            verify_response, 200, "GET after update", "/v1/user"
        )

        verified_user = self._assert_entity_in_response(verify_response)
        assert verified_user["display_name"] == display_name, "Update not persisted"

        return updated_user

    # def test_DELETE_204(self, server, jwt_a):
    #     """Test delete the current user's profile."""
    #     # First get the current user profile to confirm it exists
    #     initial_response = server.get("/v1/user", headers=self._auth_header(jwt_a))
    #     self._assert_response_status(
    #         initial_response, 200, "GET current user", "/v1/user"
    #     )

    #     initial_user = self._assert_entity_in_response(initial_response)

    #     # Now delete the user
    #     delete_response = server.delete("/v1/user", headers=self._auth_header(jwt_a))

    #     self._assert_response_status(
    #         delete_response, 204, "DELETE current user", "/v1/user"
    #     )

    #     # Verify user is deleted by trying to get the profile again
    #     # which should fail with 401 since the user no longer exists
    #     verify_response = server.get("/v1/user", headers=self._auth_header(jwt_a))
    #     self._assert_response_status(
    #         verify_response, 401, "GET after deletion", "/v1/user"
    #     )

    #     # The JWT should be invalidated
    #     assert "detail" in verify_response.json(), "Expected error detail in response"

    #     return True

    def test_PATCH_200_password(self, server, jwt_a):
        """Test changing a user's password."""
        # Create a new user
        new_user = self.test_POST_201(server)

        # Login to get JWT
        new_user_jwt = self.test_POST_200_authorize(server, new_user)

        # Extract the old password
        old_password = new_user["_test_password"]
        new_password = generate_secure_password()

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

    def test_GET_200_verify_jwt(self, server, jwt_a):
        """Test verifying authorization token."""
        response = server.get("/v1", headers=self._auth_header(jwt_a))

        self._assert_response_status(response, 204, "GET verify authorization", "/v1")

        # Response should be empty with 204 status
        assert response.content == b"", "Response body should be empty"

        return True

    def test_GET_401_verify_jwt_empty(self, server):
        """Test verifying with an empty authorization header."""
        # No authorization header
        response = server.get("/v1")

        # TODO This should be a 401 but FastAPI returns a 422, needs back end change but non-urgent.
        self._assert_response_status(response, 422, "GET verify authorization", "/v1")

        # Verify the error message includes "Field required" for the authorization header
        assert (
            "Field required" in response.text
        ), "Expected validation error about missing header"
        assert "header" in response.text, "Expected validation error to mention header"
        assert (
            "authorization" in response.text
        ), "Expected validation error to mention authorization"

        return True

    def test_GET_401_verify_jwt_invalid_token(self, server, jwt_a):
        """Test verifying with an invalid authorization token."""
        # Create an invalid JWT by replacing all numbers with 'x'
        invalid_jwt = "".join(["x" if c.isdigit() else c for c in jwt_a])

        # Use the invalid JWT
        response = server.get("/v1", headers={"Authorization": f"Bearer {invalid_jwt}"})

        self._assert_response_status(response, 401, "GET verify authorization", "/v1")

        # Verify the error message
        assert (
            "Token verification failed" in response.text
        ), "Expected error about token verification failure"

        return True

    def test_GET_401_verify_jwt_invalid_signature(self, server, jwt_a):
        """Test verifying with an invalid JWT signature."""
        # Split the JWT into its 3 parts
        jwt_parts = jwt_a.split(".")

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
        self.should_skip_test(test_name)

        # Only test accessing the user profile endpoint without authentication
        response = server.get("/v1/user")
        self._assert_response_status(response, 401, "GET unauthorized", "/v1/user")

    # def test_GET_200_fields(self, server, jwt_a, team_a):
    #     """Test retrieving resources with the fields parameter."""
    #     test_name = "test_GET_200_fields"
    #     self.should_skip_test(test_name)

    #     # Create a resource
    #     resource, parent_ids, path_parent_ids, headers = self._setup_test_resources(
    #         server, jwt_a, team_a, count=1
    #     )[0]

    #     # Select a subset of fields
    #     subset_fields = self.required_fields[
    #         :2
    #     ]  # Just use the first two required fields
    #     fields_param = f"?{'&'.join([f'fields={field}' for field in subset_fields])}"

    #     # For user endpoint, we don't use the ID since it's a non-standard implementation
    #     # that returns the current user rather than a specific user by ID
    #     endpoint = f"/v1/user{fields_param}"

    #     # Test with single entity endpoint
    #     response = server.get(
    #         endpoint,
    #         headers=headers,
    #     )

    #     self._assert_response_status(
    #         response, 200, "GET with fields parameter", endpoint
    #     )

    #     # Parse response
    #     user = self._assert_entity_in_response(response)

    #     # Verify only requested fields are returned (plus 'id' which is always returned)
    #     for field in self.required_fields:
    #         if field in subset_fields or field == "id":
    #             assert field in user, f"Requested field {field} missing in response"
    #         else:
    #             assert field not in user, f"Non-requested field {field} in response"

    #     return user

    def test_GQL_query_single(self, server, jwt_a, team_a):
        """Test retrieving the current user using GraphQL."""
        test_name = "test_GQL_query_single"
        self.should_skip_test(test_name)

        # For users, we query the current user
        resource_type = self.entity_name.lower()

        # Generate query without ID param since we want the current user
        query = self._build_gql_query(query_type=resource_type)

        # Execute the GraphQL query
        response = server.post(
            "/graphql", json={"query": query}, headers=self._auth_header(jwt_a)
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

    def test_GQL_query_list(self, server, jwt_a, team_a):
        """Test retrieving a list containing only the current user using GraphQL."""
        test_name = "test_GQL_query_list"
        self.should_skip_test(test_name)

        # Determine the GraphQL query for users plural
        resource_type_plural = self.resource_name_plural.lower()

        # Generate query for users list
        query = self._build_gql_query(query_type=resource_type_plural)

        # Execute the GraphQL query
        response = server.post(
            "/graphql", json={"query": query}, headers=self._auth_header(jwt_a)
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

    def test_GQL_query_filter(self, server, jwt_a, team_a):
        """Test filtering users using GraphQL."""
        test_name = "test_GQL_query_filter"
        self.should_skip_test(test_name)

        # First get the current user
        user_response = server.get("/v1/user", headers=self._auth_header(jwt_a))
        self._assert_response_status(user_response, 200, "GET user", "/v1/user")
        user = self._assert_entity_in_response(user_response)

        # Update the user to have a unique filter term
        filter_term = f"Filterable {self.entity_name} {uuid.uuid4()}"
        update_payload = self.nest_payload_in_entity(
            entity={self.string_field_to_update: filter_term}
        )

        # Update the current user
        update_response = server.put(
            "/v1/user", json=update_payload, headers=self._auth_header(jwt_a)
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
            "/graphql", json={"query": query}, headers=self._auth_header(jwt_a)
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

    def test_GQL_mutation_create(self, server, jwt_a, team_a):
        """Test creating a user using GraphQL mutation."""
        test_name = "test_GQL_mutation_create"
        self.should_skip_test(test_name)

        # Generate a unique name for the test user
        resource_name = self.generate_name()
        email = generate_test_email()
        password = generate_secure_password()

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

    def test_GQL_mutation_update(self, server, jwt_a, team_a):
        """Test updating the current user using GraphQL mutation."""
        test_name = "test_GQL_mutation_update"
        self.should_skip_test(test_name)

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
            "/graphql", json={"query": mutation}, headers=self._auth_header(jwt_a)
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
            headers=self._auth_header(jwt_a),
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

    def test_GQL_mutation_delete(self, server, jwt_a, team_a):
        """Test deleting a resource using GraphQL mutation."""
        test_name = "test_GQL_mutation_delete"
        self.should_skip_test(test_name)

        # First create a resource
        resource = self.test_POST_201(server, jwt_a, team_a)

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
            "/graphql", json={"query": mutation}, headers=self._auth_header(jwt_a)
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
    string_field_to_update = "code"  # Invitation doesn't have a name field
    supports_search = False

    # Parent entity for team invitations
    parent_entities = [
        ParentEntity(
            name="team",
            key="team_id",
            nullable=False,
            system=False,
            is_path=False,
        ),
    ]

    # Not a system entity
    system_entity = False

    # Skip specific tests that aren't applicable
    skip_tests = [
        {
            "name": "test_POST_201_batch",
            "reason": "Invitation endpoint does not support batch operations",
        },
        {
            "name": "test_POST_422_batch",
            "reason": "Invitation endpoint does not support batch operations",
        },
        {
            "name": "test_POST_200_search",
            "reason": "Invitation endpoint does not support search",
        },
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

    def create_parent_entities(self, server, jwt_a, team_a):
        """Create parent entities for invitation testing."""
        # Use the existing team
        return {"team": team_a}

    def test_POST_200_add_invitee(self, server, jwt_a, team_a):
        """Test adding an invitee to an invitation."""
        # First create an invitation
        invitation = self.test_POST_201(server, jwt_a, team_a)

        # Add invitee email
        email = f"new.invitee.{uuid.uuid4().hex[:8]}@example.com"
        payload = {"email": email}

        response = server.post(
            f"/v1/invitation/{invitation['id']}/add-invitee",
            json=payload,
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response,
            200,
            "POST add invitee",
            f"/v1/invitation/{invitation['id']}/add-invitee",
            payload,
        )

        result = response.json()
        assert "invitation_id" in result, "Missing invitation_id in response"
        assert "email" in result, "Missing email in response"
        assert result["email"] == email, "Email mismatch in response"

        return result


@pytest.mark.ep
@pytest.mark.auth
class TestSessionEndpoints(AbstractEndpointTest):
    """Tests for the User Session endpoints."""

    base_endpoint = "session"
    entity_name = "user_session"
    required_fields = ["id", "user_id", "session_key", "created_at"]

    # Parent entities
    parent_entities = [
        ParentEntity(
            name="user",
            key="user_id",
            nullable=False,
            system=False,
            is_path=False,
        ),
    ]

    def create_parent_entities(self, server, jwt_a, team_a):
        """Create parent entities for session testing."""
        # Get current user
        user_response = server.get("/v1/user/me", headers=self._auth_header(jwt_a))
        user = user_response.json()["user"]

        return {"user": user}

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for session creation."""
        from datetime import datetime, timedelta

        session_key = secrets.token_hex(16)
        now = datetime.utcnow()
        expires = now + timedelta(days=1)

        payload = {
            "session_key": session_key,
            "jwt_issued_at": now.isoformat(),
            "last_activity": now.isoformat(),
            "expires_at": expires.isoformat(),
            "device_type": "web",
            "browser": "test_browser",
        }

        if parent_ids and "user_id" in parent_ids:
            payload["user_id"] = parent_ids["user_id"]

        return self.nest_payload_in_entity(entity=payload)

    def test_POST_200_revoke_session(self, server, jwt_a, team_a):
        """Test revoking a user session."""
        # First create a session
        session = self.test_POST_201(server, jwt_a, team_a)

        response = server.post(
            f"/v1/session/{session['id']}/revoke", headers=self._auth_header(jwt_a)
        )

        self._assert_response_status(
            response, 200, "POST revoke session", f"/v1/session/{session['id']}/revoke"
        )

        result = response.json()
        assert "message" in result, "Missing message in response"

        # Verify session is revoked
        get_response = server.get(
            f"/v1/session/{session['id']}", headers=self._auth_header(jwt_a)
        )

        session = self._assert_entity_in_response(get_response)
        assert session["revoked"] == True, "Session not marked as revoked"

        return result

    def test_DELETE_204_revoke_all_sessions(self, server, jwt_a, team_a):
        """Test revoking all user sessions."""
        # Get current user
        user_response = server.get("/v1/user/me", headers=self._auth_header(jwt_a))
        user_id = user_response.json()["user"]["id"]

        # Create a couple of sessions
        self.test_POST_201(server, jwt_a, team_a)
        self.test_POST_201(server, jwt_a, team_a)

        # Revoke all sessions
        response = server.delete(
            f"/v1/user/{user_id}/session",
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response, 204, "DELETE revoke all sessions", f"/v1/user/{user_id}/session"
        )

        # Verify sessions are revoked by checking that there are no active sessions
        sessions_response = server.get(
            f"/v1/user/{user_id}/session?revoked=false",
            headers=self._auth_header(jwt_a),
        )

        sessions = sessions_response.json().get("user_sessions", [])
        assert len(sessions) == 0, "Not all sessions were revoked"

        return True
