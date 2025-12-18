from urllib.parse import urlparse

import httpx
from anystore.util import join_relpaths as make_key

from memorious.helpers.rule import Rule


def fetch(context, data):
    """Do an HTTP GET on the ``url`` specified in the inbound data."""
    url = data.get("url")
    if urlparse(url).scheme not in ("http", "https", ""):
        context.log.info("Fetch skipped. Unsupported scheme: %r" % url)
        return
    attempt = data.pop("retry_attempt", 1)
    try:
        result = context.http.get(url, lazy=True)
        rules = context.get("rules", {"match_all": {}})
        if not Rule.get_rule(rules).apply(result):
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


def session(context, data):
    """Set some HTTP parameters for all subsequent requests.

    This includes ``user`` and ``password`` for HTTP basic authentication,
    and ``user_agent`` as a header.
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
        # httpx uses different proxy format
        context.http.client._mounts = {
            "http://": httpx.HTTPTransport(proxy=proxy),
            "https://": httpx.HTTPTransport(proxy=proxy),
        }

    # Explicitly save the session because no actual HTTP requests were made.
    context.http.save()
    context.emit(data=data)
