"""
Memorious configuration using pydantic-settings.

All settings can be set via environment variables with MEMORIOUS_ prefix,
or via Docker secrets in /run/secrets directory.
"""

from importlib.metadata import version
from pathlib import Path

from anystore.settings import BaseSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict

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
        # secrets_dir_missing="ok",  # FIXME
        extra="ignore",
    )

    # Core configuration
    base_path: Path = Field(default_factory=lambda: Path.cwd() / "data")
    config_path: Path | None = Field(default=None)

    # Crawl behavior
    incremental: bool = Field(default=True)
    continue_on_error: bool = Field(default=False)
    expire: int = Field(default=1, description="Days until incremental crawl expires")

    # Rate limiting
    http_rate_limit: int = Field(default=120)

    # HTTP configuration
    http_cache: bool = Field(default=True)
    http_timeout: float = Field(default=30.0)
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US; rv:1.1) "
        f"memorious/{VERSION}"
    )

    cache_uri: str | None = Field(default="memory://")
    """Cache uri for runtime cache (defaults to in-memory)"""

    tags_uri: str | None = Field(default=None)
    """Tags storage for incremental crawling and HTTP caching (default in archive)"""
