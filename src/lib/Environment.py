import os
from typing import Any, Dict, Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, field_validator

load_dotenv()


class AppSettings(BaseModel):
    ENVIRONMENT: Literal["local", "staging", "development", "production", "ci"] = (
        "local"
    )

    APP_NAME: str = "Server"
    APP_DESCRIPTION: str = "extensible server framework"
    APP_VERSION: str = "0.0.0"
    APP_REPOSITORY: str = "https://github.com/ZephyrexTechnologies/ServerFramework"
    APP_EXTENSIONS: str = ""

    ROOT_API_KEY: str = "n0ne"
    SERVER_URI: str = "http://localhost:1996"
    ALLOWED_DOMAINS: str = "*"

    DATABASE_TYPE: str = "sqlite"
    DATABASE_NAME: Optional[str] = "database"
    DATABASE_SSL: str = "disable"
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: str = "5432"
    DATABASE_USER: Optional[str] = None
    DATABASE_PASSWORD: str = "Password1!"

    LOCALIZATION: str = "en"
    GRAPHIQL: str = "true"
    LOG_FORMAT: str = "%(asctime)s | %(levelname)s | %(message)s"
    LOG_LEVEL: str = "DEBUG"
    REGISTRATION_DISABLED: str = "false"
    SEED_DATA: str = "true"

    ROOT_ID: str = "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF"
    SYSTEM_ID: str = "FFFFFFFF-FFFF-FFFF-AAAA-FFFFFFFFFFFF"
    TEMPLATE_ID: str = "FFFFFFFF-FFFF-FFFF-0000-FFFFFFFFFFFF"

    SUPERADMIN_ROLE_ID: str = "FFFFFFFF-0000-0000-FFFF-FFFFFFFFFFFF"
    ADMIN_ROLE_ID: str = "FFFFFFFF-0000-0000-AAAA-FFFFFFFFFFFF"
    USER_ROLE_ID: str = "FFFFFFFF-0000-0000-0000-FFFFFFFFFFFF"

    TZ: str = "UTC"
    UVICORN_WORKERS: Optional[str] = 1

    AGINYOURPC_API_KEY: str = "n0ne"
    AGINYOURPC_API_URI: str = "http://localhost:1691/v1/"
    AGINYOURPC_MAX_TOKENS: str = "16000"
    AGINYOURPC_VOICE: str = "DukeNukem"
    OPENAI_API_KEY: str = ""
    OPENAI_MAX_TOKENS: str = "128000"
    OPENAI_MODEL: str = "chatgpt-4o-latest"

    @field_validator("DATABASE_NAME", "DATABASE_USER", mode="before")
    @classmethod
    def set_db_defaults(cls, v, info):
        if v is None:
            return info.data.get("APP_NAME", "Server").lower()
        return v

    @field_validator("UVICORN_WORKERS", mode="before")
    @classmethod
    def set_uvicorn_workers(cls, v, info):
        if v is None:
            log_level = info.data.get("LOG_LEVEL", "DEBUG")
            return "5" if str(log_level).lower() == "debug" else "20"
        return v

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


settings = AppSettings.model_validate(os.environ)


def push_env_update(updates: Dict[str, Any]) -> None:
    """
    Update both os.environ and the cached settings object with new values.

    This is particularly useful for test environments where settings need to be
    modified after the initial load.

    Args:
        updates: Dictionary of environment variables to update
    """
    # Update os.environ first
    for key, value in updates.items():
        os.environ[key] = str(value)

    # Then update the settings object
    for key, value in updates.items():
        if hasattr(settings, key):
            setattr(settings, key, value)


def env(var: str) -> str:
    """
    Get environment variable with fallback to default values.
    For backward compatibility with existing code.
    """
    if hasattr(settings, var):
        return getattr(settings, var)
    return os.getenv(var, "")
