"""HTTP fetch operations for web crawling.

This module provides operations for making HTTP requests (GET, POST)
and managing HTTP sessions in crawlers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import httpx
from anystore.util import join_relpaths as make_key
from banal import clean_dict, ensure_dict
from furl import furl

from memorious.helpers.forms import extract_form
from memorious.helpers.rule import parse_rule
from memorious.helpers.template import render_template
from memorious.logic.incremental import should_skip_incremental

if TYPE_CHECKING:
    from memorious.logic.context import Context


def fetch(context: Context, data: dict[str, Any]) -> None:
    """Fetch a URL via HTTP GET request.

    Performs an HTTP GET request on the URL specified in the data dict.
    Supports retry logic, URL rules filtering, incremental skipping,
    URL rewriting, pagination, and custom headers.

    Args:
        context: The crawler context.
        data: Must contain "url" key with the URL to fetch.

    Params:
        rules: URL/content filtering rules (default: match_all).
        retry: Number of retry attempts (default: 3).
        emit_errors: If True, emit data even on HTTP errors (default: False).
        headers: Extra HTTP headers to send.
        base_url: Base URL for resolving relative URLs.
        rewrite: URL rewriting configuration with "method" and "data" keys.
            Methods: "template" (Jinja2), "replace" (string replace).
        pagination: Pagination config with "param" key for page number.
        skip_incremental: Advanced incremental skip configuration.

    Example:
        ```yaml
        pipeline:
          # Simple fetch
          fetch:
            method: fetch
            params:
              rules:
                domain: example.com
              retry: 5
            handle:
              pass: parse

          # Fetch with URL rewriting and headers
          fetch_detail:
            method: fetch
            params:
              headers:
                Referer: https://example.com/search
              rewrite:
                method: template
                data: "https://example.com/doc/{{ doc_id }}"
            handle:
              pass: parse

          # Fetch with pagination
          fetch_list:
            method: fetch
            params:
              url: https://example.com/results
              pagination:
                param: page
              skip_incremental:
                key:
                  data: [doc_id]
                target: store
            handle:
              pass: parse
        ```
    """
    # Check incremental skip first
    if should_skip_incremental(context, data):
        return

    # Apply extra headers
    _apply_headers(context)

    # Get URL from params or data
    url = _get_url(context, data)

    # Apply pagination
    if "pagination" in context.params:
        pagination = ensure_dict(context.params["pagination"])
        if "param" in pagination:
            page = data.get("page", 1)
            f = furl(url)
            f.args[pagination["param"]] = page
            url = f.url

    # Apply URL rewriting
    if "rewrite" in context.params:
        rewrite = context.params["rewrite"]
        method = rewrite.get("method")
        method_data = rewrite.get("data")
        if method == "replace":
            url = url.replace(*method_data)
        elif method == "template":
            url = render_template(method_data, data)

    if url is None:
        context.log.error("No URL specified")
        return

    # Handle relative URLs
    f = furl(url)
    if f.scheme is None:
        base_url = context.params.get("base_url")
        if base_url:
            url = furl(base_url).join(f).url
        elif "url" in data:
            url = furl(data["url"]).join(f).url

    # Validate URL scheme
    if urlparse(url).scheme not in ("http", "https", ""):
        context.log.info("Fetch skipped. Unsupported scheme: %r" % url)
        return

    attempt = data.pop("retry_attempt", 1)
    try:
        result = context.http.get(url, lazy=True)
        rules = context.get("rules", {"match_all": {}})
        if not parse_rule(rules).apply(result):
            context.log.info("Fetch skip: %r" % result.url)
            return

        if not result.ok:
            err = (result.url, result.status_code)
            context.emit_warning("Fetch fail [%s]: HTTP %s" % err)
            if not context.params.get("emit_errors", False):
                return
        else:
            context.log.info("Fetched [%s]: %r" % (result.status_code, result.url))

        data.update(result.serialize())
        if url != result.url:
            tag = make_key(context.run_id, url)
            context.set_tag(tag, None)
        context.emit(data=data)
    except httpx.HTTPError as ce:
        retries = int(context.get("retry", 3))
        if retries >= attempt:
            context.log.warn("Retry: %s (error: %s)", url, ce)
            data["retry_attempt"] = attempt + 1
            context.recurse(data=data, delay=2**attempt)
        else:
            context.emit_warning("Fetch fail [%s]: %s" % (url, ce))


def session(context: Context, data: dict[str, Any]) -> None:
    """Configure HTTP session parameters for subsequent requests.

    Sets up authentication, user agent, referer, and proxy settings
    that will be used for all subsequent HTTP requests in this crawler run.

    Args:
        context: The crawler context.
        data: Passed through to next stage.

    Params:
        user: Username for HTTP basic authentication.
        password: Password for HTTP basic authentication.
        user_agent: Custom User-Agent header.
        url: URL to set as Referer header.
        proxy: Proxy URL for HTTP/HTTPS requests.

    Example:
        ```yaml
        pipeline:
          setup_session:
            method: session
            params:
              user: "${HTTP_USER}"
              password: "${HTTP_PASSWORD}"
              user_agent: "MyBot/1.0"
            handle:
              pass: fetch
        ```
    """
    context.http.reset()

    user = context.get("user")
    password = context.get("password")

    if user is not None and password is not None:
        context.http.client.auth = (user, password)

    user_agent = context.get("user_agent")
    if user_agent is not None:
        context.http.client.headers["User-Agent"] = user_agent

    referer = context.get("url")
    if referer is not None:
        context.http.client.headers["Referer"] = referer

    proxy = context.get("proxy")
    if proxy is not None:
        context.http.client._mounts = {
            "http://": httpx.HTTPTransport(proxy=proxy),
            "https://": httpx.HTTPTransport(proxy=proxy),
        }

    # Explicitly save the session because no actual HTTP requests were made.
    context.http.save()
    context.emit(data=data)


def _get_url(context: Context, data: dict[str, Any]) -> str | None:
    """Get URL from context params or data, with optional templating."""
    url = context.params.get("url")
    if url is not None:
        return url.format(**data)
    return data.get("url")


def _get_headers(context: Context) -> dict[str, str]:
    """Get extra headers from context params."""
    return ensure_dict(context.params.get("headers"))


def _apply_headers(context: Context) -> None:
    """Apply extra headers to the HTTP client."""
    for key, value in _get_headers(context).items():
        context.http.client.headers[key] = value


def _get_post_data(context: Context, data: dict[str, Any]) -> dict[str, Any]:
    """Build POST data from params and data dict."""
    post_data = ensure_dict(context.params.get("data"))
    for post_key, data_key in ensure_dict(context.params.get("use_data")).items():
        if data_key in data:
            post_data[post_key] = data[data_key]
    return clean_dict(post_data)


def post(context: Context, data: dict[str, Any]) -> None:
    """Perform HTTP POST request with form data.

    Sends a POST request with form-urlencoded data to the specified URL.

    Args:
        context: The crawler context.
        data: Current stage data.

    Params:
        url: Target URL (or use data["url"]).
        data: Dictionary of form fields to POST.
        use_data: Map of {post_field: data_key} to include from data dict.
        headers: Extra HTTP headers.

    Example:
        ```yaml
        pipeline:
          submit_form:
            method: post
            params:
              url: https://example.com/search
              data:
                query: "test"
                page: 1
              use_data:
                session_id: sid
              headers:
                X-Custom-Header: value
            handle:
              pass: parse
        ```
    """
    _apply_headers(context)
    url = _get_url(context, data)
    if url is None:
        context.log.warning("No URL for POST request")
        return

    post_data = _get_post_data(context, data)
    context.log.debug(f"POST to {url}: {post_data}")
    result = context.http.post(url, data=post_data)
    context.emit(data={**data, **result.serialize()})


def post_json(context: Context, data: dict[str, Any]) -> None:
    """Perform HTTP POST request with JSON body.

    Sends a POST request with a JSON payload to the specified URL.

    Args:
        context: The crawler context.
        data: Current stage data.

    Params:
        url: Target URL (or use data["url"]).
        data: Dictionary to send as JSON body.
        use_data: Map of {json_field: data_key} to include from data dict.
        headers: Extra HTTP headers.

    Example:
        ```yaml
        pipeline:
          api_call:
            method: post_json
            params:
              url: https://api.example.com/documents
              data:
                action: "search"
                limit: 100
              use_data:
                document_id: doc_id
            handle:
              pass: process
        ```
    """
    _apply_headers(context)
    url = _get_url(context, data)
    if url is None:
        context.log.warning("No URL for POST request")
        return

    json_data = _get_post_data(context, data)
    context.log.debug(f"POST JSON to {url}: {json_data}")
    result = context.http.post(url, json_data=json_data)
    context.emit(data={**data, **result.serialize()})


def post_form(context: Context, data: dict[str, Any]) -> None:
    """Perform HTTP POST to an HTML form with its current values.

    Extracts form fields from an HTML page and submits them with
    optional additional data.

    Args:
        context: The crawler context.
        data: Current stage data (must have cached HTML response).

    Params:
        form: XPath to locate the form element.
        data: Additional form fields to add/override.
        use_data: Map of {form_field: data_key} to include from data dict.
        headers: Extra HTTP headers.

    Example:
        ```yaml
        pipeline:
          submit_search:
            method: post_form
            params:
              form: './/form[@id="search-form"]'
              data:
                query: "documents"
              use_data:
                csrf_token: token
            handle:
              pass: parse_results
        ```
    """
    _apply_headers(context)
    form_xpath = context.params.get("form")
    if not form_xpath:
        context.log.error("No form XPath specified")
        return

    result = context.http.rehash(data)
    if result.html is None:
        context.log.error("No HTML content to extract form from")
        return

    action, form_data = extract_form(result.html, form_xpath)
    if action is None:
        context.log.error(f"Form not found: {form_xpath}")
        return

    base_url = data.get("url", "")
    url = furl(base_url).join(action).url

    # Merge form data with additional data from params
    form_data.update(_get_post_data(context, data))
    context.log.debug(f"POST form to {url}: {form_data}")
    post_result = context.http.post(url, data=form_data)
    context.emit(data={**data, **post_result.serialize()})


def fetch_extended(context: Context, data: dict[str, Any]) -> None:
    """Deprecated: Use fetch() instead.

    This function is kept for backward compatibility and simply
    delegates to fetch(), which now includes all extended features.
    """
    fetch(context, data)
