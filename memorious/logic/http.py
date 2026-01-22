"""HTTP client with caching and lazy evaluation using httpx."""

from __future__ import annotations

import cgi
import io
import json
import random
from datetime import datetime, timedelta, timezone
from functools import cached_property
from hashlib import sha1
from pathlib import Path
from typing import TYPE_CHECKING, Any, ContextManager
from urllib.parse import unquote, urlparse

import httpx
from banal import is_mapping
from lxml import etree, html
from normality import guess_file_encoding, stringify
from rigour.mime import normalize_mimetype, parse_mimetype

from memorious.core import get_rate_limit, settings
from memorious.exc import ParseError
from memorious.helpers.dates import parse_date
from memorious.helpers.ua import UserAgent
from memorious.logic.mime import NON_HTML
from memorious.model.session import SessionModel
from memorious.util import make_url_key

if TYPE_CHECKING:
    from memorious.logic.context import Context


class ContextHttp:
    """HTTP client with session management and caching."""

    STATE_SESSION = "_http"

    def __init__(self, context: Context) -> None:
        self.context = context

        self.cache = settings.http_cache
        if "cache" in context.params:
            self.cache = context.params.get("cache")

        self._client: httpx.Client | None = None
        self._session_state: SessionModel | None = self._load_session()

    def _get_proxy(self) -> str | None:
        """Get a proxy URL from params or settings.

        If multiple proxies are configured, returns a random one.
        Stage params take precedence over global settings.
        """
        proxies = self.context.params.get("http_proxies") or settings.http_proxies
        if not proxies:
            return None
        if isinstance(proxies, str):
            return proxies
        return random.choice(proxies)

    @property
    def client(self) -> httpx.Client:
        """Get or create the httpx Client with session state applied."""
        if self._client is None:
            proxy = self._get_proxy()

            self._client = httpx.Client(
                verify=False,
                follow_redirects=True,
                timeout=settings.http_timeout,
                proxy=proxy,
            )
            self._client.headers["User-Agent"] = settings.user_agent
            if self.context.crawler.stealthy:
                self._client.headers["User-Agent"] = UserAgent().random()

            # Apply saved session state (cookies, headers)
            if self._session_state:
                self._session_state.apply_to_client(self._client)

        return self._client

    def reset(self) -> httpx.Client:
        """Reset the HTTP client, clearing all session state."""
        if self._client:
            self._client.close()
        self._client = None
        self._session_state = None
        return self.client

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        auth: tuple[str, str] | None = None,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | list[tuple[str, Any]] | None = None,
        json_data: dict[str, Any] | None = None,
        allow_redirects: bool = True,
        timeout: int | None = None,
        lazy: bool = False,
    ) -> ContextHttpResponse:
        if timeout is None:
            timeout = settings.http_timeout
        headers = headers or {}
        if is_mapping(params):
            params = list(params.items())

        method = method.upper().strip()

        # Build httpx Request
        # Note: httpx Request doesn't take auth directly - we pass it to send()
        request = httpx.Request(
            method,
            url,
            params=params,
            headers=headers,
            data=data,
            json=json_data,
        )

        response = ContextHttpResponse(
            self,
            request=request,
            auth=auth,
            follow_redirects=allow_redirects,
            timeout=timeout,
        )
        if not lazy:
            response.fetch()
        return response

    def get(self, url: str, **kwargs: Any) -> ContextHttpResponse:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> ContextHttpResponse:
        return self.request("POST", url, **kwargs)

    def rehash(self, data: dict[str, Any]) -> ContextHttpResponse:
        return ContextHttpResponse.deserialize(self, data)

    def _get_session_key(self) -> str:
        """Get deterministic session cache key for this crawler/run."""
        return self.context.make_key("session", self.context.run_id)

    def _load_session(self) -> SessionModel | None:
        """Load session from cache using pydantic model."""
        # Use deterministic key based on crawler name and run_id
        # This allows session to be shared across stages without passing state
        key = self._get_session_key()
        return self.context.cache.get(key, model=SessionModel)

    def save(self) -> None:
        """Save session to cache using pydantic model."""
        key = self._get_session_key()
        session_state = SessionModel.from_client(self.client)
        self.context.cache.put(key, session_state, model=SessionModel)


class ContextHttpResponse:
    """Handle a cached and managed HTTP response.

    This is a wrapper for ``httpx`` HTTP response which adds several
    aspects:

    * Uses HTTP caching against the archive when configured to do so.
    * Will evaluate lazily in order to allow fast web crawling.
    * Allow responses to be serialized between crawler operations.
    """

    CACHE_METHODS = ["GET", "HEAD"]

    def __init__(
        self,
        http: ContextHttp,
        request: httpx.Request | None = None,
        auth: tuple[str, str] | None = None,
        follow_redirects: bool = True,
        timeout: int | None = None,
    ) -> None:
        self.http = http
        self.context = http.context
        self.request = request
        self.auth = auth
        self.follow_redirects = follow_redirects
        self.timeout = timeout
        self._response: httpx.Response | None = None
        self._status_code: int | None = None
        self._url: str | None = None
        self._request_id: str | None = None
        self._headers: httpx.Headers | dict[str, str] | None = None
        self._encoding: str | None = None
        self._content_hash: str | None = None
        self.retrieved_at: str | None = None

    @property
    def use_cache(self) -> bool:
        """Check if caching should be used for this request."""
        if not self.http.cache:
            return False
        if self.request is not None:
            return self.request.method in self.CACHE_METHODS
        return True

    @property
    def response(self) -> httpx.Response | None:
        """Get the underlying httpx Response, triggering the HTTP request if needed."""
        if self._response is None and self.request is not None:
            request = self.request
            existing = None
            if self.use_cache and self.request_id:
                existing = self.context.get_tag(self.request_id)

            # Build headers for conditional request
            extra_headers: dict[str, str] = {}
            if existing is not None:
                headers = existing.get("headers", {})
                last_modified = headers.get("last-modified")
                if last_modified:
                    extra_headers["If-Modified-Since"] = last_modified

                etag = headers.get("etag")
                if etag:
                    extra_headers["If-None-Match"] = etag

            self._rate_limit(str(request.url))

            # Merge extra headers with request headers for conditional requests
            # and keeping auth headers intact
            merged_headers = dict(request.headers)
            merged_headers.update(extra_headers)
            request = self.http.client.build_request(
                request.method,
                request.url,
                headers=merged_headers,
                content=request.content,
            )

            response = self.http.client.send(
                request,
                stream=True,
                auth=self.auth,
                follow_redirects=self.follow_redirects,
            )

            if existing is not None and response.status_code == 304:
                self.context.log.info(
                    "Using cached HTTP response", url=str(response.url)
                )
                response.close()
                self.apply_data(existing)
            else:
                self._response = response

            # Update the serialized session with cookies etc.
            self.http.save()
        return self._response

    def fetch(self) -> str | None:
        """Fetch response and store in archive. Returns content_hash."""
        if self._content_hash is not None:
            return self._content_hash

        if self.response is None:
            return None

        # Stream response, computing hash and collecting chunks
        content_hash = sha1()
        chunks: list[bytes] = []
        for chunk in self.response.iter_bytes(chunk_size=8192):
            content_hash.update(chunk)
            chunks.append(chunk)

        # Store raw bytes in archive
        self._content_hash = content_hash.hexdigest()
        self.context.store_data(b"".join(chunks), checksum=self._content_hash)

        # Cache HTTP metadata via tags for conditional requests
        if self.http.cache and self.ok and self.request_id:
            self.context.set_tag(self.request_id, self.serialize())

        self.retrieved_at = datetime.now(timezone.utc).isoformat()
        return self._content_hash

    def _rate_limit(self, url: str) -> None:
        """Apply rate limiting for the request URL."""
        resource = urlparse(url).netloc or url
        limit = self.context.get("http_rate_limit", settings.http_rate_limit)
        limit = limit / 60  # per minute to per second for stricter enforcement
        rate_limit = get_rate_limit(resource, limit=limit, interval=1, unit=1)
        self.context.enforce_rate_limit(rate_limit)

    @property
    def url(self) -> str | None:
        if self._response is not None:
            return str(self._response.url)  # httpx.URL -> str
        if self.request is not None:
            return str(self.request.url)
        return self._url

    @property
    def request_id(self) -> str | None:
        if self._request_id is not None:
            return self._request_id
        if self.request is not None:
            return make_url_key(
                str(self.request.url),
                method=self.request.method,
                content=self.request.content or None,
            )
        return None

    @property
    def status_code(self) -> int | None:
        if self._status_code is None and self.response is not None:
            self._status_code = self.response.status_code
        return self._status_code

    @property
    def headers(self) -> httpx.Headers | dict[str, str]:
        """Get response headers (case-insensitive via httpx.Headers or lowercase dict)."""
        if self._headers is None and self.response:
            self._headers = self.response.headers
        return self._headers or {}

    @property
    def last_modified(self) -> str | None:
        last_modified_header = self.headers.get("last-modified")
        if last_modified_header is not None:
            # Tue, 15 Nov 1994 12:45:26 GMT
            last_modified = parse_date(last_modified_header)
            if last_modified is not None:
                # Make timezone-aware comparison
                now = datetime.now(timezone.utc)
                lm_aware = last_modified.replace(tzinfo=timezone.utc)
                if lm_aware < now + timedelta(seconds=30):
                    return last_modified.strftime("%Y-%m-%dT%H:%M:%S%z")
        return None

    @property
    def encoding(self) -> str | None:
        """Detect content encoding from headers or content."""
        if self._encoding is None:
            mime = parse_mimetype(self.headers.get("content-type"))
            self._encoding = mime.charset
        if self._encoding is None:
            # Use raw bytes for encoding detection
            raw = self.raw
            if raw:
                self._encoding = guess_file_encoding(io.BytesIO(raw))
        return self._encoding

    @encoding.setter
    def encoding(self, encoding: str) -> None:
        self._encoding = encoding

    @property
    def content_hash(self) -> str | None:
        if self._content_hash is None:
            self.fetch()
        return self._content_hash

    @property
    def content_type(self) -> str | None:
        content_type = self.headers.get("content-type")
        return normalize_mimetype(content_type)

    @property
    def file_name(self) -> str | None:
        disposition = self.headers.get("content-disposition")
        file_name = None
        if disposition is not None:
            _, options = cgi.parse_header(disposition)
            filename = options.get("filename") or ""
            file_name = stringify(unquote(filename))
        return file_name

    @property
    def ok(self) -> bool:
        if self.status_code is None:
            return False
        return self.status_code < 400

    @cached_property
    def raw(self) -> bytes | None:
        """Get raw response content from archive."""
        if self.content_hash is None:
            return None
        with self.context.open(self.content_hash) as fh:
            return fh.read()

    @cached_property
    def text(self) -> str | None:
        """Get response content as text."""
        if self.raw is None:
            return None
        return self.raw.decode(self.encoding or "utf-8", "replace")

    @cached_property
    def html(self):
        """Parse HTML content."""
        if self.content_hash is None:
            return None
        if self.content_type in NON_HTML:
            return None
        text = self.text
        if text is None or not len(text):
            return None
        try:
            return html.fromstring(text)
        except ValueError as ve:
            if "encoding declaration" in str(ve):
                # Need file-like object for lxml
                with self.context.open(self.content_hash) as fh:
                    return html.parse(fh)
        except (etree.ParserError, etree.ParseError):
            pass
        return None

    @cached_property
    def xml(self):
        """Parse XML content."""
        if self.content_hash is None:
            return None
        parser = etree.XMLParser(
            ns_clean=True, recover=True, resolve_entities=False, no_network=True
        )
        with self.context.open(self.content_hash) as fh:
            return etree.parse(fh, parser=parser)

    @cached_property
    def json(self) -> Any:
        """Parse JSON content."""
        if self.raw is None:
            raise ParseError("Cannot parse failed download.")
        return json.loads(self.raw)

    def local_path(self) -> ContextManager[Path]:
        """Provide content as a local file path (for operations that need file paths)."""
        if self.content_hash is None:
            raise ValueError("No content available")
        return self.context.local_path(self.content_hash)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self) -> None:
        if self._response is not None:
            self._response.close()

    def serialize(self) -> dict[str, Any]:
        """Serialize response metadata for storage between stages."""
        self.fetch()
        data = {
            "request_id": self.request_id,
            "status_code": self.status_code,
            "url": self.url,
            "content_hash": self.content_hash,
            "encoding": self._encoding,
            "headers": dict(self.headers),
            "retrieved_at": self.retrieved_at,
        }
        if self.last_modified is not None:
            data["modified_at"] = self.last_modified
        return data

    def apply_data(self, data: dict[str, Any]) -> None:
        """Apply serialized data to restore response state."""
        self._status_code = data.get("status_code")
        self._url = data.get("url")
        self._request_id = data.get("request_id")
        self._encoding = data.get("encoding")
        self._content_hash = data.get("content_hash")
        self.retrieved_at = data.get("retrieved_at")
        # Store headers as lowercase dict (httpx.Headers can't handle unicode)
        self._headers = {k.lower(): v for k, v in data.get("headers", {}).items()}

    @classmethod
    def deserialize(
        cls, http: ContextHttp, data: dict[str, Any]
    ) -> ContextHttpResponse:
        """Create a response from serialized data."""
        obj = cls(http)
        obj.apply_data(data)
        return obj

    def __repr__(self) -> str:
        return "<ContextHttpResponse(%s,%s)>" % (self.url, self._content_hash)
