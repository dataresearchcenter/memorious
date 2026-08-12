"""Standalone HTTP fetching with archive and caching support.

This module provides factory functions for using memorious HTTP fetching
capabilities without requiring a full crawler context.

Example usage:

    # Simple one-shot fetch
    response = fetch("https://example.com/data.json")
    print(response.json)
    print(response.content_hash)  # Archived

    # With options
    response = fetch(
        "https://example.com/page",
        dataset="my-dataset",      # Archive namespace
        cache=True,                # HTTP caching (304s)
        proxies=["http://..."],    # Proxy rotation
        timeout=60,
        headers={"Authorization": "Bearer ..."},
    )

    # Reusable client (shares session/cookies)
    client = create_fetch_client(dataset="my-scraper")
    r1 = client.get("https://example.com/login")
    r2 = client.post("https://example.com/api", data={...})
    client.close()

    # Context manager
    with create_fetch_client(dataset="scraper") as client:
        response = client.get("https://example.com")

    # Incremental fetch with a manual cache key: the request is skipped
    # (returns None) if the key was already processed successfully.
    response = fetch("https://example.com/report.pdf", cache_key="report-2024")
    if response is None:
        ...  # already fetched in a previous run

    # Defer marking until downstream processing succeeded
    with create_fetch_client(dataset="scraper") as client:
        if not client.context.check_incremental("report-2024"):
            response = client.get("https://example.com/report.pdf")
            process(response)
            client.mark_complete("report-2024")
"""

from __future__ import annotations

from typing import Any

from memorious.logic.context import FetchContext
from memorious.logic.http import ContextHttpResponse


class FetchClient:
    """Reusable HTTP client with archive and caching support.

    This class wraps a FetchContext to provide a user-friendly API for
    HTTP fetching with session persistence (cookies, auth), archive storage,
    and HTTP caching.

    Example:
        >>> with create_fetch_client(dataset="my-scraper") as client:
        ...     response = client.get("https://example.com")
        ...     print(response.content_hash)
    """

    def __init__(self, context: FetchContext) -> None:
        """Initialize the fetch client with a context.

        Args:
            context: FetchContext providing HTTP, archive, and caching.
        """
        self._context = context

    @property
    def context(self) -> FetchContext:
        """Access the underlying FetchContext."""
        return self._context

    def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | list[tuple[str, Any]] | None = None,
        auth: tuple[str, str] | None = None,
        timeout: int | None = None,
        lazy: bool = False,
        cache_key: str | None = None,
    ) -> ContextHttpResponse | None:
        """Perform a GET request.

        Args:
            url: URL to fetch.
            headers: Optional HTTP headers.
            params: Optional query parameters.
            auth: Optional (username, password) tuple for basic auth.
            timeout: Optional request timeout in seconds.
            lazy: If True, don't execute request until response is accessed.
                Ignored when `cache_key` is given.
            cache_key: Optional incremental cache key, see `request`.

        Returns:
            ContextHttpResponse with content stored in archive, or None if
            the request was skipped incrementally.
        """
        return self.request(
            "GET",
            url,
            headers=headers,
            params=params,
            auth=auth,
            timeout=timeout,
            lazy=lazy,
            cache_key=cache_key,
        )

    def post(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | list[tuple[str, Any]] | None = None,
        auth: tuple[str, str] | None = None,
        timeout: int | None = None,
        lazy: bool = False,
        cache_key: str | None = None,
    ) -> ContextHttpResponse | None:
        """Perform a POST request.

        Args:
            url: URL to post to.
            data: Form data to post.
            json_data: JSON data to post (sets Content-Type automatically).
            headers: Optional HTTP headers.
            params: Optional query parameters.
            auth: Optional (username, password) tuple for basic auth.
            timeout: Optional request timeout in seconds.
            lazy: If True, don't execute request until response is accessed.
                Ignored when `cache_key` is given.
            cache_key: Optional incremental cache key, see `request`.

        Returns:
            ContextHttpResponse with content stored in archive, or None if
            the request was skipped incrementally.
        """
        return self.request(
            "POST",
            url,
            data=data,
            json_data=json_data,
            headers=headers,
            params=params,
            auth=auth,
            timeout=timeout,
            lazy=lazy,
            cache_key=cache_key,
        )

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | list[tuple[str, Any]] | None = None,
        auth: tuple[str, str] | None = None,
        timeout: int | None = None,
        lazy: bool = False,
        cache_key: str | None = None,
    ) -> ContextHttpResponse | None:
        """Perform an HTTP request with the specified method.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.).
            url: URL to request.
            headers: Optional HTTP headers.
            data: Form data for POST/PUT requests.
            json_data: JSON data for POST/PUT requests.
            params: Optional query parameters.
            auth: Optional (username, password) tuple for basic auth.
            timeout: Optional request timeout in seconds.
            lazy: If True, don't execute request until response is accessed.
                Ignored when `cache_key` is given.
            cache_key: Optional incremental cache key. If it has been marked
                as processed in a previous run, the request is skipped and
                None is returned. It is marked after a successful response.

        Returns:
            ContextHttpResponse with content stored in archive, or None if
            the request was skipped incrementally.
        """
        if cache_key and self._context.check_incremental(cache_key):
            self._context.log.info(
                "Skipping fetch (incremental)", cache_key=cache_key, url=url
            )
            return None
        if cache_key and lazy:
            self._context.log.debug("cache_key forces eager fetch", cache_key=cache_key)
            lazy = False
        response = self._context.http.request(
            method,
            url,
            headers=headers,
            data=data,
            json_data=json_data,
            params=params,
            auth=auth,
            timeout=timeout,
            lazy=lazy,
        )
        if cache_key and response.ok:
            self._context.mark_incremental(cache_key)
        return response

    def mark_complete(self, cache_key: str) -> None:
        """Mark an incremental cache key as processed.

        Use this to defer marking until downstream processing succeeded,
        instead of passing `cache_key` to the request methods.
        """
        self._context.mark_incremental(cache_key)

    def close(self) -> None:
        """Close the client and clean up resources."""
        self._context.close()

    def __enter__(self) -> "FetchClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def create_fetch_client(
    dataset: str = "fetch",
    cache: bool = True,
    proxies: str | list[str] | None = None,
    timeout: int | None = None,
    user_agent: str | None = None,
    stealthy: bool = False,
    incremental: bool = True,
) -> FetchClient:
    """Create a reusable fetch client with session persistence.

    The client shares session state (cookies, auth) across requests,
    making it suitable for multi-step interactions like login flows.

    Args:
        dataset: Dataset name for archive namespace (default: "fetch").
        cache: Enable HTTP caching with 304 responses (default: True).
        proxies: Proxy URL or list of proxy URLs for rotation.
        timeout: HTTP request timeout in seconds.
        user_agent: Custom User-Agent header.
        stealthy: Use random user agents (default: False).
        incremental: Enable incremental state tracking (default: True).

    Returns:
        FetchClient instance. Use as context manager or call close() when done.

    Example:
        >>> with create_fetch_client(dataset="my-scraper") as client:
        ...     # Login
        ...     client.post("https://example.com/login", data={"user": "..."})
        ...     # Fetch authenticated content
        ...     response = client.get("https://example.com/protected")
        ...     print(response.json)
    """
    context = FetchContext(
        dataset=dataset,
        cache=cache,
        proxies=proxies,
        timeout=timeout,
        user_agent=user_agent,
        stealthy=stealthy,
        incremental=incremental,
    )
    return FetchClient(context)


def fetch(
    url: str,
    method: str = "GET",
    data: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | list[tuple[str, Any]] | None = None,
    auth: tuple[str, str] | None = None,
    dataset: str = "fetch",
    cache: bool = True,
    proxies: str | list[str] | None = None,
    timeout: int | None = None,
    user_agent: str | None = None,
    stealthy: bool = False,
    incremental: bool = True,
    cache_key: str | None = None,
) -> ContextHttpResponse | None:
    """One-shot fetch with automatic resource cleanup.

    Fetches a URL and stores the content in the archive. The response
    content is fetched before cleanup to ensure it's available in the
    archive after the function returns.

    Args:
        url: URL to fetch.
        method: HTTP method (default: "GET").
        data: Form data for POST/PUT requests.
        json_data: JSON data for POST/PUT requests.
        headers: Optional HTTP headers.
        params: Optional query parameters.
        auth: Optional (username, password) tuple for basic auth.
        dataset: Dataset name for archive namespace (default: "fetch").
        cache: Enable HTTP caching with 304 responses (default: True).
        proxies: Proxy URL or list of proxy URLs for rotation.
        timeout: HTTP request timeout in seconds.
        user_agent: Custom User-Agent header.
        stealthy: Use random user agents (default: False).
        incremental: Enable incremental state tracking (default: True).
        cache_key: Optional incremental cache key. If it has been marked
            as processed in a previous run, the request is skipped and
            None is returned. It is marked after a successful response.

    Returns:
        ContextHttpResponse with content stored in archive, or None if
        the request was skipped incrementally.

    Example:
        >>> response = fetch("https://example.com/data.json")
        >>> print(response.json)
        >>> print(response.content_hash)  # Stored in archive
    """
    with create_fetch_client(
        dataset=dataset,
        cache=cache,
        proxies=proxies,
        timeout=timeout,
        user_agent=user_agent,
        stealthy=stealthy,
        incremental=incremental,
    ) as client:
        response = client.request(
            method,
            url,
            headers=headers,
            data=data,
            json_data=json_data,
            params=params,
            auth=auth,
            timeout=timeout,
            cache_key=cache_key,
        )
        if response is None:
            return None
        # Ensure content is fetched and archived before context closes
        response.fetch()
        return response
