from datetime import date

from pydantic_settings import BaseSettings, SettingsConfigDict


class Env(BaseSettings):
    """Runtime env vars"""

    model_config = SettingsConfigDict(
        env_file=".env",
        secrets_dir="/run/secrets",
        # secrets_dir_missing="ok",  # FIXME
        extra="ignore",
    )

    full_run: bool = False
    start_date: date | None = None
    end_date: date | None = None
