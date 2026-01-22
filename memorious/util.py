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


def make_url_key(
    url: str,
    method: str | None = "GET",
    content: bytes | None = None,
) -> str:
    """Make a unique url key that works in file-like systems.

    Creates a hierarchical key from URL components for easy prefix/glob cleanup.
    Query strings and optional content are hashed separately for uniqueness.

    Args:
        url: The URL to create a key for.
        method: HTTP method (default: GET).
        content: Optional request body content to include in key.

    Returns:
        A path-like key: method/netloc/path/[hash(query)]/[hash(content)]/hash(url)
    """
    parts = urlsplit(url)
    method = method or "GET"
    key_parts = [method.upper(), parts.netloc, parts.path]
    if parts.query:
        key_parts.append(hash_data(parts.query))
    if content:
        key_parts.append(hash_data(content))
    key_parts.append(hash_data(url))
    return join_relpaths(*key_parts)
