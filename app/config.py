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
