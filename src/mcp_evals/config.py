"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_prefix="MCP_EVALS_",
        env_file=".env",
        extra="ignore",
    )

    log_level: str = "INFO"
    log_json: bool = False
    default_model: str = "gpt-4o-mini"
    eval_samples: int = 3
    pass_threshold: float = 0.8


def get_settings() -> Settings:
    return Settings()
