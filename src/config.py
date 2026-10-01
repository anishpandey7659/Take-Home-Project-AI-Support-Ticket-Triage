from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    groq_api_key: SecretStr
    groq_api_key2: SecretStr
    groq_model: str
    groq_model2: str

    default_temperature: float = 0.1

    max_concurrency: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_settings() -> Settings:
    return Settings()