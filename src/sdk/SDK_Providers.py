from typing import Any, Dict, Optional

from .AbstractSDKHandler import AbstractSDKHandler


class ProvidersSDK(AbstractSDKHandler):
    """SDK for provider management.

    This class provides methods for managing providers, provider instances,
    provider settings, rotations, and related entities.
    """

    # --- Provider methods ---

    def create_provider(
        self, name: str, extension_id: str, agent_settings_json: str = None, **kwargs
    ) -> Dict[str, Any]:
        """Create a new provider.

        Args:
            name: Provider name
            extension_id: ID of the extension to use
            agent_settings_json: JSON string with agent settings
            **kwargs: Additional provider data

        Returns:
            New provider information
        """
        data = {
            "provider": {
                "name": name,
                "extension_id": extension_id,
                **kwargs,
            }
        }

        if agent_settings_json:
            data["provider"]["agent_settings_json"] = agent_settings_json

        return self.post("/v1/provider", data, resource_name="provider")

    def get_provider(self, provider_id: str) -> Dict[str, Any]:
        """Get a provider by ID.

        Args:
            provider_id: Provider ID

        Returns:
            Provider information
        """
        return self.get(f"/v1/provider/{provider_id}", resource_name="provider")

    def update_provider(self, provider_id: str, **provider_data) -> Dict[str, Any]:
        """Update a provider.

        Args:
            provider_id: Provider ID
            **provider_data: Provider data to update

        Returns:
            Updated provider information
        """
        data = {"provider": provider_data}
        return self.put(f"/v1/provider/{provider_id}", data, resource_name="provider")

    def list_providers(
        self,
        offset: int = 0,
        limit: int = 100,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
    ) -> Dict[str, Any]:
        """List providers with pagination.

        Args:
            offset: Number of items to skip
            limit: Maximum number of items to return
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)

        Returns:
            List of providers
        """
        params = {
            "offset": offset,
            "limit": limit,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }

        return self.get("/v1/provider", query_params=params, resource_name="providers")

    def delete_provider(self, provider_id: str) -> None:
        """Delete a provider.

        Args:
            provider_id: Provider ID
        """
        self.delete(f"/v1/provider/{provider_id}", resource_name="provider")

    def search_providers(
        self, criteria: Dict[str, Any], offset: int = 0, limit: int = 100
    ) -> Dict[str, Any]:
        """Search for providers.

        Args:
            criteria: Search criteria
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of matching providers
        """
        params = {
            "offset": offset,
            "limit": limit,
        }

        return self.post(
            "/v1/provider/search",
            criteria,
            query_params=params,
            resource_name="providers",
        )

    # --- Provider Instance methods ---

    def create_provider_instance(
        self,
        name: str,
        provider_id: str,
        model_name: str,
        api_key: str,
        team_id: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Create a new provider instance.

        Args:
            name: Instance name
            provider_id: Provider ID
            model_name: Name of the model to use
            api_key: API key for the provider
            team_id: ID of the team this instance belongs to
            **kwargs: Additional instance data

        Returns:
            New provider instance information
        """
        data = {
            "provider_instance": {
                "name": name,
                "provider_id": provider_id,
                "model_name": model_name,
                "api_key": api_key,
                "team_id": team_id,
                **kwargs,
            }
        }

        return self.post(
            "/v1/provider-instance", data, resource_name="provider_instance"
        )

    def get_provider_instance(self, instance_id: str) -> Dict[str, Any]:
        """Get a provider instance by ID.

        Args:
            instance_id: Provider instance ID

        Returns:
            Provider instance information
        """
        return self.get(
            f"/v1/provider-instance/{instance_id}", resource_name="provider_instance"
        )

    def update_provider_instance(
        self, instance_id: str, **instance_data
    ) -> Dict[str, Any]:
        """Update a provider instance.

        Args:
            instance_id: Provider instance ID
            **instance_data: Provider instance data to update

        Returns:
            Updated provider instance information
        """
        data = {"provider_instance": instance_data}
        return self.put(
            f"/v1/provider-instance/{instance_id}",
            data,
            resource_name="provider_instance",
        )

    def list_provider_instances(
        self,
        offset: int = 0,
        limit: int = 100,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
    ) -> Dict[str, Any]:
        """List provider instances with pagination.

        Args:
            offset: Number of items to skip
            limit: Maximum number of items to return
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)

        Returns:
            List of provider instances
        """
        params = {
            "offset": offset,
            "limit": limit,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }

        return self.get(
            "/v1/provider-instance",
            query_params=params,
            resource_name="provider_instances",
        )

    def delete_provider_instance(self, instance_id: str) -> None:
        """Delete a provider instance.

        Args:
            instance_id: Provider instance ID
        """
        self.delete(
            f"/v1/provider-instance/{instance_id}", resource_name="provider_instance"
        )

    def list_provider_instances_for_provider(
        self, provider_id: str, offset: int = 0, limit: int = 100
    ) -> Dict[str, Any]:
        """List instances for a specific provider.

        Args:
            provider_id: Provider ID
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of provider instances for the provider
        """
        params = {
            "offset": offset,
            "limit": limit,
        }

        return self.get(
            f"/v1/provider/{provider_id}/instance",
            query_params=params,
            resource_name="provider_instances",
        )

    # --- Provider Instance Settings methods ---

    def create_provider_instance_setting(
        self, instance_id: str, key: str, value: str
    ) -> Dict[str, Any]:
        """Create a setting for a provider instance.

        Args:
            instance_id: Provider instance ID
            key: Setting key
            value: Setting value

        Returns:
            New provider instance setting information
        """
        data = {
            "provider_instance_setting": {
                "provider_instance_id": instance_id,
                "key": key,
                "value": value,
            }
        }

        return self.post(
            "/v1/provider-instance-setting",
            data,
            resource_name="provider_instance_setting",
        )

    def get_provider_instance_setting(self, setting_id: str) -> Dict[str, Any]:
        """Get a provider instance setting by ID.

        Args:
            setting_id: Provider instance setting ID

        Returns:
            Provider instance setting information
        """
        return self.get(
            f"/v1/provider-instance-setting/{setting_id}",
            resource_name="provider_instance_setting",
        )

    def update_provider_instance_setting(
        self, setting_id: str, value: str
    ) -> Dict[str, Any]:
        """Update a provider instance setting.

        Args:
            setting_id: Provider instance setting ID
            value: New setting value

        Returns:
            Updated provider instance setting information
        """
        data = {"provider_instance_setting": {"value": value}}
        return self.put(
            f"/v1/provider-instance-setting/{setting_id}",
            data,
            resource_name="provider_instance_setting",
        )

    def list_provider_instance_settings(
        self, instance_id: str, offset: int = 0, limit: int = 100
    ) -> Dict[str, Any]:
        """List settings for a provider instance.

        Args:
            instance_id: Provider instance ID
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of provider instance settings
        """
        params = {
            "offset": offset,
            "limit": limit,
        }

        return self.get(
            f"/v1/provider-instance/{instance_id}/setting",
            query_params=params,
            resource_name="provider_instance_settings",
        )

    def delete_provider_instance_setting(self, setting_id: str) -> None:
        """Delete a provider instance setting.

        Args:
            setting_id: Provider instance setting ID
        """
        self.delete(
            f"/v1/provider-instance-setting/{setting_id}",
            resource_name="provider_instance_setting",
        )

    # --- Rotation methods ---

    def create_rotation(
        self, name: str, team_id: str, description: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Create a new rotation.

        Args:
            name: Rotation name
            team_id: ID of the team this rotation belongs to
            description: Optional description
            **kwargs: Additional rotation data

        Returns:
            New rotation information
        """
        data = {
            "rotation": {
                "name": name,
                "team_id": team_id,
                **kwargs,
            }
        }

        if description:
            data["rotation"]["description"] = description

        return self.post("/v1/rotation", data, resource_name="rotation")

    def get_rotation(self, rotation_id: str) -> Dict[str, Any]:
        """Get a rotation by ID.

        Args:
            rotation_id: Rotation ID

        Returns:
            Rotation information
        """
        return self.get(f"/v1/rotation/{rotation_id}", resource_name="rotation")

    def update_rotation(self, rotation_id: str, **rotation_data) -> Dict[str, Any]:
        """Update a rotation.

        Args:
            rotation_id: Rotation ID
            **rotation_data: Rotation data to update

        Returns:
            Updated rotation information
        """
        data = {"rotation": rotation_data}
        return self.put(f"/v1/rotation/{rotation_id}", data, resource_name="rotation")

    def list_rotations(
        self,
        offset: int = 0,
        limit: int = 100,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
    ) -> Dict[str, Any]:
        """List rotations with pagination.

        Args:
            offset: Number of items to skip
            limit: Maximum number of items to return
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)

        Returns:
            List of rotations
        """
        params = {
            "offset": offset,
            "limit": limit,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }

        return self.get("/v1/rotation", query_params=params, resource_name="rotations")

    def delete_rotation(self, rotation_id: str) -> None:
        """Delete a rotation.

        Args:
            rotation_id: Rotation ID
        """
        self.delete(f"/v1/rotation/{rotation_id}", resource_name="rotation")

    # --- Rotation Provider Instance methods ---

    def add_provider_instance_to_rotation(
        self,
        rotation_id: str,
        provider_instance_id: str,
        parent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a provider instance to a rotation.

        Args:
            rotation_id: Rotation ID
            provider_instance_id: Provider instance ID
            parent_id: Optional parent rotation provider instance ID

        Returns:
            New rotation provider instance information
        """
        data = {
            "rotation_provider_instance": {
                "rotation_id": rotation_id,
                "provider_instance_id": provider_instance_id,
            }
        }

        if parent_id:
            data["rotation_provider_instance"]["parent_id"] = parent_id

        return self.post(
            "/v1/rotation-provider",
            data,
            resource_name="rotation_provider_instance",
        )

    def get_rotation_provider_instance(
        self, rotation_provider_id: str
    ) -> Dict[str, Any]:
        """Get a rotation provider instance by ID.

        Args:
            rotation_provider_id: Rotation provider instance ID

        Returns:
            Rotation provider instance information
        """
        return self.get(
            f"/v1/rotation-provider/{rotation_provider_id}",
            resource_name="rotation_provider_instance",
        )

    def update_rotation_provider_instance(
        self, rotation_provider_id: str, parent_id: str
    ) -> Dict[str, Any]:
        """Update a rotation provider instance.

        Args:
            rotation_provider_id: Rotation provider instance ID
            parent_id: New parent rotation provider instance ID

        Returns:
            Updated rotation provider instance information
        """
        data = {"rotation_provider_instance": {"parent_id": parent_id}}
        return self.put(
            f"/v1/rotation-provider/{rotation_provider_id}",
            data,
            resource_name="rotation_provider_instance",
        )

    def list_provider_instances_in_rotation(
        self, rotation_id: str, offset: int = 0, limit: int = 100
    ) -> Dict[str, Any]:
        """List provider instances in a rotation.

        Args:
            rotation_id: Rotation ID
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of provider instances in the rotation
        """
        params = {
            "offset": offset,
            "limit": limit,
        }

        return self.get(
            f"/v1/rotation/{rotation_id}/provider",
            query_params=params,
            resource_name="rotation_provider_instances",
        )

    def remove_provider_instance_from_rotation(self, rotation_provider_id: str) -> None:
        """Remove a provider instance from a rotation.

        Args:
            rotation_provider_id: Rotation provider instance ID
        """
        self.delete(
            f"/v1/rotation-provider/{rotation_provider_id}",
            resource_name="rotation_provider_instance",
        )

    # --- Provider Extension Ability methods ---

    def add_ability_to_provider_extension(
        self, provider_extension_id: str, ability_id: str
    ) -> Dict[str, Any]:
        """Add an ability to a provider extension.

        Args:
            provider_extension_id: Provider extension ID
            ability_id: Ability ID

        Returns:
            New provider extension ability information
        """
        data = {
            "provider_extension_ability": {
                "provider_extension_id": provider_extension_id,
                "ability_id": ability_id,
            }
        }

        return self.post(
            "/v1/provider/extension/ability",
            data,
            resource_name="provider_extension_ability",
        )

    def get_provider_extension_ability(self, ability_id: str) -> Dict[str, Any]:
        """Get a provider extension ability by ID.

        Args:
            ability_id: Provider extension ability ID

        Returns:
            Provider extension ability information
        """
        return self.get(
            f"/v1/provider/extension/ability/{ability_id}",
            resource_name="provider_extension_ability",
        )

    def list_provider_extension_abilities(
        self, provider_extension_id: str, offset: int = 0, limit: int = 100
    ) -> Dict[str, Any]:
        """List abilities for a provider extension.

        Args:
            provider_extension_id: Provider extension ID
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of provider extension abilities
        """
        params = {
            "offset": offset,
            "limit": limit,
            "provider_extension_id": provider_extension_id,
        }

        return self.get(
            "/v1/provider/extension/ability",
            query_params=params,
            resource_name="provider_extension_abilities",
        )

    def remove_ability_from_provider_extension(self, ability_id: str) -> None:
        """Remove an ability from a provider extension.

        Args:
            ability_id: Provider extension ability ID
        """
        self.delete(
            f"/v1/provider/extension/ability/{ability_id}",
            resource_name="provider_extension_ability",
        )

    # --- Provider Instance Usage methods ---

    def record_provider_instance_usage(
        self, provider_instance_id: str, input_tokens: int, output_tokens: int
    ) -> Dict[str, Any]:
        """Record usage for a provider instance.

        Args:
            provider_instance_id: Provider instance ID
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used

        Returns:
            New provider instance usage information
        """
        data = {
            "provider_instance_usage": {
                "provider_instance_id": provider_instance_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        }

        return self.post(
            "/v1/provider-instance/usage",
            data,
            resource_name="provider_instance_usage",
        )

    def get_provider_instance_usage(self, usage_id: str) -> Dict[str, Any]:
        """Get a provider instance usage record by ID.

        Args:
            usage_id: Provider instance usage ID

        Returns:
            Provider instance usage information
        """
        return self.get(
            f"/v1/provider-instance/usage/{usage_id}",
            resource_name="provider_instance_usage",
        )

    def list_provider_instance_usage(
        self, provider_instance_id: str, offset: int = 0, limit: int = 100
    ) -> Dict[str, Any]:
        """List usage records for a provider instance.

        Args:
            provider_instance_id: Provider instance ID
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of provider instance usage records
        """
        params = {
            "offset": offset,
            "limit": limit,
            "provider_instance_id": provider_instance_id,
        }

        return self.get(
            "/v1/provider-instance/usage",
            query_params=params,
            resource_name="provider_instance_usages",
        )

    # --- Extension Instance Ability methods ---

    def set_extension_instance_ability(
        self,
        provider_instance_id: str,
        command_id: str,
        state: bool,
        forced: bool = False,
    ) -> Dict[str, Any]:
        """Set an ability for a provider instance.

        Args:
            provider_instance_id: Provider instance ID
            command_id: Command ID
            state: Enable/disable state
            forced: Whether this setting is forced

        Returns:
            New extension instance ability information
        """
        data = {
            "extension_instance_ability": {
                "provider_instance_id": provider_instance_id,
                "command_id": command_id,
                "state": state,
                "forced": forced,
            }
        }

        return self.post(
            "/v1/extension-instance/ability",
            data,
            resource_name="extension_instance_ability",
        )

    def get_extension_instance_ability(self, ability_id: str) -> Dict[str, Any]:
        """Get an extension instance ability by ID.

        Args:
            ability_id: Extension instance ability ID

        Returns:
            Extension instance ability information
        """
        return self.get(
            f"/v1/extension-instance/ability/{ability_id}",
            resource_name="extension_instance_ability",
        )

    def update_extension_instance_ability(
        self, ability_id: str, state: bool, forced: bool = None
    ) -> Dict[str, Any]:
        """Update an extension instance ability.

        Args:
            ability_id: Extension instance ability ID
            state: Enable/disable state
            forced: Whether this setting is forced

        Returns:
            Updated extension instance ability information
        """
        data = {"extension_instance_ability": {"state": state}}

        if forced is not None:
            data["extension_instance_ability"]["forced"] = forced

        return self.put(
            f"/v1/extension-instance/ability/{ability_id}",
            data,
            resource_name="extension_instance_ability",
        )

    def list_extension_instance_abilities(
        self, provider_instance_id: str, offset: int = 0, limit: int = 100
    ) -> Dict[str, Any]:
        """List abilities for a provider instance.

        Args:
            provider_instance_id: Provider instance ID
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of extension instance abilities
        """
        params = {
            "offset": offset,
            "limit": limit,
            "provider_instance_id": provider_instance_id,
        }

        return self.get(
            "/v1/extension-instance/ability",
            query_params=params,
            resource_name="extension_instance_abilities",
        )

    def delete_extension_instance_ability(self, ability_id: str) -> None:
        """Delete an extension instance ability.

        Args:
            ability_id: Extension instance ability ID
        """
        self.delete(
            f"/v1/extension-instance/ability/{ability_id}",
            resource_name="extension_instance_ability",
        )
