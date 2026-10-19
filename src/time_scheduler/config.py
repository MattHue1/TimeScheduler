"""Application configuration loaded from environment variables and .env."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for Hermes, Google Calendar, and local storage."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    timescheduler_api_key: str = "change-me"
    hermes_api_url: str = "http://127.0.0.1:8642/v1"
    hermes_api_key: str = ""
    hermes_model: str = "hermes-agent"
    google_credentials_file: Path = Path("credentials.json")
    google_token_file: Path = Path("token.json")
    google_calendar_id: str = "primary"
    database_path: Path = Path("data/timescheduler.db")
    timescheduler_host: str = "127.0.0.1"
    timescheduler_port: int = 8081
    default_timezone: str = "America/Toronto"
    default_reminders_minutes: Annotated[list[int], NoDecode] = Field(
        default_factory=lambda: [30, 10]
    )

    @field_validator("default_reminders_minutes", mode="before")
    @classmethod
    def parse_reminders(cls, value: object) -> object:
        """Convert a comma-separated environment value into reminder minutes."""
        if isinstance(value, str):
            if value.strip().startswith("["):
                return json.loads(value)
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return one cached Settings instance for the process."""
    return Settings()
