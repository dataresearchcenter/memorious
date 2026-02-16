"""Tests for standalone fetch functionality."""

from memorious import FetchClient, create_fetch_client, fetch
from memorious.logic.context import BaseContext, FetchContext
from memorious.logic.http import ContextHttpResponse


class TestFetchContext:
    """Tests for FetchContext class."""

    def test_fetch_context_creation(self):
        """Test FetchContext can be created without a crawler."""
        ctx = FetchContext(dataset="test-fetch")
        assert ctx.dataset == "test-fetch"
        assert ctx.incremental is True
        assert ctx.stealthy is False
        assert ctx.http is not None
        ctx.close()

    def test_fetch_context_with_options(self):
        """Test FetchContext accepts configuration options."""
        ctx = FetchContext(
            dataset="my-dataset",
            cache=False,
            proxies=["http://proxy1:8080"],
            timeout=30,
            stealthy=True,
            incremental=False,
        )
        assert ctx.dataset == "my-dataset"
        assert ctx.params.get("cache") is False
        assert ctx.params.get("http_proxies") == ["http://proxy1:8080"]
        assert ctx.params.get("http_timeout") == 30
        assert ctx.stealthy is True
        assert ctx.incremental is False
        ctx.close()

    def test_fetch_context_context_manager(self):
        """Test FetchContext works as context manager."""
        with FetchContext(dataset="ctx-mgr-test") as ctx:
            assert isinstance(ctx, FetchContext)
            assert ctx.dataset == "ctx-mgr-test"

    def test_fetch_context_inherits_base_context(self):
        """Test FetchContext inherits from BaseContext."""
        ctx = FetchContext()
        assert isinstance(ctx, BaseContext)
        ctx.close()

    def test_fetch_context_has_archive(self):
        """Test FetchContext has archive for storage."""
        with FetchContext(dataset="archive-test") as ctx:
            assert ctx.archive is not None

    def test_fetch_context_has_tags(self):
        """Test FetchContext has tags for incremental state."""
        with FetchContext(dataset="tags-test") as ctx:
            assert ctx.tags is not None

    def test_fetch_context_make_key(self):
        """Test FetchContext can create namespaced keys."""
        with FetchContext(dataset="key-test") as ctx:
            key = ctx.make_key("foo", "bar")
            assert key is not None
            assert "key-test" in key


class TestFetchClient:
    """Tests for FetchClient class."""

    def test_create_fetch_client(self):
        """Test create_fetch_client factory function."""
        client = create_fetch_client(dataset="factory-test")
        assert isinstance(client, FetchClient)
        assert client.context.dataset == "factory-test"
        client.close()

    def test_create_fetch_client_with_options(self):
        """Test create_fetch_client with configuration options."""
        client = create_fetch_client(
            dataset="options-test",
            cache=False,
            stealthy=True,
            incremental=False,
        )
        assert client.context.params.get("cache") is False
        assert client.context.stealthy is True
        assert client.context.incremental is False
        client.close()

    def test_fetch_client_context_manager(self):
        """Test FetchClient works as context manager."""
        with create_fetch_client(dataset="client-ctx-mgr") as client:
            assert isinstance(client, FetchClient)

    def test_fetch_client_has_context_property(self):
        """Test FetchClient exposes underlying context."""
        with create_fetch_client() as client:
            assert isinstance(client.context, FetchContext)


class TestFetchClientHttp:
    """Tests for FetchClient HTTP operations with httpbin."""

    def test_fetch_client_get(self, httpbin_url):
        """Test FetchClient.get() performs GET request."""
        with create_fetch_client(dataset="get-test") as client:
            response = client.get(f"{httpbin_url}/get")
            assert isinstance(response, ContextHttpResponse)
            assert response.ok
            assert response.status_code == 200

    def test_fetch_client_get_json(self, httpbin_url):
        """Test FetchClient.get() can parse JSON response."""
        with create_fetch_client(dataset="json-test") as client:
            response = client.get(f"{httpbin_url}/json")
            assert response.ok
            assert isinstance(response.json, dict)

    def test_fetch_client_get_with_params(self, httpbin_url):
        """Test FetchClient.get() with query parameters."""
        with create_fetch_client(dataset="params-test") as client:
            response = client.get(
                f"{httpbin_url}/get",
                params={"foo": "bar", "baz": "qux"},
            )
            assert response.ok
            json_data = response.json
            assert json_data["args"]["foo"] == "bar"
            assert json_data["args"]["baz"] == "qux"

    def test_fetch_client_get_with_headers(self, httpbin_url):
        """Test FetchClient.get() with custom headers."""
        with create_fetch_client(dataset="headers-test") as client:
            response = client.get(
                f"{httpbin_url}/headers",
                headers={"X-Custom-Header": "custom-value"},
            )
            assert response.ok
            json_data = response.json
            assert json_data["headers"]["X-Custom-Header"] == "custom-value"

    def test_fetch_client_post(self, httpbin_url):
        """Test FetchClient.post() performs POST request."""
        with create_fetch_client(dataset="post-test") as client:
            response = client.post(
                f"{httpbin_url}/post",
                data={"key": "value"},
            )
            assert response.ok
            json_data = response.json
            assert json_data["form"]["key"] == "value"

    def test_fetch_client_post_json(self, httpbin_url):
        """Test FetchClient.post() with JSON data."""
        with create_fetch_client(dataset="post-json-test") as client:
            response = client.post(
                f"{httpbin_url}/post",
                json_data={"key": "value"},
            )
            assert response.ok
            json_data = response.json
            assert json_data["json"]["key"] == "value"

    def test_fetch_client_request_method(self, httpbin_url):
        """Test FetchClient.request() with custom method."""
        with create_fetch_client(dataset="request-test") as client:
            response = client.request("PUT", f"{httpbin_url}/put")
            assert response.ok
            assert response.status_code == 200

    def test_fetch_client_lazy_request(self, httpbin_url):
        """Test FetchClient with lazy request."""
        with create_fetch_client(dataset="lazy-test") as client:
            response = client.get(f"{httpbin_url}/get", lazy=True)
            assert response._response is None
            # Accessing response triggers the request
            assert response.response is not None
            assert response.ok


class TestFetchFunction:
    """Tests for fetch() one-shot function."""

    def test_fetch_simple(self, httpbin_url):
        """Test simple fetch() call."""
        response = fetch(f"{httpbin_url}/get", dataset="fetch-simple")
        assert isinstance(response, ContextHttpResponse)
        assert response.ok
        assert response.content_hash is not None

    def test_fetch_with_headers(self, httpbin_url):
        """Test fetch() with custom headers."""
        response = fetch(
            f"{httpbin_url}/headers",
            headers={"X-Test": "test-value"},
            dataset="fetch-headers",
        )
        assert response.ok
        json_data = response.json
        assert json_data["headers"]["X-Test"] == "test-value"

    def test_fetch_post(self, httpbin_url):
        """Test fetch() with POST method."""
        response = fetch(
            f"{httpbin_url}/post",
            method="POST",
            data={"field": "value"},
            dataset="fetch-post",
        )
        assert response.ok
        json_data = response.json
        assert json_data["form"]["field"] == "value"

    def test_fetch_post_json(self, httpbin_url):
        """Test fetch() with POST method and JSON data."""
        response = fetch(
            f"{httpbin_url}/post",
            method="POST",
            json_data={"key": "value"},
            dataset="fetch-post-json",
        )
        assert response.ok
        json_data = response.json
        assert json_data["json"]["key"] == "value"

    def test_fetch_archives_content(self, httpbin_url):
        """Test that fetch() stores content in archive."""
        response = fetch(f"{httpbin_url}/json", dataset="fetch-archive")
        assert response.content_hash is not None
        # Content hash should be a SHA256 hex digest (64 chars)
        assert len(response.content_hash) == 64


class TestFetchCaching:
    """Tests for HTTP caching behavior."""

    def test_fetch_client_caching_enabled(self, httpbin_url):
        """Test that caching is enabled by default."""
        with create_fetch_client(dataset="cache-enabled") as client:
            assert client.context.http.cache is True

    def test_fetch_client_caching_disabled(self, httpbin_url):
        """Test that caching can be disabled."""
        with create_fetch_client(dataset="cache-disabled", cache=False) as client:
            assert client.context.http.cache is False


class TestFetchSessionPersistence:
    """Tests for session persistence (cookies)."""

    def test_fetch_client_cookies_persist(self, httpbin_url):
        """Test that cookies persist across requests."""
        with create_fetch_client(dataset="cookies-test") as client:
            # Set a cookie via httpbin
            client.get(f"{httpbin_url}/cookies/set/test_cookie/test_value")
            # Verify cookie is sent in subsequent request
            response = client.get(f"{httpbin_url}/cookies")
            assert response.ok
            json_data = response.json
            assert json_data["cookies"].get("test_cookie") == "test_value"


class TestPackageLevelImports:
    """Tests for package-level imports."""

    def test_fetch_importable(self):
        """Test fetch is importable from memorious."""
        from memorious import fetch as fetch_func

        assert callable(fetch_func)

    def test_create_fetch_client_importable(self):
        """Test create_fetch_client is importable from memorious."""
        from memorious import create_fetch_client as factory_func

        assert callable(factory_func)

    def test_fetch_client_importable(self):
        """Test FetchClient is importable from memorious."""
        from memorious import FetchClient as ClientClass

        assert ClientClass is not None
