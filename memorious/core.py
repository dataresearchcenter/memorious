import logging
import os

from anystore.tags import Tags
from anystore.tags import get_tags as _get_tags
from servicelayer.archive import init_archive
from servicelayer.cache import get_fakeredis, get_redis
from servicelayer.extensions import get_extensions
from servicelayer.logs import configure_logging
from servicelayer.rate_limit import RateLimit
from werkzeug.local import LocalProxy

from memorious.settings import Settings

log = logging.getLogger(__name__)


def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.init_servicelayer()
    return settings


def get_conn():
    """Get cached Redis connection (or FakeRedis for testing)."""
    settings = get_settings()
    if settings.testing:
        return get_fakeredis()
    return get_redis()


def get_storage():
    """Get cached archive storage."""
    settings = get_settings()
    return init_archive(path=str(settings.archive_path))


def get_tags() -> Tags:
    """Get cached Tags instance."""
    settings = get_settings()
    # Ensure base_path exists for SQLite tags database
    try:
        os.makedirs(settings.base_path, exist_ok=True)
    except Exception:
        pass
    return _get_tags(settings.resolved_tags_uri)


tags = LocalProxy(get_tags)
conn = LocalProxy(get_conn)
storage = LocalProxy(get_storage)
settings = LocalProxy(get_settings)


def init_memorious() -> None:
    """Initialize memorious with logging and plugins."""
    settings = get_settings()
    if settings.debug:
        configure_logging(level=logging.DEBUG)
    else:
        configure_logging(level=logging.INFO)
    try:
        os.makedirs(settings.base_path)
    except Exception:
        pass
    for func in get_extensions("memorious.plugins"):
        func()


def get_rate_limit(resource, limit=100, interval=60, unit=1):
    """Get a rate limiter for a resource."""
    return RateLimit(conn, resource, limit=limit, interval=interval, unit=unit)
