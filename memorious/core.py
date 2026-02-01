import logging
import os

from anystore.functools import weakref_cache as cache
from anystore.interface.rate_limit import RateLimit
from anystore.logging import configure_logging, get_logger
from anystore.store import get_store
from ftm_lakehouse.repository.factories import get_tags as _get_tags
from ftm_lakehouse.storage.tags import TagStore

from memorious.settings import Settings

log = get_logger(__name__)
settings = Settings()


@cache
def get_tags(dataset: str) -> TagStore:
    """Get tags store"""
    return _get_tags(dataset, settings.tags_uri, "memorious")


@cache
def get_cache():
    """Get cached store instance for runtime cache (sessions, etc.)."""
    return get_store(settings.cache_uri, raise_on_nonexist=False)


def init_memorious() -> None:
    """Initialize memorious with logging and plugins."""
    if settings.debug:
        configure_logging(level=logging.DEBUG)
    else:
        configure_logging(level=logging.INFO)
    try:
        os.makedirs(settings.base_path)
    except Exception:
        pass


def get_rate_limit(resource, limit=100, interval=60, unit=1):
    """Get a rate limiter for a resource."""
    return RateLimit(
        get_cache(),
        resource,
        limit=limit,
        interval=interval,
        unit=unit,
    )
