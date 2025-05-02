import unittest

from .AbstractSDKTest import AbstractSDKTest
from .SDK_Providers import ProvidersSDK


class TestProvidersSDK(AbstractSDKTest):
    """Tests for the ProvidersSDK module."""

    def setUp(self):
        """Set up the test environment."""
        super().setUp()

        # Create ProvidersSDK instance
        self.providers_sdk = ProvidersSDK(
            base_url=self.base_url,
            token=self.default_token,
            api_key=self.default_api_key,
        )

    def test_create_provider(self):
        """Test creating a provider."""
        # Set up mock response
        provider_response = {
            "provider": {
                "id": "provider-123",
                "name": "Test Provider",
                "description": "A test provider",
                "icon_url": "https://example.com/icon.png",
                "created_at": "2023-01-01T00:00:00Z",
            }
        }
        self.mock_response_json(provider_response)

        # Call create_provider method
        result = self.providers_sdk.create_provider(
            name="Test Provider",
            description="A test provider",
            icon_url="https://example.com/icon.png",
        )

        # Verify request
        self.assert_request_called_with(
            "POST",
            "/v1/provider",
            data={
                "provider": {
                    "name": "Test Provider",
                    "description": "A test provider",
                    "icon_url": "https://example.com/icon.png",
                }
            },
        )

        # Verify response
        self.assertEqual(result, provider_response)

    def test_get_provider(self):
        """Test retrieving a provider by ID."""
        # Set up mock response
        provider_response = {
            "provider": {
                "id": "provider-123",
                "name": "Test Provider",
                "description": "A test provider",
                "icon_url": "https://example.com/icon.png",
                "created_at": "2023-01-01T00:00:00Z",
            }
        }
        self.mock_response_json(provider_response)

        # Call get_provider method
        result = self.providers_sdk.get_provider("provider-123")

        # Verify request
        self.assert_request_called_with("GET", "/v1/provider/provider-123")

        # Verify response
        self.assertEqual(result, provider_response)

    def test_update_provider(self):
        """Test updating a provider."""
        # Set up mock response
        provider_response = {
            "provider": {
                "id": "provider-123",
                "name": "Updated Provider",
                "description": "An updated provider",
                "icon_url": "https://example.com/updated-icon.png",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-02T00:00:00Z",
            }
        }
        self.mock_response_json(provider_response)

        # Call update_provider method
        result = self.providers_sdk.update_provider(
            provider_id="provider-123",
            name="Updated Provider",
            description="An updated provider",
            icon_url="https://example.com/updated-icon.png",
        )

        # Verify request
        self.assert_request_called_with(
            "PUT",
            "/v1/provider/provider-123",
            data={
                "provider": {
                    "name": "Updated Provider",
                    "description": "An updated provider",
                    "icon_url": "https://example.com/updated-icon.png",
                }
            },
        )

        # Verify response
        self.assertEqual(result, provider_response)

    def test_list_providers(self):
        """Test listing providers with pagination and sorting."""
        # Set up mock response
        providers_response = {
            "providers": [
                {
                    "id": "provider-123",
                    "name": "Test Provider 1",
                    "description": "A test provider",
                    "icon_url": "https://example.com/icon1.png",
                    "created_at": "2023-01-01T00:00:00Z",
                },
                {
                    "id": "provider-456",
                    "name": "Test Provider 2",
                    "description": "Another test provider",
                    "icon_url": "https://example.com/icon2.png",
                    "created_at": "2023-01-02T00:00:00Z",
                },
            ]
        }
        self.mock_response_json(providers_response)

        # Call list_providers method with pagination and sorting
        result = self.providers_sdk.list_providers(
            offset=10, limit=50, sort_by="name", sort_order="desc"
        )

        # Verify request
        self.assert_request_called_with(
            "GET",
            "/v1/provider",
            params={"offset": 10, "limit": 50, "sort_by": "name", "sort_order": "desc"},
        )

        # Verify response
        self.assertEqual(result, providers_response)

    def test_delete_provider(self):
        """Test deleting a provider."""
        # Set up mock response for successful deletion
        self.mock_response.status_code = 204
        self.mock_response.content = b""

        # Call delete_provider method
        self.providers_sdk.delete_provider("provider-123")

        # Verify request
        self.assert_request_called_with("DELETE", "/v1/provider/provider-123")

    # --- Provider Instance Tests ---

    def test_create_provider_instance(self):
        """Test creating a provider instance."""
        # Set up mock response
        instance_response = {
            "provider_instance": {
                "id": "instance-123",
                "name": "Test Instance",
                "provider_id": "provider-123",
                "model_name": "gpt-4",
                "api_key": "•••••••",  # Masked
                "team_id": "team-123",
                "created_at": "2023-01-01T00:00:00Z",
            }
        }
        self.mock_response_json(instance_response)

        # Call create_provider_instance method
        result = self.providers_sdk.create_provider_instance(
            name="Test Instance",
            provider_id="provider-123",
            model_name="gpt-4",
            api_key="secret-api-key",
            team_id="team-123",
        )

        # Verify request
        self.assert_request_called_with(
            "POST",
            "/v1/provider-instance",
            data={
                "provider_instance": {
                    "name": "Test Instance",
                    "provider_id": "provider-123",
                    "model_name": "gpt-4",
                    "api_key": "secret-api-key",
                    "team_id": "team-123",
                }
            },
        )

        # Verify response
        self.assertEqual(result, instance_response)

    def test_get_provider_instance(self):
        """Test retrieving a provider instance by ID."""
        # Set up mock response
        instance_response = {
            "provider_instance": {
                "id": "instance-123",
                "name": "Test Instance",
                "provider_id": "provider-123",
                "model_name": "gpt-4",
                "api_key": "•••••••",  # Masked
                "team_id": "team-123",
                "created_at": "2023-01-01T00:00:00Z",
            }
        }
        self.mock_response_json(instance_response)

        # Call get_provider_instance method
        result = self.providers_sdk.get_provider_instance("instance-123")

        # Verify request
        self.assert_request_called_with("GET", "/v1/provider-instance/instance-123")

        # Verify response
        self.assertEqual(result, instance_response)

    def test_update_provider_instance(self):
        """Test updating a provider instance."""
        # Set up mock response
        instance_response = {
            "provider_instance": {
                "id": "instance-123",
                "name": "Updated Instance",
                "provider_id": "provider-123",
                "model_name": "gpt-4-turbo",
                "api_key": "•••••••",  # Masked
                "team_id": "team-123",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-02T00:00:00Z",
            }
        }
        self.mock_response_json(instance_response)

        # Call update_provider_instance method
        result = self.providers_sdk.update_provider_instance(
            instance_id="instance-123",
            name="Updated Instance",
            model_name="gpt-4-turbo",
        )

        # Verify request
        self.assert_request_called_with(
            "PUT",
            "/v1/provider-instance/instance-123",
            data={
                "provider_instance": {
                    "name": "Updated Instance",
                    "model_name": "gpt-4-turbo",
                }
            },
        )

        # Verify response
        self.assertEqual(result, instance_response)

    def test_list_provider_instances(self):
        """Test listing provider instances with pagination and sorting."""
        # Set up mock response
        instances_response = {
            "provider_instances": [
                {
                    "id": "instance-123",
                    "name": "Test Instance 1",
                    "provider_id": "provider-123",
                    "model_name": "gpt-4",
                    "api_key": "•••••••",  # Masked
                    "team_id": "team-123",
                    "created_at": "2023-01-01T00:00:00Z",
                },
                {
                    "id": "instance-456",
                    "name": "Test Instance 2",
                    "provider_id": "provider-456",
                    "model_name": "claude-3",
                    "api_key": "•••••••",  # Masked
                    "team_id": "team-123",
                    "created_at": "2023-01-02T00:00:00Z",
                },
            ]
        }
        self.mock_response_json(instances_response)

        # Call list_provider_instances method with pagination and sorting
        result = self.providers_sdk.list_provider_instances(
            offset=10, limit=50, sort_by="name", sort_order="desc"
        )

        # Verify request
        self.assert_request_called_with(
            "GET",
            "/v1/provider-instance",
            params={"offset": 10, "limit": 50, "sort_by": "name", "sort_order": "desc"},
        )

        # Verify response
        self.assertEqual(result, instances_response)

    def test_delete_provider_instance(self):
        """Test deleting a provider instance."""
        # Set up mock response for successful deletion
        self.mock_response.status_code = 204
        self.mock_response.content = b""

        # Call delete_provider_instance method
        self.providers_sdk.delete_provider_instance("instance-123")

        # Verify request
        self.assert_request_called_with("DELETE", "/v1/provider-instance/instance-123")

    def test_list_provider_instances_for_provider(self):
        """Test listing provider instances for a specific provider."""
        # Set up mock response
        instances_response = {
            "provider_instances": [
                {
                    "id": "instance-123",
                    "name": "Test Instance 1",
                    "provider_id": "provider-123",
                    "model_name": "gpt-4",
                    "api_key": "•••••••",  # Masked
                    "team_id": "team-123",
                    "created_at": "2023-01-01T00:00:00Z",
                },
                {
                    "id": "instance-456",
                    "name": "Test Instance 2",
                    "provider_id": "provider-123",
                    "model_name": "gpt-3.5-turbo",
                    "api_key": "•••••••",  # Masked
                    "team_id": "team-123",
                    "created_at": "2023-01-02T00:00:00Z",
                },
            ]
        }
        self.mock_response_json(instances_response)

        # Call list_provider_instances_for_provider method
        result = self.providers_sdk.list_provider_instances_for_provider(
            provider_id="provider-123", offset=5, limit=20
        )

        # Verify request
        self.assert_request_called_with(
            "GET",
            "/v1/provider/provider-123/instance",
            params={"offset": 5, "limit": 20},
        )

        # Verify response
        self.assertEqual(result, instances_response)

    # --- Provider Instance Setting Tests ---

    def test_create_provider_instance_setting(self):
        """Test creating a provider instance setting."""
        # Set up mock response
        setting_response = {
            "provider_instance_setting": {
                "id": "setting-123",
                "provider_instance_id": "instance-123",
                "key": "temperature",
                "value": "0.7",
                "created_at": "2023-01-01T00:00:00Z",
            }
        }
        self.mock_response_json(setting_response)

        # Call create_provider_instance_setting method
        result = self.providers_sdk.create_provider_instance_setting(
            instance_id="instance-123", key="temperature", value="0.7"
        )

        # Verify request
        self.assert_request_called_with(
            "POST",
            "/v1/provider-instance-setting",
            data={
                "provider_instance_setting": {
                    "provider_instance_id": "instance-123",
                    "key": "temperature",
                    "value": "0.7",
                }
            },
        )

        # Verify response
        self.assertEqual(result, setting_response)

    # --- Rotation Tests ---

    def test_create_rotation(self):
        """Test creating a rotation."""
        # Set up mock response
        rotation_response = {
            "rotation": {
                "id": "rotation-123",
                "name": "Test Rotation",
                "description": "Test description",
                "team_id": "team-123",
                "created_at": "2023-01-01T00:00:00Z",
            }
        }
        self.mock_response_json(rotation_response)

        # Call create_rotation method
        result = self.providers_sdk.create_rotation(
            name="Test Rotation", team_id="team-123", description="Test description"
        )

        # Verify request
        self.assert_request_called_with(
            "POST",
            "/v1/rotation",
            data={
                "rotation": {
                    "name": "Test Rotation",
                    "team_id": "team-123",
                    "description": "Test description",
                }
            },
        )

        # Verify response
        self.assertEqual(result, rotation_response)

    def test_add_provider_instance_to_rotation(self):
        """Test adding a provider instance to a rotation."""
        # Set up mock response
        rotation_provider_response = {
            "rotation_provider_instance": {
                "id": "rotation-provider-123",
                "rotation_id": "rotation-123",
                "provider_instance_id": "instance-123",
                "parent_id": None,
                "created_at": "2023-01-01T00:00:00Z",
            }
        }
        self.mock_response_json(rotation_provider_response)

        # Call add_provider_instance_to_rotation method
        result = self.providers_sdk.add_provider_instance_to_rotation(
            rotation_id="rotation-123", provider_instance_id="instance-123"
        )

        # Verify request
        self.assert_request_called_with(
            "POST",
            "/v1/rotation-provider",
            data={
                "rotation_provider_instance": {
                    "rotation_id": "rotation-123",
                    "provider_instance_id": "instance-123",
                }
            },
        )

        # Verify response
        self.assertEqual(result, rotation_provider_response)

    # --- Provider Extension Ability Tests ---

    def test_add_ability_to_provider_extension(self):
        """Test adding an ability to a provider extension."""
        # Set up mock response
        ability_response = {
            "provider_extension_ability": {
                "id": "ability-123",
                "provider_extension_id": "extension-123",
                "ability_id": "abilityType-123",
                "created_at": "2023-01-01T00:00:00Z",
            }
        }
        self.mock_response_json(ability_response)

        # Call add_ability_to_provider_extension method
        result = self.providers_sdk.add_ability_to_provider_extension(
            provider_extension_id="extension-123", ability_id="abilityType-123"
        )

        # Verify request
        self.assert_request_called_with(
            "POST",
            "/v1/provider/extension/ability",
            data={
                "provider_extension_ability": {
                    "provider_extension_id": "extension-123",
                    "ability_id": "abilityType-123",
                }
            },
        )

        # Verify response
        self.assertEqual(result, ability_response)

    # --- Provider Instance Usage Tests ---

    def test_record_provider_instance_usage(self):
        """Test recording provider instance usage."""
        # Set up mock response
        usage_response = {
            "provider_instance_usage": {
                "id": "usage-123",
                "provider_instance_id": "instance-123",
                "input_tokens": 100,
                "output_tokens": 50,
                "created_at": "2023-01-01T00:00:00Z",
            }
        }
        self.mock_response_json(usage_response)

        # Call record_provider_instance_usage method
        result = self.providers_sdk.record_provider_instance_usage(
            provider_instance_id="instance-123", input_tokens=100, output_tokens=50
        )

        # Verify request
        self.assert_request_called_with(
            "POST",
            "/v1/provider-instance/usage",
            data={
                "provider_instance_usage": {
                    "provider_instance_id": "instance-123",
                    "input_tokens": 100,
                    "output_tokens": 50,
                }
            },
        )

        # Verify response
        self.assertEqual(result, usage_response)

    # --- Extension Instance Ability Tests ---

    def test_set_extension_instance_ability(self):
        """Test setting an extension instance ability."""
        # Set up mock response
        ability_response = {
            "extension_instance_ability": {
                "id": "ability-123",
                "provider_instance_id": "instance-123",
                "command_id": "command-123",
                "state": True,
                "forced": False,
                "created_at": "2023-01-01T00:00:00Z",
            }
        }
        self.mock_response_json(ability_response)

        # Call set_extension_instance_ability method
        result = self.providers_sdk.set_extension_instance_ability(
            provider_instance_id="instance-123",
            command_id="command-123",
            state=True,
            forced=False,
        )

        # Verify request
        self.assert_request_called_with(
            "POST",
            "/v1/extension-instance/ability",
            data={
                "extension_instance_ability": {
                    "provider_instance_id": "instance-123",
                    "command_id": "command-123",
                    "state": True,
                    "forced": False,
                }
            },
        )

        # Verify response
        self.assertEqual(result, ability_response)


if __name__ == "__main__":
    unittest.main()
