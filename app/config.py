import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, loaded from environment variables / .env.

    Field names map case-insensitively to env vars, e.g. SERPAPI_KEY ->
    serpapi_key. See .env.example for the full list.
    """

    serpapi_key: str = ""
    use_mock_data: bool = True

    anthropic_api_key: str = ""
    agent_model: str = "claude-sonnet-5"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()


# "local" (default, for a dev machine) or "production" (set once, droplet-wide, via systemd's
# DefaultEnvironment - see DEPLOYMENT.md). Picks which shared-assets host the page loads its theme
# from, so local iteration never means hand-editing a URL.
ENV = os.environ.get("APP_ENV", "local")
SHARED_ASSETS_BASE = "https://static.evancooperman.com" if ENV == "production" else "http://127.0.0.1:8070"
