import uuid

import pytest

from endpoints.AbstractEPTest import AbstractEndpointTest, ParentEntity, SkippedTest


@pytest.mark.ep
@pytest.mark.providers
class TestProviderEndpoints(AbstractEndpointTest):
    """Tests for the Provider Management endpoints."""

    base_endpoint = "provider"
    entity_name = "provider"
    required_fields = ["id", "name", "created_at"]
    string_field_to_update = "name"

    # No parent entities for providers
    parent_entities = []

    # Provider is a system entity - requires API key
    system_entity = True

    # Tests to skip
    skip_tests = [
        SkippedTest(
            name="test_GET_404_other_user",
            reason="Users can access all providers - they are global resources.",
        ),
        SkippedTest(name="test_PUT_404_other_user", reason="See test_PUT_403_system"),
        SkippedTest(
            name="test_DELETE_404_other_user", reason="See test_DELETE_403_system"
        ),
    ]

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for provider creation."""
        payload = {
            "name": name or self.generate_name(),
            "agent_settings_json": '{"api_base": "https://api.example.com"}',
        }
        return self.nest_payload_in_entity(payload)


@pytest.mark.ep
@pytest.mark.providers
class TestProviderExtensionEndpoints(AbstractEndpointTest):
    """Tests for the Provider Extension Management endpoints."""

    base_endpoint = "provider/extension"
    entity_name = "extension"
    required_fields = ["id", "name", "created_at"]
    string_field_to_update = "name"

    # No parent entities for provider extensions
    parent_entities = []

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for provider extension creation."""
        payload = {
            "name": name or self.generate_name(),
            "description": f"Test extension {uuid.uuid4()}",
            "version": "1.0.0",
            "entry_point": "test_extension.py",
        }

        if team_id:
            payload["team_id"] = team_id

        return self.nest_payload_in_entity(payload)


@pytest.mark.ep
@pytest.mark.providers
class TestProviderInstanceEndpoints(AbstractEndpointTest):
    """Tests for the Provider Instance Management endpoints."""

    base_endpoint = "provider-instance"
    entity_name = "provider_instance"
    required_fields = ["id", "name", "provider_id", "created_at"]
    string_field_to_update = "name"

    # Parent entity is provider
    parent_entities = [
        ParentEntity(
            name="provider",
            key="provider_id",
            nullable=False,
            system=True,
            is_path=False,
        ),
    ]

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for provider instance creation."""
        parent_ids = parent_ids or {}
        payload = {
            "name": name or self.generate_name(),
            "model_name": "gpt-4",
            "api_key": "fake-api-key-for-testing",
        }

        # Add provider_id if provided
        if "provider_id" in parent_ids:
            payload["provider_id"] = parent_ids["provider_id"]

        if team_id:
            payload["team_id"] = team_id

        return self.nest_payload_in_entity(entity=payload)

    def create_parent_entities(self, server, jwt_a, team_a):
        """Create parent entities for provider instance testing."""
        provider_test = TestProviderEndpoints()
        provider = provider_test.test_POST_201(
            server, jwt_a, team_a, api_key="test-api-key"
        )
        return {"provider": provider}

    def test_GET_200_list_by_team(self, server, jwt_a, team_a):
        """Test retrieving provider instances filtered by team."""
        # Create an instance first
        instance = self.test_POST_201(server, jwt_a, team_a)

        # Get instances filtered by team
        endpoint = f"/v1/{self.base_endpoint}?team_id={team_a['id']}"
        response = server.get(
            endpoint,
            headers=self._auth_header(jwt_a),
        )

        # Should return success with proper response
        self._assert_response_status(response, 200, "GET list by team", endpoint)
        entities = self._assert_entities_in_response(response)

        # Check if our instance is in the results
        instance_ids = [i["id"] for i in entities]
        assert instance["id"] in instance_ids, (
            f"[{self.entity_name}] Created instance not found in team-filtered results\n"
            f"Expected ID: {instance['id']}\n"
            f"Found IDs: {instance_ids}"
        )

        return entities


@pytest.mark.ep
@pytest.mark.providers
class TestProviderNestedInstanceEndpoints(AbstractEndpointTest):
    """Tests for the nested Provider Instance endpoints under Provider."""

    base_endpoint = "instance"
    entity_name = "provider_instance"
    required_fields = ["id", "name", "provider_id", "created_at"]
    string_field_to_update = "name"

    # Parent entity is provider (with path relationship)
    parent_entities = [
        ParentEntity(
            name="provider",
            key="provider_id",
            nullable=False,
            system=True,
            is_path=True,
        ),
    ]

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for provider instance creation."""
        parent_ids = parent_ids or {}
        payload = {
            "name": name or self.generate_name(),
            "model_name": "gpt-4",
            "api_key": "fake-api-key-for-testing",
        }

        # For nested resources, we don't need to explicitly set the parent ID in the payload
        # as it comes from the URL path, but we include it for clarity
        if "provider_id" in parent_ids:
            payload["provider_id"] = parent_ids["provider_id"]

        if team_id:
            payload["team_id"] = team_id

        return self.nest_payload_in_entity(entity=payload)

    def create_parent_entities(self, server, jwt_a, team_a):
        """Create parent entities for provider instance testing."""
        provider_test = TestProviderEndpoints()
        provider = provider_test.test_POST_201(
            server, jwt_a, team_a, api_key="test-api-key"
        )
        return {"provider": provider}


@pytest.mark.ep
@pytest.mark.providers
class TestProviderInstanceSettingEndpoints(AbstractEndpointTest):
    """Tests for the Provider Instance Setting Management endpoints."""

    base_endpoint = "provider-instance-setting"
    entity_name = "provider_instance_setting"
    required_fields = [
        "id",
        "key",
        "value",
        "provider_instance_id",
        "created_at",
        "updated_at",
    ]
    string_field_to_update = "value"

    # Parent entity is provider instance
    parent_entities = [
        ParentEntity(
            name="provider_instance",
            key="provider_instance_id",
            nullable=False,
            system=False,
            is_path=False,
        ),
    ]

    # Tests to skip
    skip_tests = [
        SkippedTest(
            name="test_POST_201", reason="Using the nested endpoint test instead"
        ),
        SkippedTest(
            name="test_POST_201_batch",
            reason="Batch creation not applicable for provider instance settings",
        ),
    ]

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for setting creation."""
        parent_ids = parent_ids or {}
        payload = {"key": f"setting-{uuid.uuid4()}", "value": "test-value"}

        # Add provider_instance_id if provided
        if "provider_instance_id" in parent_ids:
            payload["provider_instance_id"] = parent_ids["provider_instance_id"]

        return self.nest_payload_in_entity(entity=payload)

    def create_parent_entities(self, server, jwt_a, team_a):
        """Create parent entities for provider instance setting testing."""
        provider_instance = TestProviderInstanceEndpoints().test_POST_201(
            server, jwt_a, team_a
        )
        return {"provider_instance": provider_instance}


@pytest.mark.ep
@pytest.mark.providers
class TestProviderInstanceNestedSettingEndpoints(AbstractEndpointTest):
    """Tests for the nested Provider Instance Setting endpoints under Provider Instance."""

    base_endpoint = "setting"
    entity_name = "provider_instance_setting"
    required_fields = [
        "id",
        "key",
        "value",
        "provider_instance_id",
        "created_at",
        "updated_at",
    ]
    string_field_to_update = "value"

    # Parent entity is provider instance (with path relationship)
    parent_entities = [
        ParentEntity(
            name="provider_instance",
            key="provider_instance_id",
            nullable=False,
            system=False,
            is_path=True,
        ),
    ]

    # Tests to skip
    skip_tests = [
        SkippedTest(
            name="test_POST_201_batch",
            reason="Batch creation not applicable for provider instance settings",
        ),
    ]

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for setting creation."""
        payload = {"key": f"setting-{uuid.uuid4()}", "value": "test-value"}

        # For nested resources, we don't need to explicitly set the parent ID in the payload
        return self.nest_payload_in_entity(entity=payload)

    def create_parent_entities(self, server, jwt_a, team_a):
        """Create parent entities for provider instance setting testing."""
        provider_instance_test = TestProviderInstanceEndpoints()
        provider_instance = provider_instance_test.test_POST_201(server, jwt_a, team_a)
        return {"provider_instance": provider_instance}


@pytest.mark.ep
@pytest.mark.providers
class TestRotationEndpoints(AbstractEndpointTest):
    """Tests for the Rotation Management endpoints."""

    base_endpoint = "rotation"
    entity_name = "rotation"
    required_fields = ["id", "name", "created_at"]
    string_field_to_update = "name"

    # No parent entities for rotations
    parent_entities = []

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for rotation creation."""
        payload = {
            "name": name or self.generate_name(),
            "description": f"A test rotation for {name or 'testing'}",
        }

        if team_id:
            payload["team_id"] = team_id

        return self.nest_payload_in_entity(entity=payload)

    def test_GET_200_list_by_team(self, server, jwt_a, team_a):
        """Test retrieving rotations filtered by team."""
        # Create a rotation first
        rotation = self.test_POST_201(server, jwt_a, team_a)

        # Get rotations filtered by team
        endpoint = f"/v1/{self.base_endpoint}?team_id={team_a['id']}"
        response = server.get(
            endpoint,
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(response, 200, "GET list by team", endpoint)
        entities = self._assert_entities_in_response(response)

        # Check if our rotation is in the results
        rotation_ids = [r["id"] for r in entities]
        assert rotation["id"] in rotation_ids, (
            f"[{self.entity_name}] Created rotation not found in team-filtered results\n"
            f"Expected ID: {rotation['id']}\n"
            f"Found IDs: {rotation_ids}"
        )

        return entities


@pytest.mark.ep
@pytest.mark.providers
class TestRotationProviderInstanceEndpoints(AbstractEndpointTest):
    """Tests for the Rotation Provider Management endpoints."""

    base_endpoint = "rotation-provider"
    entity_name = "rotation_provider_instance"
    required_fields = [
        "id",
        "rotation_id",
        "provider_instance_id",
        "created_at",
        "updated_at",
    ]
    string_field_to_update = "parent_id"

    # Parent entities for rotation provider instances
    parent_entities = [
        ParentEntity(
            name="rotation",
            key="rotation_id",
            nullable=False,
            system=False,
            is_path=False,
        ),
        ParentEntity(
            name="provider_instance",
            key="provider_instance_id",
            nullable=False,
            system=False,
            is_path=False,
        ),
    ]

    # Tests to skip
    skip_tests = [
        SkippedTest(
            name="test_POST_201", reason="Using the nested endpoint test instead"
        ),
        SkippedTest(
            name="test_POST_201_batch",
            reason="Batch creation not applicable for rotation provider instances",
        ),
    ]

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for rotation provider instance creation."""
        parent_ids = parent_ids or {}
        payload = {}

        # Add parent IDs if provided
        if "rotation_id" in parent_ids:
            payload["rotation_id"] = parent_ids["rotation_id"]
        if "provider_instance_id" in parent_ids:
            payload["provider_instance_id"] = parent_ids["provider_instance_id"]

        return self.nest_payload_in_entity(entity=payload)

    def create_parent_entities(self, server, jwt_a, team_a):
        """Create parent entities for rotation provider instance testing."""
        rotation_test = TestRotationEndpoints()
        rotation = rotation_test.test_POST_201(server, jwt_a, team_a)

        provider_instance_test = TestProviderInstanceEndpoints()
        provider_instance = provider_instance_test.test_POST_201(server, jwt_a, team_a)

        return {"rotation": rotation, "provider_instance": provider_instance}


@pytest.mark.ep
@pytest.mark.providers
class TestRotationNestedProviderEndpoints(AbstractEndpointTest):
    """Tests for the nested Rotation Provider endpoints under Rotation."""

    base_endpoint = "provider"
    entity_name = "rotation_provider_instance"
    required_fields = [
        "id",
        "rotation_id",
        "provider_instance_id",
        "created_at",
        "updated_at",
    ]
    string_field_to_update = "parent_id"

    # Parent entities with rotation as path parent
    parent_entities = [
        ParentEntity(
            name="rotation",
            key="rotation_id",
            nullable=False,
            system=False,
            is_path=True,
        ),
        ParentEntity(
            name="provider_instance",
            key="provider_instance_id",
            nullable=False,
            system=False,
            is_path=False,
        ),
    ]

    # Tests to skip
    skip_tests = [
        SkippedTest(
            name="test_POST_201_batch",
            reason="Batch creation not applicable for rotation provider instances",
        ),
    ]

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for rotation provider instance creation."""
        parent_ids = parent_ids or {}
        payload = {}

        # For nested resources under rotation, we don't need to specify rotation_id in the payload
        # But we do need to specify the provider_instance_id
        if "provider_instance_id" in parent_ids:
            payload["provider_instance_id"] = parent_ids["provider_instance_id"]

        return self.nest_payload_in_entity(entity=payload)

    def create_parent_entities(self, server, jwt_a, team_a):
        """Create parent entities for rotation provider instance testing."""
        rotation_test = TestRotationEndpoints()
        rotation = rotation_test.test_POST_201(server, jwt_a, team_a)

        provider_instance_test = TestProviderInstanceEndpoints()
        provider_instance = provider_instance_test.test_POST_201(server, jwt_a, team_a)

        return {"rotation": rotation, "provider_instance": provider_instance}

    def test_POST_201_add_provider_with_parent(self, server, jwt_a, team_a):
        """Test adding a provider with parent to a rotation."""
        # Create parent entities
        parent_entities = self.create_parent_entities(server, jwt_a, team_a)
        rotation = parent_entities["rotation"]

        # Create two provider instances
        provider_instance_test = TestProviderInstanceEndpoints()
        provider_instance1 = provider_instance_test.test_POST_201(server, jwt_a, team_a)
        provider_instance2 = provider_instance_test.test_POST_201(server, jwt_a, team_a)

        # Extract parent IDs for the path
        path_parent_ids = {"rotation_id": rotation["id"]}

        # Add first provider to rotation
        payload1 = {
            self.entity_name: {"provider_instance_id": provider_instance1["id"]}
        }

        response1 = server.post(
            self.get_create_endpoint(path_parent_ids),
            json=payload1,
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response1,
            201,
            "POST add first provider",
            self.get_create_endpoint(path_parent_ids),
            payload1,
        )
        rotation_provider1 = self._assert_entity_in_response(response1)

        # Add second provider with first as parent
        payload2 = {
            self.entity_name: {
                "provider_instance_id": provider_instance2["id"],
                "parent_id": rotation_provider1["id"],
            }
        }

        response2 = server.post(
            self.get_create_endpoint(path_parent_ids),
            json=payload2,
            headers=self._auth_header(jwt_a),
        )

        self._assert_response_status(
            response2,
            201,
            "POST add provider with parent",
            self.get_create_endpoint(path_parent_ids),
            payload2,
        )
        rotation_provider2 = self._assert_entity_in_response(response2)

        assert rotation_provider2["parent_id"] == rotation_provider1["id"], (
            f"[{self.entity_name}] Parent ID mismatch\n"
            f"Expected: {rotation_provider1['id']}\n"
            f"Got: {rotation_provider2['parent_id']}"
        )

        return rotation_provider2


@pytest.mark.ep
@pytest.mark.providers
class TestProviderExtensionAbilityEndpoints(AbstractEndpointTest):
    """Tests for the Provider Extension Ability Management endpoints."""

    base_endpoint = "provider/extension/ability"
    entity_name = "provider_extension_ability"
    required_fields = [
        "id",
        "provider_extension_id",
        "ability_id",
        "created_at",
        "updated_at",
    ]
    string_field_to_update = "provider_extension_id"

    # Parent entities
    parent_entities = [
        ParentEntity(
            name="provider_extension",
            key="provider_extension_id",
            nullable=False,
            system=False,
            is_path=False,
        ),
    ]

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for provider extension ability creation."""
        parent_ids = parent_ids or {}
        payload = {"ability_id": str(uuid.uuid4())}  # Random ability ID

        # Add parent IDs if provided
        if "provider_extension_id" in parent_ids:
            payload["provider_extension_id"] = parent_ids["provider_extension_id"]

        return self.nest_payload_in_entity(entity=payload)

    def create_parent_entities(self, server, jwt_a, team_a):
        """Create parent entities for provider extension ability testing."""
        extension_test = TestProviderExtensionEndpoints()
        extension = extension_test.test_POST_201(server, jwt_a, team_a)
        return {"provider_extension": extension}


@pytest.mark.ep
@pytest.mark.providers
class TestProviderInstanceUsageEndpoints(AbstractEndpointTest):
    """Tests for the Provider Instance Usage Management endpoints."""

    base_endpoint = "provider-instance/usage"
    entity_name = "provider_instance_usage"
    required_fields = [
        "id",
        "provider_instance_id",
        "input_tokens",
        "output_tokens",
        "created_at",
        "updated_at",
    ]
    string_field_to_update = (
        "input_tokens"  # Not a string but we can convert int to str for tests
    )

    # Parent entities
    parent_entities = [
        ParentEntity(
            name="provider_instance",
            key="provider_instance_id",
            nullable=False,
            system=False,
            is_path=False,
        ),
    ]

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for provider instance usage creation."""
        parent_ids = parent_ids or {}
        payload = {"input_tokens": 100, "output_tokens": 50}

        # Add parent IDs if provided
        if "provider_instance_id" in parent_ids:
            payload["provider_instance_id"] = parent_ids["provider_instance_id"]

        return self.nest_payload_in_entity(entity=payload)

    def create_parent_entities(self, server, jwt_a, team_a):
        """Create parent entities for provider instance usage testing."""
        instance_test = TestProviderInstanceEndpoints()
        instance = instance_test.test_POST_201(server, jwt_a, team_a)
        return {"provider_instance": instance}


@pytest.mark.ep
@pytest.mark.providers
class TestExtensionInstanceAbilityEndpoints(AbstractEndpointTest):
    """Tests for the Extension Instance Ability Management endpoints."""

    base_endpoint = "extension-instance/ability"
    entity_name = "extension_instance_ability"
    required_fields = [
        "id",
        "provider_instance_id",
        "command_id",
        "state",
        "created_at",
        "updated_at",
    ]
    string_field_to_update = (
        "state"  # Not a string but we can convert bool to str for tests
    )

    # Parent entities
    parent_entities = [
        ParentEntity(
            name="provider_instance",
            key="provider_instance_id",
            nullable=False,
            system=False,
            is_path=False,
        ),
    ]

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for extension instance ability creation."""
        parent_ids = parent_ids or {}
        payload = {
            "command_id": str(uuid.uuid4()),  # Random command ID
            "state": True,
            "forced": False,
        }

        # Add parent IDs if provided
        if "provider_instance_id" in parent_ids:
            payload["provider_instance_id"] = parent_ids["provider_instance_id"]

        return self.nest_payload_in_entity(entity=payload)

    def create_parent_entities(self, server, jwt_a, team_a):
        """Create parent entities for extension instance ability testing."""
        instance_test = TestProviderInstanceEndpoints()
        instance = instance_test.test_POST_201(server, jwt_a, team_a)
        return {"provider_instance": instance}


@pytest.mark.ep
@pytest.mark.providers
class TestCrossUserInteractions:
    """Tests for cross-user interactions with provider resources that aren't covered by AbstractEndpointTest."""

    def test_404_when_accessing_non_team_provider_instance(
        self, server, jwt_a, team_a, jwt_b
    ):
        """Test that users cannot access provider instances not shared with their team."""
        # Create a provider instance with user A (not shared with a team)
        provider_endpoints = TestProviderEndpoints()
        provider = provider_endpoints.test_POST_201(
            server, jwt_a, team_a, api_key="test-api-key"
        )

        instance_name = f"Private Provider Instance {uuid.uuid4()}"
        payload = {
            "provider_instance": {
                "name": instance_name,
                "provider_id": provider["id"],
                "model_name": "gpt-4",
                "api_key": "fake-api-key-for-testing-private",
            }
        }

        response_a = server.post(
            "/v1/provider-instance",
            json=payload,
            headers={"Authorization": f"Bearer {jwt_a}"},
        )
        assert response_a.status_code == 201, (
            f"Expected 201, got {response_a.status_code}: {response_a.text}\n"
            f"Payload: {payload}"
        )
        instance = response_a.json()["provider_instance"]

        # User B should not be able to see or access the provider instance
        response_b = server.get(
            f"/v1/provider-instance/{instance['id']}",
            headers={"Authorization": f"Bearer {jwt_b}"},
        )

        # Should return 404 Not Found (not 403) since the user shouldn't even know it exists
        assert response_b.status_code == 404, (
            f"Expected 404, got {response_b.status_code}: {response_b.text}\n"
            f"User B should not be able to access user A's provider instance"
        )

    def test_200_system_provider_visibility(self, server, jwt_a, jwt_b):
        """Test that system providers are visible to all users."""
        # Get list of providers
        response_a = server.get(
            "/v1/provider", headers={"Authorization": f"Bearer {jwt_a}"}
        )

        response_b = server.get(
            "/v1/provider", headers={"Authorization": f"Bearer {jwt_b}"}
        )

        assert (
            response_a.status_code == 200
        ), f"Expected 200, got {response_a.status_code}: {response_a.text}"
        assert (
            response_b.status_code == 200
        ), f"Expected 200, got {response_b.status_code}: {response_b.text}"

        providers_a = response_a.json()["providers"]
        providers_b = response_b.json()["providers"]

        # Both users should see system providers like OpenAI, Anthropic, etc.
        system_providers = ["OpenAI", "Anthropic", "Cohere", "Mistral"]

        for provider_name in system_providers:
            provider_a = next(
                (p for p in providers_a if p["name"] == provider_name), None
            )
            provider_b = next(
                (p for p in providers_b if p["name"] == provider_name), None
            )

            # If this provider exists in the system, both users should see it
            if provider_a is not None:
                assert (
                    provider_b is not None
                ), f"Provider {provider_name} visible to user A but not to user B"
                assert provider_a["id"] == provider_b["id"], (
                    f"Provider {provider_name} IDs don't match between users: "
                    f"{provider_a['id']} vs {provider_b['id']}"
                )

    def test_404_when_modifying_another_users_rotation_provider(
        self, server, jwt_a, team_a, jwt_b
    ):
        """Test that users cannot modify rotation providers created by other users."""
        # Create a rotation with user A
        rotation_test = TestRotationEndpoints()
        rotation = rotation_test.test_POST_201(server, jwt_a, team_a)

        # Create a provider instance
        provider_instance_test = TestProviderInstanceEndpoints()
        provider_instance = provider_instance_test.test_POST_201(server, jwt_a, team_a)

        # Add a provider to the rotation
        rotation_provider_test = TestRotationNestedProviderEndpoints()
        rotation_provider_test.parent_entities = [
            ParentEntity(
                name="rotation",
                key="rotation_id",
                nullable=False,
                system=False,
                is_path=True,
            ),
            ParentEntity(
                name="provider_instance",
                key="provider_instance_id",
                nullable=False,
                system=False,
                is_path=False,
            ),
        ]

        payload = {
            "rotation_provider_instance": {
                "provider_instance_id": provider_instance["id"]
            }
        }

        response = server.post(
            f"/v1/rotation/{rotation['id']}/provider",
            json=payload,
            headers={"Authorization": f"Bearer {jwt_a}"},
        )

        assert response.status_code == 201, (
            f"Expected 201, got {response.status_code}: {response.text}\n"
            f"Failed to create rotation provider\n"
            f"Payload: {payload}"
        )

        rotation_provider_instance = response.json()["rotation_provider_instance"]

        # Try to update the rotation provider with user B
        update_payload = {"rotation_provider_instance": {"parent_id": None}}

        response = server.put(
            f"/v1/rotation-provider/{rotation_provider_instance['id']}",
            json=update_payload,
            headers={"Authorization": f"Bearer {jwt_b}"},
        )

        # Should return 404 Not Found (not 403)
        assert response.status_code == 404, (
            f"Expected 404, got {response.status_code}: {response.text}\n"
            f"User B should not be able to update user A's rotation provider"
        )

        # Try to delete the rotation provider with user B
        response = server.delete(
            f"/v1/rotation-provider/{rotation_provider_instance['id']}",
            headers={"Authorization": f"Bearer {jwt_b}"},
        )

        # Should return 404 Not Found (not 403)
        assert response.status_code == 404, (
            f"Expected 404, got {response.status_code}: {response.text}\n"
            f"User B should not be able to delete user A's rotation provider"
        )

        # Verify the rotation provider wasn't modified or deleted
        response = server.get(
            f"/v1/rotation-provider/{rotation_provider_instance['id']}",
            headers={"Authorization": f"Bearer {jwt_a}"},
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}\n"
            f"User A should still be able to access their rotation provider"
        )
        assert (
            response.json()["rotation_provider_instance"]["id"]
            == rotation_provider_instance["id"]
        ), (
            f"Rotation provider ID mismatch: "
            f"Expected {rotation_provider_instance['id']}, got {response.json()['rotation_provider_instance']['id']}"
        )
