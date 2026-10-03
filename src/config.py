from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    groq_api_key: SecretStr = SecretStr("")
    groq_api_key2: SecretStr = SecretStr("")
    
    groq_model: str = ''
    fallback_model1: str = ''

    groq_model2: str = ''
    fallback_model2: str = ''

    rpm: int = 30
    max_concurrency: int = 2
    max_attempts: int = 4
    default_temperature: float = 0.1
    
    @property
    def cooldown(self) -> float:
        return 60 / self.rpm * self.max_concurrency
    

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_settings() -> Settings:
    return Settings()