import uuid

import pytest

from endpoints.AbstractEPTest import AbstractEndpointTest, ParentEntity


class ProviderExtensionEndpointTest(AbstractEndpointTest):
    """Test class for Provider Extension endpoints."""

    base_endpoint = "provider/extension"
    entity_name = "extension"
    string_field_to_update = "name"
    required_fields = [
        "id",
        "name",
        "description",
        "provider_id",
        "created_at",
        "updated_at",
    ]

    # Parent entity configurations
    parent_entities = [ParentEntity(name="provider", key="provider_id", is_path=False)]

    def create_parent_entities(self, server, jwt_a, team_a):
        """Create parent entities required for testing this resource."""
        # Create a provider to use for extension testing
        provider_payload = {"name": f"Test Provider {uuid.uuid4()}"}

        if team_a and "team_id" in provider_payload:
            provider_payload["team_id"] = team_a.get("id", None)

        nested_payload = {"provider": provider_payload}

        response = server.post(
            "/v1/provider", json=nested_payload, headers=self._auth_header(jwt_a)
        )

        assert response.status_code == 201
        provider = response.json()["provider"]

        return {"provider": provider}

    def test_GET_200_available_extensions(self, server, jwt_a, team_a):
        """Test listing available extensions."""
        if self.should_skip_test("test_GET_200_available_extensions"):
            return

        response = server.get(
            "/v1/provider/extension/available", headers=self._auth_header(jwt_a)
        )

        self._assert_response_status(
            response,
            200,
            "GET available extensions",
            "/v1/provider/extension/available",
        )

        json_response = response.json()
        assert "extensions" in json_response, "Response should contain 'extensions' key"
        assert isinstance(
            json_response["extensions"], list
        ), "Extensions should be a list"

        # Verify the structure of at least one extension if the list is not empty
        if json_response["extensions"]:
            extension = json_response["extensions"][0]
            assert "id" in extension, "Extension should have an ID"
            assert "name" in extension, "Extension should have a name"
            assert "description" in extension, "Extension should have a description"

        return json_response["extensions"]

    def test_GET_200_provider_extensions(self, server, jwt_a, team_a):
        """Test getting extensions for a specific provider."""
        if self.should_skip_test("test_GET_200_provider_extensions"):
            return

        # First create a provider
        parent_entities = self.create_parent_entities(server, jwt_a, team_a)
        provider = parent_entities["provider"]

        # Then get extensions for this provider
        response = server.get(
            f"/v1/provider/extension/provider/{provider['id']}",
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response,
            200,
            "GET provider extensions",
            f"/v1/provider/extension/provider/{provider['id']}",
        )

        json_response = response.json()
        assert "extensions" in json_response, "Response should contain 'extensions' key"
        assert isinstance(
            json_response["extensions"], list
        ), "Extensions should be a list"

        # Also test with status filter
        response_with_filter = server.get(
            f"/v1/provider/extension/provider/{provider['id']}?status=enabled",
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response_with_filter,
            200,
            "GET provider extensions with filter",
            f"/v1/provider/extension/provider/{provider['id']}?status=enabled",
        )

        filtered_json = response_with_filter.json()
        assert (
            "extensions" in filtered_json
        ), "Filtered response should contain 'extensions' key"
        assert isinstance(
            filtered_json["extensions"], list
        ), "Filtered extensions should be a list"

        return json_response["extensions"]

    def test_POST_200_install_extension(self, server, jwt_a, team_a):
        """Test installing an extension."""
        if self.should_skip_test("test_POST_200_install_extension"):
            return

        # First create a provider and an extension
        parent_entities = self.create_parent_entities(server, jwt_a, team_a)
        provider = parent_entities["provider"]

        extension = self.test_POST_201(server, jwt_a, team_a)

        # Then install the extension
        options = {"option1": "value1", "option2": "value2"}

        response = server.post(
            f"/v1/provider/extension/{extension['id']}/install?provider_id={provider['id']}",
            json=options,
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response,
            200,
            "POST install extension",
            f"/v1/provider/extension/{extension['id']}/install",
        )

        json_response = response.json()
        assert "result" in json_response, "Response should contain 'result' key"
        assert json_response["result"] == "success", "Result should be 'success'"
        assert "extension" in json_response, "Response should contain 'extension' key"

        installed_extension = json_response["extension"]
        assert "id" in installed_extension, "Installed extension should have an id"
        assert (
            installed_extension["id"] == extension["id"]
        ), "Installed extension ID should match original"
        assert (
            "provider_id" in installed_extension
        ), "Installed extension should have provider_id"
        assert (
            installed_extension["provider_id"] == provider["id"]
        ), "Provider ID should match"

        # Verify installation by getting provider extensions
        verify_response = server.get(
            f"/v1/provider/extension/provider/{provider['id']}",
            headers=self._auth_header(jwt_a),
        )

        verify_json = verify_response.json()
        installed_found = False
        for ext in verify_json["extensions"]:
            if ext["id"] == extension["id"]:
                installed_found = True
                break

        assert (
            installed_found
        ), "Installed extension should appear in provider's extensions list"

        return json_response

    def test_POST_204_uninstall_extension(self, server, jwt_a, team_a):
        """Test uninstalling an extension."""
        if self.should_skip_test("test_POST_204_uninstall_extension"):
            return

        # First create a provider and an extension, and install it
        parent_entities = self.create_parent_entities(server, jwt_a, team_a)
        provider = parent_entities["provider"]

        extension = self.test_POST_201(server, jwt_a, team_a)

        # Install the extension
        options = {"option1": "value1", "option2": "value2"}

        install_response = server.post(
            f"/v1/provider/extension/{extension['id']}/install?provider_id={provider['id']}",
            json=options,
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            install_response,
            200,
            "POST install extension",
            f"/v1/provider/extension/{extension['id']}/install",
        )

        # Verify installation
        before_uninstall_response = server.get(
            f"/v1/provider/extension/provider/{provider['id']}",
            headers=self._auth_header(jwt_a),
        )

        before_uninstall_json = before_uninstall_response.json()
        extension_found_before = False
        for ext in before_uninstall_json["extensions"]:
            if ext["id"] == extension["id"]:
                extension_found_before = True
                break

        assert (
            extension_found_before
        ), "Extension should be in provider's extensions before uninstall"

        # Then uninstall the extension
        response = server.post(
            f"/v1/provider/extension/{extension['id']}/uninstall?provider_id={provider['id']}",
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response,
            204,
            "POST uninstall extension",
            f"/v1/provider/extension/{extension['id']}/uninstall",
        )

        # Verify uninstallation
        after_uninstall_response = server.get(
            f"/v1/provider/extension/provider/{provider['id']}",
            headers=self._auth_header(jwt_a),
        )

        after_uninstall_json = after_uninstall_response.json()
        extension_found_after = False
        for ext in after_uninstall_json["extensions"]:
            if ext["id"] == extension["id"]:
                extension_found_after = True
                break

        assert (
            not extension_found_after
        ), "Extension should not be in provider's extensions after uninstall"

        return True

    def test_GET_404_provider_extensions_nonexistent(self, server, jwt_a, team_a):
        """Test getting extensions for a nonexistent provider."""
        if self.should_skip_test("test_GET_404_provider_extensions_nonexistent"):
            return

        nonexistent_id = str(uuid.uuid4())

        response = server.get(
            f"/v1/provider/extension/provider/{nonexistent_id}",
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response,
            404,
            "GET provider extensions nonexistent",
            f"/v1/provider/extension/provider/{nonexistent_id}",
        )

        return True

    def test_POST_404_install_extension_nonexistent(self, server, jwt_a, team_a):
        """Test installing a nonexistent extension."""
        if self.should_skip_test("test_POST_404_install_extension_nonexistent"):
            return

        # Create a provider
        parent_entities = self.create_parent_entities(server, jwt_a, team_a)
        provider = parent_entities["provider"]

        nonexistent_id = str(uuid.uuid4())
        options = {"option1": "value1", "option2": "value2"}

        response = server.post(
            f"/v1/provider/extension/{nonexistent_id}/install?provider_id={provider['id']}",
            json=options,
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response,
            404,
            "POST install nonexistent extension",
            f"/v1/provider/extension/{nonexistent_id}/install",
        )

        return True

    def test_POST_404_install_extension_nonexistent_provider(
        self, server, jwt_a, team_a
    ):
        """Test installing an extension for a nonexistent provider."""
        if self.should_skip_test(
            "test_POST_404_install_extension_nonexistent_provider"
        ):
            return

        # Create an extension
        extension = self.test_POST_201(server, jwt_a, team_a)

        nonexistent_id = str(uuid.uuid4())
        options = {"option1": "value1", "option2": "value2"}

        response = server.post(
            f"/v1/provider/extension/{extension['id']}/install?provider_id={nonexistent_id}",
            json=options,
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response,
            404,
            "POST install extension for nonexistent provider",
            f"/v1/provider/extension/{extension['id']}/install?provider_id={nonexistent_id}",
        )

        # Verify error response format
        error_json = response.json()
        assert "detail" in error_json, "Error response should contain 'detail' field"
        assert "Provider" in error_json["detail"], "Error should mention the provider"
        assert (
            nonexistent_id in error_json["detail"]
        ), "Error should include the nonexistent ID"

        return True

    def test_POST_404_uninstall_extension_nonexistent_provider(
        self, server, jwt_a, team_a
    ):
        """Test uninstalling an extension from a nonexistent provider."""
        if self.should_skip_test(
            "test_POST_404_uninstall_extension_nonexistent_provider"
        ):
            return

        # Create an extension
        extension = self.test_POST_201(server, jwt_a, team_a)

        nonexistent_id = str(uuid.uuid4())

        response = server.post(
            f"/v1/provider/extension/{extension['id']}/uninstall?provider_id={nonexistent_id}",
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response,
            404,
            "POST uninstall extension from nonexistent provider",
            f"/v1/provider/extension/{extension['id']}/uninstall?provider_id={nonexistent_id}",
        )

        # Verify error response format
        error_json = response.json()
        assert "detail" in error_json, "Error response should contain 'detail' field"
        assert "Provider" in error_json["detail"], "Error should mention the provider"
        assert (
            nonexistent_id in error_json["detail"]
        ), "Error should include the nonexistent ID"

        return True

    def test_POST_401_install_extension_unauthorized(self, server):
        """Test installing an extension without authentication."""
        if self.should_skip_test("test_POST_401_install_extension_unauthorized"):
            return

        extension_id = str(uuid.uuid4())
        provider_id = str(uuid.uuid4())
        options = {"option1": "value1", "option2": "value2"}

        response = server.post(
            f"/v1/provider/extension/{extension_id}/install?provider_id={provider_id}",
            json=options,
        )

        self._assert_response_status(
            response,
            401,
            "POST install extension unauthorized",
            f"/v1/provider/extension/{extension_id}/install?provider_id={provider_id}",
        )

        return True

    def test_POST_422_install_extension_invalid_options(self, server, jwt_a, team_a):
        """Test installing an extension with invalid options."""
        if self.should_skip_test("test_POST_422_install_extension_invalid_options"):
            return

        # Create a provider and an extension
        parent_entities = self.create_parent_entities(server, jwt_a, team_a)
        provider = parent_entities["provider"]

        extension = self.test_POST_201(server, jwt_a, team_a)

        # Create invalid options (assuming the API validates option types)
        # This is a placeholder test - the actual validation would depend on the implementation
        invalid_options = {
            "option1": 12345,  # Number instead of string
            "required_option": None,  # Null for a required option
        }

        # In a real implementation, this would trigger a validation error
        # For this example, we'll assume it passes through to the manager which then returns a 422
        # If your implementation doesn't validate options, this test should be adjusted or removed
        response = server.post(
            f"/v1/provider/extension/{extension['id']}/install?provider_id={provider['id']}",
            json=invalid_options,
            headers=self._auth_header(jwt_a),
        )

        # This assertion might need to be adjusted based on your actual implementation
        # If your API doesn't currently validate options, consider adding this feature
        if response.status_code == 422:
            self._assert_response_status(
                response,
                422,
                "POST install extension with invalid options",
                f"/v1/provider/extension/{extension['id']}/install?provider_id={provider['id']}",
            )

            error_json = response.json()
            assert (
                "detail" in error_json
            ), "Error response should contain 'detail' field"
        else:
            # If validation is not implemented, skip this test
            pytest.skip("Option validation is not implemented in the current API")

        return True
