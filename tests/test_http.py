from lxml import etree, html
from requests import Request, Response, Session

from memorious.logic.http import ContextHttpResponse


class TestContextHttp:
    def test_session(self, http):
        assert isinstance(http.session, Session)

    def test_response(self, http, httpbin_url):
        response = http.get(f"{httpbin_url}/get")
        assert isinstance(response, ContextHttpResponse)
        assert isinstance(response._response, Response)

    def test_response_lazy(self, http, httpbin_url):
        response = http.get(f"{httpbin_url}/get", lazy=True)
        assert isinstance(response, ContextHttpResponse)
        assert response._response is None


class TestContextHttpResponse:
    def test_fetch_response(self, http, httpbin_url):
        request = Request("GET", f"{httpbin_url}/get")
        context_http_response = ContextHttpResponse(http, request)
        content_hash = context_http_response.fetch()
        # fetch() now returns content_hash, not file_path
        assert isinstance(content_hash, str)
        assert len(content_hash) == 40  # SHA1 hex digest length

    def test_contenttype(self, http, httpbin_url):
        request = Request("GET", f"{httpbin_url}/get")
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response.content_type == "application/json"

    def test_attachment(self, http, httpbin_url):
        request = Request(
            "GET",
            f"{httpbin_url}/response-headers?Content-Type="
            "text/plain;%20charset=UTF-8&Content-Disposition=attachment;"
            "%20filename%3d%22test.json%22",
        )
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response.file_name == "test.json"

    def test_encoding_default(self, http, httpbin_url):
        request = Request("GET", f"{httpbin_url}/response-headers?charset=")
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response.encoding == "utf-8"

    def test_encoding_utf16(self, http, httpbin_url):
        request = Request(
            "GET",
            f"{httpbin_url}/response-headers?content-type=text"
            "/plain;%20charset=utf-16",
        )
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response.encoding == "utf-16"

    def test_encoding_utf32(self, http, httpbin_url):
        request = Request(
            "GET",
            f"{httpbin_url}/response-headers?Content-Type=text/"
            "plain;%20charset=utf-32",
        )
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response.encoding == "utf-32"

    def test_request_id(self, http, httpbin_url):
        request = Request("GET", f"{httpbin_url}/get", data={"hello": "world"})
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response._request_id is None
        assert isinstance(context_http_response.request_id, str)

    def test_content(self, http, httpbin_url):
        request = Request(
            "GET",
            f"{httpbin_url}/user-agent",
            headers={"User-Agent": "Memorious Test"},
        )
        context_http_response = ContextHttpResponse(http, request)
        assert isinstance(context_http_response.raw, bytes)
        assert isinstance(context_http_response.text, str)
        assert context_http_response.json == {"user-agent": "Memorious Test"}

    def test_html(self, http, httpbin_url):
        request = Request("GET", f"{httpbin_url}/html")
        context_http_response = ContextHttpResponse(http, request)
        assert isinstance(context_http_response.html, html.HtmlElement)

    def test_xml(self, http, httpbin_url):
        request = Request("GET", f"{httpbin_url}/xml")
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
        request = Request("GET", f"{httpbin_url}/get")
        context_http_response = ContextHttpResponse(http, request)
        content_hash = context_http_response.fetch()
        # fetch() now returns content_hash, not file_path
        assert isinstance(content_hash, str)
        context_http_response.close()
        # Content remains in archive after close

    def test_status_code_404(self, http, httpbin_url):
        request = Request("GET", f"{httpbin_url}/status/404")
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response.status_code == 404

    def test_status_code_500(self, http, httpbin_url):
        request = Request("GET", f"{httpbin_url}/status/500")
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response.status_code == 500

    def test_status_code_200(self, http, httpbin_url):
        request = Request("GET", f"{httpbin_url}/status/200")
        context_http_response = ContextHttpResponse(http, request)
        assert context_http_response.status_code == 200
