import uuid

import pytest

from AbstractTest import ParentEntity, TestToSkip
from endpoints.AbstractEPTest import AbstractEndpointTest


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
        TestToSkip(
            name="test_GET_404_other_user",
            details="Users can access all providers - they are global resources.",
        ),
        TestToSkip(name="test_PUT_404_other_user", details="See test_PUT_403_system"),
        TestToSkip(
            name="test_DELETE_404_other_user", details="See test_DELETE_403_system"
        ),
    ]

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for provider creation."""
        payload = {
            "name": name or testdata.get_name(1),
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
            "name": name or testdata.get_name(1),
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
            foreign_key="provider_id",
            nullable=False,
            system=True,
            path_level=1,
            test_class=TestProviderEndpoints,
        ),
    ]

    NESTING_CONFIG_OVERRIDES = {
        "LIST": 1,
        "CREATE": 1,
        "DETAIL": 1,
        "SEARCH": 1,
    }

    def create_payload(self, name=None, parent_ids=None, team_id=None):
        """Create a payload for provider instance creation."""
        parent_ids = parent_ids or {}
        payload = {
            "name": name or testdata.get_name(1),
            "model_name": "gpt-4",
            "api_key": "fake-api-key-for-testing",
        }

        # Add provider_id if provided
        if "provider_id" in parent_ids:
            payload["provider_id"] = parent_ids["provider_id"]

        if team_id:
            payload["team_id"] = team_id

        return self.nest_payload_in_entity(entity=payload)

    def create_parent_entities(self, server, admin_a_jwt, team_a):
        """Create parent entities for provider instance testing."""
        provider_test = TestProviderEndpoints()
        provider = provider_test.test_POST_201(
            server, admin_a_jwt, team_a, api_key="test-api-key"
        )
        return {"provider": provider}

    def test_GET_200_list_by_team(self, server, admin_a_jwt, team_a):
        """Test retrieving provider instances filtered by team."""
        # Create an instance first
        instance = self.test_POST_201(server, admin_a_jwt, team_a)

        # Get instances filtered by team
        endpoint = f"/v1/{self.base_endpoint}?team_id={team_a['id']}"
        response = server.get(
            endpoint,
            headers=self._auth_header(admin_a_jwt),
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
            "name": name or testdata.get_name(1),
            "description": f"A test rotation for {name or 'testing'}",
        }

        if team_id:
            payload["team_id"] = team_id

        return self.nest_payload_in_entity(entity=payload)

    def test_GET_200_list_by_team(self, server, admin_a_jwt, team_a):
        """Test retrieving rotations filtered by team."""
        # Create a rotation first
        rotation = self.test_POST_201(server, admin_a_jwt, team_a)

        # Get rotations filtered by team
        endpoint = f"/v1/{self.base_endpoint}?team_id={team_a['id']}"
        response = server.get(
            endpoint,
            headers=self._auth_header(admin_a_jwt),
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
            foreign_key="rotation_id",
            nullable=False,
            test_class=TestRotationEndpoints,
        ),
        ParentEntity(
            name="provider_instance",
            foreign_key="provider_instance_id",
            nullable=False,
            test_class=TestProviderInstanceEndpoints,
        ),
    ]

    # Tests to skip
    skip_tests = [
        TestToSkip(
            name="test_POST_201", details="Using the nested endpoint test instead"
        ),
        TestToSkip(
            name="test_POST_201_batch",
            details="Batch creation not applicable for rotation provider instances",
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

    def create_parent_entities(self, server, admin_a_jwt, team_a):
        """Create parent entities for rotation provider instance testing."""
        rotation_test = TestRotationEndpoints()
        rotation = rotation_test.test_POST_201(server, admin_a_jwt, team_a)

        provider_instance_test = TestProviderInstanceEndpoints()
        provider_instance = provider_instance_test.test_POST_201(
            server, admin_a_jwt, team_a
        )

        return {"rotation": rotation, "provider_instance": provider_instance}


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
            foreign_key="provider_extension_id",
            nullable=False,
            system=False,
            is_path=False,
            test_class=TestProviderExtensionEndpoints,
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

    def create_parent_entities(self, server, admin_a_jwt, team_a):
        """Create parent entities for provider extension ability testing."""
        extension_test = TestProviderExtensionEndpoints()
        extension = extension_test.test_POST_201(server, admin_a_jwt, team_a)
        return {"provider_extension": extension}
