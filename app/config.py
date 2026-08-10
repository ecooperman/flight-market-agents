from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, loaded from environment variables / .env.

    Field names map case-insensitively to env vars, e.g. AMADEUS_CLIENT_ID
    -> amadeus_client_id. See .env.example for the full list.
    """

    amadeus_client_id: str = ""
    amadeus_client_secret: str = ""
    amadeus_base_url: str = "https://test.api.amadeus.com"
    use_mock_data: bool = True

    anthropic_api_key: str = ""
    agent_model: str = "claude-sonnet-5"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
