import json
import unittest

from .AbstractSDKTest import AbstractSDKTest
from .SDK_Extensions import ExtensionsSDK


class TestExtensionsSDK(AbstractSDKTest):
    """Tests for the ExtensionsSDK module."""

    def setUp(self):
        """Set up the test environment."""
        super().setUp()

        # Create ExtensionsSDK instance
        self.extensions_sdk = ExtensionsSDK(
            base_url=self.base_url,
            token=self.default_token,
            api_key=self.default_api_key,
        )

    def test_list_available_extensions(self):
        """Test listing available extensions."""
        # Set up mock response
        extensions_response = {
            "extensions": [
                {
                    "id": "extension-123",
                    "name": "OpenAI",
                    "description": "OpenAI provider integration",
                    "icon_url": "https://example.com/openai.png",
                    "version": "1.0.0",
                    "created_at": "2023-01-01T00:00:00Z",
                },
                {
                    "id": "extension-456",
                    "name": "Anthropic",
                    "description": "Anthropic provider integration",
                    "icon_url": "https://example.com/anthropic.png",
                    "version": "1.0.0",
                    "created_at": "2023-01-02T00:00:00Z",
                },
            ]
        }
        self.mock_response_json(extensions_response)

        # Call list_available_extensions method
        result = self.extensions_sdk.list_available_extensions(
            offset=10,
            limit=50,
            sort_by="name",
            sort_order="desc",
            filters={"is_common": True},
        )

        # Verify request
        self.assert_request_called_with(
            "GET",
            "/v1/extension/available",
            params={
                "offset": 10,
                "limit": 50,
                "sort_by": "name",
                "sort_order": "desc",
                "is_common": True,
            },
        )

        # Verify response
        self.assertEqual(result, extensions_response)

    def test_get_provider_extensions(self):
        """Test getting extensions for a provider."""
        # Set up mock response
        extensions_response = {
            "provider_extensions": [
                {
                    "id": "provider-extension-123",
                    "provider_id": "provider-123",
                    "extension_id": "extension-123",
                    "status": "enabled",
                    "config_json": '{"api_base": "https://api.openai.com/v1"}',
                    "created_at": "2023-01-01T00:00:00Z",
                }
            ]
        }
        self.mock_response_json(extensions_response)

        # Call get_provider_extensions method
        result = self.extensions_sdk.get_provider_extensions(
            provider_id="provider-123", status="enabled"
        )

        # Verify request
        self.assert_request_called_with(
            "GET", "/v1/provider/provider-123/extension", params={"status": "enabled"}
        )

        # Verify response
        self.assertEqual(result, extensions_response)

    def test_install_extension(self):
        """Test installing an extension for a provider."""
        # Set up mock response
        extension_response = {
            "provider_extension": {
                "id": "provider-extension-123",
                "provider_id": "provider-123",
                "extension_id": "extension-123",
                "status": "enabled",
                "config_json": '{"api_base": "https://api.openai.com/v1"}',
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
            }
        }
        self.mock_response_json(extension_response)

        # Call install_extension method
        result = self.extensions_sdk.install_extension(
            provider_id="provider-123",
            extension_id="extension-123",
            config={"api_base": "https://api.openai.com/v1"},
        )

        # Verify request
        self.assert_request_called_with(
            "POST",
            "/v1/provider/provider-123/extension",
            data={
                "provider_extension": {
                    "extension_id": "extension-123",
                    "config_json": json.dumps(
                        {"api_base": "https://api.openai.com/v1"}
                    ),
                }
            },
        )

        # Verify response
        self.assertEqual(result, extension_response)

    def test_uninstall_extension(self):
        """Test uninstalling an extension from a provider."""
        # Set up mock response for successful deletion
        self.mock_response.status_code = 204
        self.mock_response.content = b""

        # Call uninstall_extension method
        self.extensions_sdk.uninstall_extension(
            provider_id="provider-123", extension_id="extension-123"
        )

        # Verify request
        self.assert_request_called_with(
            "DELETE", "/v1/provider/provider-123/extension/extension-123"
        )

    def test_create_extension(self):
        """Test creating a new extension."""
        # Set up mock response
        extension_response = {
            "extension": {
                "id": "extension-123",
                "name": "Custom Extension",
                "description": "A custom extension",
                "icon_url": "https://example.com/icon.png",
                "version": "1.0.0",
                "created_at": "2023-01-01T00:00:00Z",
            }
        }
        self.mock_response_json(extension_response)

        # Call create_extension method
        result = self.extensions_sdk.create_extension(
            name="Custom Extension",
            description="A custom extension",
            icon_url="https://example.com/icon.png",
            version="1.0.0",
        )

        # Verify request
        self.assert_request_called_with(
            "POST",
            "/v1/extension",
            data={
                "extension": {
                    "name": "Custom Extension",
                    "description": "A custom extension",
                    "icon_url": "https://example.com/icon.png",
                    "version": "1.0.0",
                }
            },
        )

        # Verify response
        self.assertEqual(result, extension_response)

    def test_get_extension(self):
        """Test getting an extension by ID."""
        # Set up mock response
        extension_response = {
            "extension": {
                "id": "extension-123",
                "name": "OpenAI",
                "description": "OpenAI provider integration",
                "icon_url": "https://example.com/openai.png",
                "version": "1.0.0",
                "created_at": "2023-01-01T00:00:00Z",
            }
        }
        self.mock_response_json(extension_response)

        # Call get_extension method
        result = self.extensions_sdk.get_extension("extension-123")

        # Verify request
        self.assert_request_called_with("GET", "/v1/extension/extension-123")

        # Verify response
        self.assertEqual(result, extension_response)

    def test_update_extension(self):
        """Test updating an extension."""
        # Set up mock response
        extension_response = {
            "extension": {
                "id": "extension-123",
                "name": "Updated Extension",
                "description": "Updated description",
                "icon_url": "https://example.com/updated-icon.png",
                "version": "1.1.0",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-02T00:00:00Z",
            }
        }
        self.mock_response_json(extension_response)

        # Call update_extension method
        result = self.extensions_sdk.update_extension(
            extension_id="extension-123",
            name="Updated Extension",
            description="Updated description",
            icon_url="https://example.com/updated-icon.png",
            version="1.1.0",
        )

        # Verify request
        self.assert_request_called_with(
            "PUT",
            "/v1/extension/extension-123",
            data={
                "extension": {
                    "name": "Updated Extension",
                    "description": "Updated description",
                    "icon_url": "https://example.com/updated-icon.png",
                    "version": "1.1.0",
                }
            },
        )

        # Verify response
        self.assertEqual(result, extension_response)

    def test_list_extensions(self):
        """Test listing extensions."""
        # Set up mock response
        extensions_response = {
            "extensions": [
                {
                    "id": "extension-123",
                    "name": "OpenAI",
                    "description": "OpenAI provider integration",
                    "icon_url": "https://example.com/openai.png",
                    "version": "1.0.0",
                    "created_at": "2023-01-01T00:00:00Z",
                },
                {
                    "id": "extension-456",
                    "name": "Anthropic",
                    "description": "Anthropic provider integration",
                    "icon_url": "https://example.com/anthropic.png",
                    "version": "1.0.0",
                    "created_at": "2023-01-02T00:00:00Z",
                },
            ]
        }
        self.mock_response_json(extensions_response)

        # Call list_extensions method
        result = self.extensions_sdk.list_extensions(
            offset=10, limit=50, sort_by="name", sort_order="desc"
        )

        # Verify request
        self.assert_request_called_with(
            "GET",
            "/v1/extension",
            params={"offset": 10, "limit": 50, "sort_by": "name", "sort_order": "desc"},
        )

        # Verify response
        self.assertEqual(result, extensions_response)

    def test_delete_extension(self):
        """Test deleting an extension."""
        # Set up mock response for successful deletion
        self.mock_response.status_code = 204
        self.mock_response.content = b""

        # Call delete_extension method
        self.extensions_sdk.delete_extension("extension-123")

        # Verify request
        self.assert_request_called_with("DELETE", "/v1/extension/extension-123")

    def test_search_extensions(self):
        """Test searching for extensions."""
        # Set up mock response
        search_response = {
            "extensions": [
                {
                    "id": "extension-123",
                    "name": "OpenAI",
                    "description": "OpenAI provider integration",
                    "icon_url": "https://example.com/openai.png",
                    "version": "1.0.0",
                    "created_at": "2023-01-01T00:00:00Z",
                }
            ]
        }
        self.mock_response_json(search_response)

        # Call search_extensions method
        result = self.extensions_sdk.search_extensions(
            query="OpenAI", offset=0, limit=10, sort_by="relevance", sort_order="desc"
        )

        # Verify request
        self.assert_request_called_with(
            "GET",
            "/v1/extension/search",
            params={
                "query": "OpenAI",
                "offset": 0,
                "limit": 10,
                "sort_by": "relevance",
                "sort_order": "desc",
            },
        )

        # Verify response
        self.assertEqual(result, search_response)


if __name__ == "__main__":
    unittest.main()
