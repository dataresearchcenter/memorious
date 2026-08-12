"""Tests for standalone fetch functionality."""

from memorious import FetchClient, create_fetch_client, fetch
from memorious.logic.context import BaseContext, FetchContext
from memorious.logic.http import ContextHttpResponse


class TestFetchContext:
    """Tests for FetchContext class."""

    def test_fetch_context_creation(self):
        """Test FetchContext can be created without a crawler."""
        ctx = FetchContext(dataset="test_fetch")
        assert ctx.dataset == "test_fetch"
        assert ctx.incremental is True
        assert ctx.stealthy is False
        assert ctx.http is not None
        ctx.close()

    def test_fetch_context_with_options(self):
        """Test FetchContext accepts configuration options."""
        ctx = FetchContext(
            dataset="my_dataset",
            cache=False,
            proxies=["http://proxy1:8080"],
            timeout=30,
            stealthy=True,
            incremental=False,
        )
        assert ctx.dataset == "my_dataset"
        assert ctx.params.get("cache") is False
        assert ctx.params.get("http_proxies") == ["http://proxy1:8080"]
        assert ctx.params.get("http_timeout") == 30
        assert ctx.stealthy is True
        assert ctx.incremental is False
        ctx.close()

    def test_fetch_context_context_manager(self):
        """Test FetchContext works as context manager."""
        with FetchContext(dataset="ctx_mgr_test") as ctx:
            assert isinstance(ctx, FetchContext)
            assert ctx.dataset == "ctx_mgr_test"

    def test_fetch_context_inherits_base_context(self):
        """Test FetchContext inherits from BaseContext."""
        ctx = FetchContext()
        assert isinstance(ctx, BaseContext)
        ctx.close()

    def test_fetch_context_has_archive(self):
        """Test FetchContext has archive for storage."""
        with FetchContext(dataset="archive_test") as ctx:
            assert ctx.archive is not None

    def test_fetch_context_has_tags(self):
        """Test FetchContext has tags for incremental state."""
        with FetchContext(dataset="tags_test") as ctx:
            assert ctx.tags is not None

    def test_fetch_context_make_key(self):
        """Test FetchContext can create namespaced keys."""
        with FetchContext(dataset="key_test") as ctx:
            key = ctx.make_key("foo", "bar")
            assert key is not None
            assert "key_test" in key


class TestFetchClient:
    """Tests for FetchClient class."""

    def test_create_fetch_client(self):
        """Test create_fetch_client factory function."""
        client = create_fetch_client(dataset="factory_test")
        assert isinstance(client, FetchClient)
        assert client.context.dataset == "factory_test"
        client.close()

    def test_create_fetch_client_with_options(self):
        """Test create_fetch_client with configuration options."""
        client = create_fetch_client(
            dataset="options_test",
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
        with create_fetch_client(dataset="client_ctx_mgr") as client:
            assert isinstance(client, FetchClient)

    def test_fetch_client_has_context_property(self):
        """Test FetchClient exposes underlying context."""
        with create_fetch_client() as client:
            assert isinstance(client.context, FetchContext)


class TestFetchClientHttp:
    """Tests for FetchClient HTTP operations with httpbin."""

    def test_fetch_client_get(self, httpbin_url):
        """Test FetchClient.get() performs GET request."""
        with create_fetch_client(dataset="get_test") as client:
            response = client.get(f"{httpbin_url}/get")
            assert isinstance(response, ContextHttpResponse)
            assert response.ok
            assert response.status_code == 200

    def test_fetch_client_get_json(self, httpbin_url):
        """Test FetchClient.get() can parse JSON response."""
        with create_fetch_client(dataset="json_test") as client:
            response = client.get(f"{httpbin_url}/json")
            assert response.ok
            assert isinstance(response.json, dict)

    def test_fetch_client_get_with_params(self, httpbin_url):
        """Test FetchClient.get() with query parameters."""
        with create_fetch_client(dataset="params_test") as client:
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
        with create_fetch_client(dataset="headers_test") as client:
            response = client.get(
                f"{httpbin_url}/headers",
                headers={"X-Custom-Header": "custom-value"},
            )
            assert response.ok
            json_data = response.json
            assert json_data["headers"]["X-Custom-Header"] == "custom-value"

    def test_fetch_client_post(self, httpbin_url):
        """Test FetchClient.post() performs POST request."""
        with create_fetch_client(dataset="post_test") as client:
            response = client.post(
                f"{httpbin_url}/post",
                data={"key": "value"},
            )
            assert response.ok
            json_data = response.json
            assert json_data["form"]["key"] == "value"

    def test_fetch_client_post_json(self, httpbin_url):
        """Test FetchClient.post() with JSON data."""
        with create_fetch_client(dataset="post_json_test") as client:
            response = client.post(
                f"{httpbin_url}/post",
                json_data={"key": "value"},
            )
            assert response.ok
            json_data = response.json
            assert json_data["json"]["key"] == "value"

    def test_fetch_client_request_method(self, httpbin_url):
        """Test FetchClient.request() with custom method."""
        with create_fetch_client(dataset="request_test") as client:
            response = client.request("PUT", f"{httpbin_url}/put")
            assert response.ok
            assert response.status_code == 200

    def test_fetch_client_lazy_request(self, httpbin_url):
        """Test FetchClient with lazy request."""
        with create_fetch_client(dataset="lazy_test") as client:
            response = client.get(f"{httpbin_url}/get", lazy=True)
            assert response._response is None
            # Accessing response triggers the request
            assert response.response is not None
            assert response.ok


class TestFetchFunction:
    """Tests for fetch() one_shot function."""

    def test_fetch_simple(self, httpbin_url):
        """Test simple fetch() call."""
        response = fetch(f"{httpbin_url}/get", dataset="fetch_simple")
        assert isinstance(response, ContextHttpResponse)
        assert response.ok
        assert response.content_hash is not None

    def test_fetch_with_headers(self, httpbin_url):
        """Test fetch() with custom headers."""
        response = fetch(
            f"{httpbin_url}/headers",
            headers={"X-Test": "test-value"},
            dataset="fetch_headers",
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
            dataset="fetch_post",
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
            dataset="fetch_post_json",
        )
        assert response.ok
        json_data = response.json
        assert json_data["json"]["key"] == "value"

    def test_fetch_archives_content(self, httpbin_url):
        """Test that fetch() stores content in archive."""
        response = fetch(f"{httpbin_url}/json", dataset="fetch_archive")
        assert response.content_hash is not None
        # Content hash should be a SHA256 hex digest (64 chars)
        assert len(response.content_hash) == 64


class TestFetchCaching:
    """Tests for HTTP caching behavior."""

    def test_fetch_client_caching_enabled(self, httpbin_url):
        """Test that caching is enabled by default."""
        with create_fetch_client(dataset="cache_enabled") as client:
            assert client.context.http.cache is True

    def test_fetch_client_caching_disabled(self, httpbin_url):
        """Test that caching can be disabled."""
        with create_fetch_client(dataset="cache_disabled", cache=False) as client:
            assert client.context.http.cache is False


class TestFetchSessionPersistence:
    """Tests for session persistence (cookies)."""

    def test_fetch_client_cookies_persist(self, httpbin_url):
        """Test that cookies persist across requests."""
        with create_fetch_client(dataset="cookies_test") as client:
            # Set a cookie via httpbin
            client.get(f"{httpbin_url}/cookies/set/test_cookie/test_value")
            # Verify cookie is sent in subsequent request
            response = client.get(f"{httpbin_url}/cookies")
            assert response.ok
            json_data = response.json
            assert json_data["cookies"].get("test_cookie") == "test_value"


class TestFetchIncremental:
    """Tests for incremental skipping via manual cache keys."""

    def test_fetch_one_shot_skips_second_call(self, httpbin_url):
        """Test one-shot fetch() skips when cache_key was processed."""
        url = f"{httpbin_url}/get"
        response = fetch(url, dataset="inc_oneshot", cache_key="k1")
        assert response is not None
        assert response.ok
        response = fetch(url, dataset="inc_oneshot", cache_key="k1")
        assert response is None

    def test_fetch_client_get_skips_second_call(self, httpbin_url):
        """Test FetchClient.get() skips a processed cache_key."""
        url = f"{httpbin_url}/get"
        with create_fetch_client(dataset="inc_client") as client:
            response = client.get(url, cache_key="k1")
            assert response is not None
            assert response.ok
            assert client.get(url, cache_key="k1") is None
            # A different cache key still fetches
            response = client.get(url, cache_key="k2")
            assert response is not None
            assert response.ok

    def test_cache_key_without_incremental_never_skips(self, httpbin_url):
        """Test incremental=False disables skipping."""
        url = f"{httpbin_url}/get"
        with create_fetch_client(dataset="inc_disabled", incremental=False) as client:
            assert client.get(url, cache_key="k1") is not None
            assert client.get(url, cache_key="k1") is not None

    def test_no_cache_key_never_skips(self, httpbin_url):
        """Test requests without cache_key are never skipped."""
        url = f"{httpbin_url}/get"
        with create_fetch_client(dataset="inc_nokey") as client:
            assert client.get(url) is not None
            assert client.get(url) is not None

    def test_failed_request_not_marked(self, httpbin_url):
        """Test failed requests are not marked and get retried."""
        url = f"{httpbin_url}/status/404"
        with create_fetch_client(dataset="inc_failed") as client:
            response = client.get(url, cache_key="bad")
            assert response is not None
            assert not response.ok
            assert client.context.check_incremental("bad") is False
            # Not skipped on retry
            assert client.get(url, cache_key="bad") is not None

    def test_mark_complete_explicit(self, httpbin_url):
        """Test explicit mark_complete() for deferred marking."""
        url = f"{httpbin_url}/get"
        with create_fetch_client(dataset="inc_deferred") as client:
            client.mark_complete("k1")
            assert client.get(url, cache_key="k1") is None

    def test_cache_key_forces_eager(self, httpbin_url):
        """Test cache_key overrides lazy to mark reliably."""
        with create_fetch_client(dataset="inc_eager") as client:
            response = client.get(f"{httpbin_url}/get", lazy=True, cache_key="k1")
            assert response is not None
            assert response._response is not None
            assert client.context.check_incremental("k1") is True

    def test_context_check_and_mark(self):
        """Test check_incremental/mark_incremental on the context."""
        with FetchContext(dataset="inc_context") as ctx:
            assert ctx.check_incremental("foo") is False
            ctx.mark_incremental("foo")
            assert ctx.check_incremental("foo") is True

    def test_context_check_respects_incremental_flag(self):
        """Test check_incremental is False when incremental is off."""
        with FetchContext(dataset="inc_context_off", incremental=False) as ctx:
            ctx.mark_incremental("foo")
            assert ctx.check_incremental("foo") is False

    def test_context_skip_incremental_eager(self):
        """Test skip_incremental keeps its eager check-then-mark behavior."""
        with FetchContext(dataset="inc_context_skip") as ctx:
            assert ctx.skip_incremental("foo") is False
            assert ctx.skip_incremental("foo") is True


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
