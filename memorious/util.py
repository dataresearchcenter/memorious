import os
from urllib.parse import urlsplit
from uuid import uuid4

from anystore.util import join_relpaths
from banal import hash_data


def random_filename(path=None):
    """Make a UUID-based file name which is extremely unlikely
    to exist already."""
    filename = uuid4().hex
    if path is not None:
        filename = os.path.join(path, filename)
    return filename


def make_url_key(url: str, method: str | None = "GET") -> str:
    """Make a unique url key that works in file-like systems for easy prefix or
    glob based cleanup"""
    parts = urlsplit(url)
    method = method or "GET"
    return join_relpaths(method.upper(), parts.netloc, parts.path, hash_data(url))
