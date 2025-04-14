import os

from dotenv import load_dotenv

load_dotenv()

default_values = {
    "APP_NAME": "Zephyrex",
    "ROOT_API_KEY": "n0ne",
    "SERVER_URI": "http://localhost:1996",
    "ALLOWED_DOMAINS": "*",
    "DATABASE_TYPE": "sqlite",
    "DATABASE_NAME": "zephyrex",
    "DATABASE_SSL": "disable",
    "DATABASE_HOST": "localhost",
    "DATABASE_PORT": "5432",
    "DATABASE_USER": "zephyrex",
    "DATABASE_PASSWORD": "Password1!",
    "LOCALIZATION": "en",
    "GRAPHIQL": "true",
    "LOG_FORMAT": "%(asctime)s | %(levelname)s | %(message)s",
    "LOG_LEVEL": "DEBUG",
    "REGISTRATION_DISABLED": "false",
    "SEED_DATA": "true",
    "ROOT_ID": "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
    "SYSTEM_ID": "FFFFFFFF-FFFF-FFFF-AAAA-FFFFFFFFFFFF",
    "TEMPLATE_ID": "FFFFFFFF-FFFF-FFFF-0000-FFFFFFFFFFFF",
    "TZ": "UTC",
    "UVICORN_WORKERS": (
        "5" if str(os.getenv("LOG_LEVEL", "DEBUG")).lower() == "debug" else "20"
    ),
}


def env(var: str) -> str:
    return os.getenv(var, default_values[var] if var in default_values else "")
