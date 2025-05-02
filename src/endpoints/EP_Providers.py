from typing import Optional

from fastapi import APIRouter, Depends, Query

from endpoints.AbstractEndpointRouter import AbstractEPRouter, AuthType
from lib.Environment import env
from logic.BLL_Auth import User, UserManager
from logic.BLL_Providers import (
    ProviderExtensionAbilityNetworkModel,
    ProviderExtensionNetworkModel,
    ProviderInstanceExtensionAbilityNetworkModel,
    ProviderInstanceNetworkModel,
    ProviderInstanceSettingNetworkModel,
    ProviderInstanceUsageNetworkModel,
    ProviderManager,
    ProviderNetworkModel,
    RotationNetworkModel,
    RotationProviderInstanceNetworkModel,
)


def get_provider_manager(
    user: User = Depends(UserManager.auth),
    target_user_id: Optional[str] = Query(
        None, description="Target user ID for admin operations"
    ),
    target_team_id: Optional[str] = Query(
        None, description="Target team ID for admin operations"
    ),
):
    """Get an initialized ProviderManager instance."""
    return ProviderManager(
        requester_id=user.id,
        target_user_id=target_user_id or user.id,
        target_team_id=target_team_id,
    )


# Factory for API Key authenticated routes
def get_provider_manager_api_key(
    target_user_id: Optional[str] = Query(
        None, description="Target user ID for admin operations"
    ),
    target_team_id: Optional[str] = Query(
        None, description="Target team ID for admin operations"
    ),
):
    """Get an initialized ProviderManager instance for API key authenticated routes."""
    # Use ROOT_ID as the requester for system operations
    effective_target_user_id = target_user_id or env("ROOT_ID")

    return ProviderManager(
        requester_id=env("ROOT_ID"),
        target_user_id=effective_target_user_id,
        target_team_id=target_team_id,
    )


# Example definitions for documentation
provider_extension_examples = {
    "get": {
        "extension": {
            "id": "e1x2t3n4-5678-90ab-cdef-123456789012",
            "name": "OpenAI Extension",
            "description": "Extension for OpenAI API integration",
            "version": "1.0.0",
            "entry_point": "openai_provider.py",
            "created_at": "2025-03-01T12:00:00.000Z",
            "created_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
            "updated_at": "2025-03-28T14:30:00.000Z",
            "updated_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
        }
    },
    "create": {
        "extension": {
            "name": "Anthropic Extension",
            "description": "Extension for Anthropic API integration",
            "version": "1.0.0",
            "entry_point": "anthropic_provider.py",
        }
    },
    "update": {
        "extension": {
            "name": "Updated OpenAI Extension",
            "description": "Updated extension for OpenAI API with additional features",
            "version": "1.1.0",
        }
    },
}

provider_examples = {
    "get": {
        "provider": {
            "id": "p1r2v3d4-5678-90ab-cdef-123456789012",
            "name": "OpenAI",
            "extension_id": "e1x2t3n4-5678-90ab-cdef-123456789012",
            "agent_settings_json": '{"api_base":"https://api.openai.com/v1"}',
            "extension": provider_extension_examples["get"]["extension"],
            "created_at": "2025-03-01T12:00:00.000Z",
            "created_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
            "updated_at": "2025-03-28T14:30:00.000Z",
            "updated_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
        }
    },
    "create": {
        "provider": {
            "name": "Anthropic",
            "extension_id": "e1x2t3n4-5678-90ab-cdef-123456789013",
            "agent_settings_json": '{"api_base":"https://api.anthropic.com/v1"}',
        }
    },
    "update": {
        "provider": {
            "name": "Updated OpenAI",
            "agent_settings_json": '{"api_base":"https://api.openai.com/v2"}',
        }
    },
}

provider_instance_examples = {
    "get": {
        "provider_instance": {
            "id": "i1n2s3t4-5678-90ab-cdef-123456789012",
            "name": "GPT-4 Production",
            "provider_id": "p1r2v3d4-5678-90ab-cdef-123456789012",
            "provider": {
                "id": "p1r2v3d4-5678-90ab-cdef-123456789012",
                "name": "Google",
            },
            "model_name": "gpt-4",
            "api_key": "••••••••••••••••••••••••••",  # Masked for security
            "team_id": "t1e2a3m4-5678-90ab-cdef-123456789012",
            "team": {
                "id": "t1e2a3m4-5678-90ab-cdef-123456789012",
                "name": "Engineering",
            },
            "created_at": "2025-03-01T12:00:00.000Z",
            "created_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
            "updated_at": "2025-03-28T14:30:00.000Z",
            "updated_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
        }
    },
    "create": {
        "provider_instance": {
            "name": "Claude 3 Opus",
            "provider_id": "p1r2v3d4-5678-90ab-cdef-123456789013",
            "model_name": "claude-3-opus-20240229",
            "api_key": "sk-ant-api03-examplekey123456789abcdefghijklmnopqrstuvwxyz",
            "team_id": "t1e2a3m4-5678-90ab-cdef-123456789012",
        }
    },
    "update": {
        "provider_instance": {
            "name": "Updated GPT-4",
            "model_name": "gpt-4-32k",
            "api_key": "sk-openai-newapikey123456789abcdefghijklmnopqrstuvwxyz",
        }
    },
}

provider_instance_setting_examples = {
    "get": {
        "provider_instance_setting": {
            "id": "s1e2t3t4-5678-90ab-cdef-123456789012",
            "provider_instance_id": "i1n2s3t4-5678-90ab-cdef-123456789012",
            "key": "temperature",
            "value": "0.7",
            "created_at": "2025-03-01T12:00:00.000Z",
            "created_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
            "updated_at": "2025-03-28T14:30:00.000Z",
            "updated_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
        }
    },
    "create": {
        "provider_instance_setting": {
            "provider_instance_id": "i1n2s3t4-5678-90ab-cdef-123456789012",
            "key": "max_tokens",
            "value": "4096",
        }
    },
    "update": {
        "provider_instance_setting": {
            "value": "8192",
        }
    },
}

rotation_examples = {
    "get": {
        "rotation": {
            "id": "r1o2t3a4-5678-90ab-cdef-123456789012",
            "name": "Production Models",
            "description": "Models approved for production use",
            "team_id": "t1e2a3m4-5678-90ab-cdef-123456789012",
            "team": {
                "id": "t1e2a3m4-5678-90ab-cdef-123456789012",
                "name": "Engineering",
            },
            "created_at": "2025-03-01T12:00:00.000Z",
            "created_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
            "updated_at": "2025-03-28T14:30:00.000Z",
            "updated_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
        }
    },
    "create": {
        "rotation": {
            "name": "Development Models",
            "description": "Models for testing and development",
            "team_id": "t1e2a3m4-5678-90ab-cdef-123456789012",
        }
    },
    "update": {
        "rotation": {
            "name": "Updated Production Models",
            "description": "Updated models approved for production use",
        }
    },
}

rotation_provider_examples = {
    "get": {
        "rotation_provider_instance": {
            "id": "r1p2i3d4-5678-90ab-cdef-123456789012",
            "rotation_id": "r1o2t3a4-5678-90ab-cdef-123456789012",
            "rotation": {
                "id": "r1o2t3a4-5678-90ab-cdef-123456789012",
                "name": "Production Models",
            },
            "provider_instance_id": "i1n2s3t4-5678-90ab-cdef-123456789012",
            "provider_instance": {
                "id": "i1n2s3t4-5678-90ab-cdef-123456789012",
                "name": "Production",
            },
            "parent_id": None,
            "created_at": "2025-03-01T12:00:00.000Z",
            "created_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
            "updated_at": "2025-03-28T14:30:00.000Z",
            "updated_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
        }
    },
    "create": {
        "rotation_provider_instance": {
            "rotation_id": "r1o2t3a4-5678-90ab-cdef-123456789012",
            "provider_instance_id": "i1n2s3t4-5678-90ab-cdef-123456789013",
            "parent_id": None,
        }
    },
    "update": {
        "rotation_provider_instance": {
            "parent_id": "r1p2i3d4-5678-90ab-cdef-123456789012",
        }
    },
}

provider_extension_ability_examples = {
    "get": {
        "provider_extension_ability": {
            "id": "a1b2i3l4-5678-90ab-cdef-123456789012",
            "provider_extension_id": "e1x2t3n4-5678-90ab-cdef-123456789012",
            "ability_id": "a1b2i3l4-5678-90ab-cdef-123456789012",
            "created_at": "2025-03-01T12:00:00.000Z",
            "created_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
            "updated_at": "2025-03-28T14:30:00.000Z",
            "updated_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
        }
    },
    "create": {
        "provider_extension_ability": {
            "provider_extension_id": "e1x2t3n4-5678-90ab-cdef-123456789012",
            "ability_id": "a1b2i3l4-5678-90ab-cdef-123456789013",
        }
    },
    "update": {
        "provider_extension_ability": {
            "provider_extension_id": "e1x2t3n4-5678-90ab-cdef-123456789013",
        }
    },
}

provider_instance_usage_examples = {
    "get": {
        "provider_instance_usage": {
            "id": "u1s2a3g4-5678-90ab-cdef-123456789012",
            "provider_instance_id": "i1n2s3t4-5678-90ab-cdef-123456789012",
            "input_tokens": 100,
            "output_tokens": 50,
            "created_at": "2025-03-01T12:00:00.000Z",
            "created_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
            "updated_at": "2025-03-28T14:30:00.000Z",
            "updated_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
        }
    },
    "create": {
        "provider_instance_usage": {
            "provider_instance_id": "i1n2s3t4-5678-90ab-cdef-123456789012",
            "input_tokens": 200,
            "output_tokens": 75,
        }
    },
    "update": {
        "provider_instance_usage": {
            "input_tokens": 300,
            "output_tokens": 100,
        }
    },
}

extension_instance_ability_examples = {
    "get": {
        "extension_instance_ability": {
            "id": "e1i2a3b4-5678-90ab-cdef-123456789012",
            "provider_instance_id": "i1n2s3t4-5678-90ab-cdef-123456789012",
            "command_id": "c1o2m3d4-5678-90ab-cdef-123456789012",
            "state": True,
            "forced": False,
            "created_at": "2025-03-01T12:00:00.000Z",
            "created_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
            "updated_at": "2025-03-28T14:30:00.000Z",
            "updated_by_user_id": "u1s2e3r4-5678-90ab-cdef-123456789012",
        }
    },
    "create": {
        "extension_instance_ability": {
            "provider_instance_id": "i1n2s3t4-5678-90ab-cdef-123456789012",
            "command_id": "c1o2m3d4-5678-90ab-cdef-123456789012",
            "state": True,
            "forced": False,
        }
    },
    "update": {
        "extension_instance_ability": {
            "state": False,
            "forced": True,
        }
    },
}

# Create provider extension router
provider_extension_router = AbstractEPRouter(
    prefix="/v1/provider/extension",
    tags=["Provider Extension Management"],
    manager_factory=get_provider_manager,
    manager_property="extension",
    network_model_cls=ProviderExtensionNetworkModel,
    resource_name="extension",
    example_overrides=provider_extension_examples,
)

# Create provider router (system entity requiring API key)
provider_router = AbstractEPRouter(
    prefix="/v1/provider",
    tags=["Provider Management"],
    manager_factory=get_provider_manager_api_key,
    network_model_cls=ProviderNetworkModel,
    resource_name="provider",
    example_overrides=provider_examples,
    auth_type=AuthType.API_KEY,
)

# Create provider instance router as a standalone router
provider_instance_router = AbstractEPRouter(
    prefix="/v1/provider-instance",
    tags=["Provider Instance Management"],
    manager_factory=get_provider_manager,
    manager_property="instance",
    network_model_cls=ProviderInstanceNetworkModel,
    resource_name="provider_instance",
    example_overrides=provider_instance_examples,
)

# Create provider instance nested router under provider
provider_instance_nested_router = provider_router.create_nested_router(
    parent_prefix="/v1/provider",
    parent_param_name="provider_id",
    child_resource_name="instance",
    manager_property="instance",
    tags=["Provider Instance Management"],
    example_overrides=provider_instance_examples,
)

# Create provider instance setting router as a standalone router
provider_instance_setting_router = AbstractEPRouter(
    prefix="/v1/provider-instance-setting",
    tags=["Provider Instance Settings"],
    manager_factory=get_provider_manager,
    manager_property="instance.setting",
    network_model_cls=ProviderInstanceSettingNetworkModel,
    resource_name="provider_instance_setting",
    example_overrides=provider_instance_setting_examples,
)

# Create provider instance setting nested router under provider instance
provider_instance_setting_nested_router = provider_instance_router.create_nested_router(
    parent_prefix="/v1/provider-instance",
    parent_param_name="instance_id",
    child_resource_name="setting",
    manager_property="instance.setting",
    tags=["Provider Instance Settings"],
    example_overrides=provider_instance_setting_examples,
)

# Create rotation router
rotation_router = AbstractEPRouter(
    prefix="/v1/rotation",
    tags=["Rotation Management"],
    manager_factory=get_provider_manager,
    manager_property="rotation",
    network_model_cls=RotationNetworkModel,
    resource_name="rotation",
    example_overrides=rotation_examples,
)

# Create rotation provider router as a standalone router
rotation_provider_router = AbstractEPRouter(
    prefix="/v1/rotation-provider",
    tags=["Rotation Provider Management"],
    manager_factory=get_provider_manager,
    manager_property="rotation.provider_instances",
    network_model_cls=RotationProviderInstanceNetworkModel,
    resource_name="rotation_provider_instance",
    example_overrides=rotation_provider_examples,
)

# Create rotation provider nested router under rotation
rotation_provider_nested_router = rotation_router.create_nested_router(
    parent_prefix="/v1/rotation",
    parent_param_name="rotation_id",
    child_resource_name="provider",
    manager_property="rotation.provider_instances",
    tags=["Rotation Provider Management"],
    example_overrides=rotation_provider_examples,
)

# Create provider extension ability router
provider_extension_ability_router = AbstractEPRouter(
    prefix="/v1/provider/extension/ability",
    tags=["Provider Extension Ability Management"],
    manager_factory=get_provider_manager,
    manager_property="extension.ability",
    network_model_cls=ProviderExtensionAbilityNetworkModel,
    resource_name="provider_extension_ability",
    example_overrides=provider_extension_ability_examples,
)

# Create provider instance usage router
provider_instance_usage_router = AbstractEPRouter(
    prefix="/v1/provider-instance/usage",
    tags=["Provider Instance Usage Management"],
    manager_factory=get_provider_manager,
    manager_property="instance.usage",
    network_model_cls=ProviderInstanceUsageNetworkModel,
    resource_name="provider_instance_usage",
    example_overrides=provider_instance_usage_examples,
)

# Create extension instance ability router
extension_instance_ability_router = AbstractEPRouter(
    prefix="/v1/extension-instance/ability",
    tags=["Extension Instance Ability Management"],
    manager_factory=get_provider_manager,
    manager_property="instance.ability",
    network_model_cls=ProviderInstanceExtensionAbilityNetworkModel,
    resource_name="extension_instance_ability",
    example_overrides=extension_instance_ability_examples,
)

# Combine all routers
router = APIRouter()

router.include_router(provider_extension_router)
router.include_router(provider_router)
router.include_router(provider_instance_router)
router.include_router(provider_instance_nested_router)
router.include_router(provider_instance_setting_router)
router.include_router(provider_instance_setting_nested_router)
router.include_router(rotation_router)
router.include_router(rotation_provider_router)
router.include_router(rotation_provider_nested_router)
router.include_router(provider_extension_ability_router)
router.include_router(provider_instance_usage_router)
router.include_router(extension_instance_ability_router)
