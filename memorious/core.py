import logging
import os

from servicelayer.archive import init_archive
from servicelayer.cache import get_fakeredis, get_redis
from servicelayer.extensions import get_extensions
from servicelayer.logs import configure_logging
from servicelayer.rate_limit import RateLimit
from servicelayer.tags import Tags
from werkzeug.local import LocalProxy

from memorious import settings

log = logging.getLogger(__name__)


def load_manager():
    if not hasattr(settings, "_manager"):
        from memorious.logic.manager import CrawlerManager

        settings._manager = CrawlerManager()
        if settings.CONFIG_PATH:
            settings._manager.load_path(settings.CONFIG_PATH)
    return settings._manager


def load_tags():
    if not hasattr(settings, "_tags"):
        settings._tags = Tags(settings.TAGS_TABLE, uri=settings.DATASTORE_URI)
    return settings._tags


def get_crawler():
    if not hasattr(settings, "_crawler"):
        return RuntimeError("No current crawler. Quitting.")
    return settings._crawler


def connect_redis():
    if settings.TESTING:
        return get_fakeredis()
    return get_redis()


manager = LocalProxy(load_manager)
tags = LocalProxy(load_tags)
conn = LocalProxy(connect_redis)
crawler = LocalProxy(get_crawler)

# File storage layer for blobs on local file system or S3
storage = init_archive()


def init_memorious():
    if settings.DEBUG:
        configure_logging(level=logging.DEBUG)
    else:
        configure_logging(level=logging.INFO)
    try:
        os.makedirs(settings.BASE_PATH)
    except Exception:
        pass
    for func in get_extensions("memorious.plugins"):
        func()


def get_rate_limit(resource, limit=100, interval=60, unit=1):
    return RateLimit(conn, resource, limit=limit, interval=interval, unit=unit)
