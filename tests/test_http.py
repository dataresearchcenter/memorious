import httpx
from lxml import etree, html

from memorious.logic.http import ContextHttpResponse
from memorious.model.session import CookieModel, SessionModel


class TestSessionModel:
    def test_session_model_serialization(self):
        """Test SessionModel can serialize and deserialize."""
        model = SessionModel(
            cookies=[CookieModel(name="session_id", value="abc123")],
            headers={"X-Custom": "value"},
            auth_header="Basic dXNlcjpwYXNzd29yZA==",
        )
        # Serialize to dict
        data = model.model_dump()
        assert len(data["cookies"]) == 1
        assert data["cookies"][0]["name"] == "session_id"
        assert data["cookies"][0]["value"] == "abc123"
        assert data["headers"] == {"X-Custom": "value"}
        assert data["auth_header"] == "Basic dXNlcjpwYXNzd29yZA=="

        # Deserialize from dict
        restored = SessionModel.model_validate(data)
        assert len(restored.cookies) == 1
        assert restored.cookies[0].name == "session_id"
        assert restored.cookies[0].value == "abc123"
        assert restored.headers == {"X-Custom": "value"}
        assert restored.auth_header == "Basic dXNlcjpwYXNzd29yZA=="

    def test_session_model_from_client(self):
        """Test extracting session state from httpx.Client."""
        client = httpx.Client()
        client.cookies.set("test_cookie", "cookie_value")
        client.headers["X-Test-Header"] = "header_value"
        client.auth = ("testuser", "testpass")

        model = SessionModel.from_client(client)
        # Find cookie by name
        cookie = next((c for c in model.cookies if c.name == "test_cookie"), None)
        assert cookie is not None
        assert cookie.value == "cookie_value"
        assert model.headers.get("x-test-header") == "header_value"
        assert model.auth_header is not None
        assert model.auth_header.startswith("Basic ")

        client.close()

    def test_session_model_apply_to_client(self):
        """Test applying session state to httpx.Client."""
        model = SessionModel(
            cookies=[CookieModel(name="restored_cookie", value="restored_value")],
            headers={"X-Restored": "restored_header"},
            auth_header="Basic dXNlcjpwYXNzd29yZA==",
        )

        client = httpx.Client()
        model.apply_to_client(client)

        assert client.cookies.get("restored_cookie") == "restored_value"
        assert client.headers.get("X-Restored") == "restored_header"
        assert client.headers.get("Authorization") == "Basic dXNlcjpwYXNzd29yZA=="

        client.close()

    def test_session_model_duplicate_cookies(self):
        """Test handling multiple cookies with the same name but different domains."""
        client = httpx.Client()
        client.cookies.set("INGRESSCOOKIE", "value1", domain="example.com")
        client.cookies.set("INGRESSCOOKIE", "value2", domain="other.com")

        # Should not raise CookieConflict
        model = SessionModel.from_client(client)
        assert len(model.cookies) == 2

        # Apply to new client
        client2 = httpx.Client()
        model.apply_to_client(client2)
        assert len(list(client2.cookies.jar)) == 2

        client.close()
        client2.close()

    def test_session_model_roundtrip(self):
        """Test full roundtrip: client -> model -> dict -> model -> client."""
        # Create client with state
        client1 = httpx.Client()
        client1.cookies.set("roundtrip", "test")
        client1.headers["X-Roundtrip"] = "header"
        client1.auth = ("round", "trip")

        # Extract to model, serialize to dict
        model1 = SessionModel.from_client(client1)
        data = model1.model_dump()

        # Deserialize and apply to new client
        model2 = SessionModel.model_validate(data)
        client2 = httpx.Client()
        model2.apply_to_client(client2)

        # Verify state was preserved
        assert client2.cookies.get("roundtrip") == "test"
        assert client2.headers.get("X-Roundtrip") == "header"
        # Auth is now stored as Authorization header
        assert client2.headers.get("Authorization") == model1.auth_header

        client1.close()
        client2.close()


class TestContextHttp:
    def test_client(self, http):
        assert isinstance(http.client, httpx.Client)

    def test_response(self, http, httpbin_url):
        response = http.get(f"{httpbin_url}/get")
        assert isinstance(response, ContextHttpResponse)
        assert isinstance(response._response, httpx.Response)

    def test_response_lazy(self, http, httpbin_url):
        response = http.get(f"{httpbin_url}/get", lazy=True)
        assert isinstance(response, ContextHttpResponse)
        assert response._response is None


class TestContextHttpResponse:
    def test_fetch_response(self, http, httpbin_url):
        request = httpx.Request("GET", f"{httpbin_url}/get")
        context_http_response = ContextHttpResponse(http, request)
        content_hash = context_http_response.fetch()
        # fetch() now returns content_hash, not file_path
        assert isinstance(content_hash, str)
        assert len(content_hash) == 40  # SHA1 hex digest length

    def test_contenttype(self, http, httpbin_url):
        request = httpx.Request("GET", f"{httpbin_url}/get")
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response.content_type == "application/json"

    def test_attachment(self, http, httpbin_url):
        request = httpx.Request(
            "GET",
            f"{httpbin_url}/response-headers?Content-Type="
            "text/plain;%20charset=UTF-8&Content-Disposition=attachment;"
            "%20filename%3d%22test.json%22",
        )
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response.file_name == "test.json"

    def test_encoding_default(self, http, httpbin_url):
        request = httpx.Request("GET", f"{httpbin_url}/response-headers?charset=")
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response.encoding == "utf-8"

    def test_encoding_utf16(self, http, httpbin_url):
        request = httpx.Request(
            "GET",
            f"{httpbin_url}/response-headers?content-type=text"
            "/plain;%20charset=utf-16",
        )
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response.encoding == "utf-16"

    def test_encoding_utf32(self, http, httpbin_url):
        request = httpx.Request(
            "GET",
            f"{httpbin_url}/response-headers?Content-Type=text/"
            "plain;%20charset=utf-32",
        )
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response.encoding == "utf-32"

    def test_request_id(self, http, httpbin_url):
        # httpx.Request with data needs to be passed as content
        request = httpx.Request(
            "GET", f"{httpbin_url}/get", content=b'{"hello": "world"}'
        )
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response._request_id is None
        assert isinstance(context_http_response.request_id, str)

    def test_content(self, http, httpbin_url):
        request = httpx.Request(
            "GET",
            f"{httpbin_url}/user-agent",
            headers={"User-Agent": "Memorious Test"},
        )
        context_http_response = ContextHttpResponse(http, request)
        assert isinstance(context_http_response.raw, bytes)
        assert isinstance(context_http_response.text, str)
        assert context_http_response.json == {"user-agent": "Memorious Test"}

    def test_html(self, http, httpbin_url):
        request = httpx.Request("GET", f"{httpbin_url}/html")
        context_http_response = ContextHttpResponse(http, request)
        assert isinstance(context_http_response.html, html.HtmlElement)

    def test_xml(self, http, httpbin_url):
        request = httpx.Request("GET", f"{httpbin_url}/xml")
        context_http_response = ContextHttpResponse(http, request)
        assert isinstance(context_http_response.xml, etree._ElementTree)

    def test_apply_data(self, http, httpbin_url):
        context_http_response = ContextHttpResponse(http)
        assert context_http_response.url is None
        assert context_http_response.status_code is None
        context_http_response.apply_data(
            data={"status_code": 200, "url": f"{httpbin_url}/get"}
        )
        assert context_http_response.url == f"{httpbin_url}/get"
        assert context_http_response.status_code == 200

    def test_deserialize(self, http, httpbin_url):
        data = {"status_code": 200, "url": f"{httpbin_url}/get"}
        context_http_response = ContextHttpResponse.deserialize(http, data)
        assert isinstance(context_http_response, ContextHttpResponse)
        assert context_http_response.url == f"{httpbin_url}/get"
        assert context_http_response.status_code == 200

    def test_close(self, http, httpbin_url):
        request = httpx.Request("GET", f"{httpbin_url}/get")
        context_http_response = ContextHttpResponse(http, request)
        content_hash = context_http_response.fetch()
        # fetch() now returns content_hash, not file_path
        assert isinstance(content_hash, str)
        context_http_response.close()
        # Content remains in archive after close

    def test_status_code_404(self, http, httpbin_url):
        request = httpx.Request("GET", f"{httpbin_url}/status/404")
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response.status_code == 404

    def test_status_code_500(self, http, httpbin_url):
        request = httpx.Request("GET", f"{httpbin_url}/status/500")
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response.status_code == 500

    def test_status_code_200(self, http, httpbin_url):
        request = httpx.Request("GET", f"{httpbin_url}/status/200")
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response.status_code == 200
