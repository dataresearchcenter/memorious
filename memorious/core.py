import logging
import os

from anystore.functools import weakref_cache as cache
from anystore.logging import get_logger
from anystore.store import get_store
from ftm_lakehouse.repository.factories import get_tags as _get_tags
from ftm_lakehouse.storage.tags import TagStore
from servicelayer.cache import get_fakeredis, get_redis
from servicelayer.extensions import get_extensions
from servicelayer.logs import configure_logging
from servicelayer.rate_limit import RateLimit
from werkzeug.local import LocalProxy

from memorious.settings import Settings

log = get_logger(__name__)


@cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_conn():
    """Get cached Redis connection (or FakeRedis for testing)."""
    settings = get_settings()
    if settings.testing:
        return get_fakeredis()
    return get_redis()


@cache
def get_tags(dataset: str) -> TagStore:
    """Get tags store"""
    settings = get_settings()
    return _get_tags(dataset, settings.tags_uri, "memorious")


@cache
def get_cache():
    """Get cached store instance for runtime cache (sessions, etc.)."""
    settings = get_settings()
    return get_store(settings.cache_uri, raise_on_nonexist=False)


conn = LocalProxy(get_conn)
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
