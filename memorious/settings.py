"""
Memorious configuration using pydantic-settings.

All settings can be set via environment variables with MEMORIOUS_ prefix,
or via Docker secrets in /run/secrets directory.
"""

from functools import cached_property
from importlib.metadata import version
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from servicelayer import settings as sls

# Get version from package metadata
try:
    VERSION = version("memorious")
except Exception:
    VERSION = "0.0.0"


class Settings(BaseSettings):
    """
    Memorious configuration using pydantic-settings.

    Settings are loaded from (in order of priority, highest first):
    1. Environment variables with MEMORIOUS_ prefix
    2. .env file
    3. Docker secrets in /run/secrets directory

    For Docker secrets, create a secret file named after the setting
    (with memorious_ prefix), e.g., /run/secrets/memorious_tags_uri
    """

    model_config = SettingsConfigDict(
        env_prefix="memorious_",
        env_nested_delimiter="__",
        env_file=".env",
        secrets_dir="/run/secrets",
        extra="ignore",
    )

    # Core configuration
    app_name: str = Field(default="memorious")
    debug: bool = Field(default=False)
    testing: bool = Field(default=False, alias="testing")
    base_path: Path = Field(default_factory=lambda: Path.cwd() / "data")
    config_path: Path | None = Field(default=None)

    # Crawl behavior
    incremental: bool = Field(default=True)
    continue_on_error: bool = Field(default=False)
    expire: int = Field(default=1, description="Days until incremental crawl expires")

    # Rate limiting
    db_rate_limit: int = Field(default=6000)
    http_rate_limit: int = Field(default=120)
    max_queue_length: int = Field(default=50000)

    # HTTP configuration
    http_cache: bool = Field(default=True)
    http_timeout: float = Field(default=30.0)
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US; rv:1.1) "
        f"aleph.memorious/{VERSION}"
    )

    tags_uri: str | None = Field(default=None)
    """Tags storage for incremental crawling and HTTP caching."""

    @cached_property
    def archive_path(self) -> Path:
        return self.base_path / "archive"

    @cached_property
    def resolved_tags_uri(self) -> str:
        """Tags store URI, defaults to SQLite in base_path."""
        if self.tags_uri:
            return self.tags_uri
        return f"sqlite:///{self.base_path / 'tags.sqlite3'}"

    def init_servicelayer(self) -> None:
        """Initialize servicelayer settings from memorious settings."""
        if not sls.ARCHIVE_PATH:
            sls.ARCHIVE_PATH = str(self.archive_path)
