import json
import os
import shutil
from unittest.mock import ANY

from memorious.operations.fetch import fetch, session
from memorious.operations.initializers import dates, enumerate, seed, sequence
from memorious.operations.parse import parse
from memorious.operations.store import (
    _compute_file_path,
    directory,
    lakehouse,
)


def test_fetch_html(context, mocker, httpbin_url):
    rules = {"pattern": f"{httpbin_url}/*"}
    context.params["rules"] = rules
    mocker.patch.object(context, "emit")
    fetch(context, {"url": f"{httpbin_url}/html"})
    assert context.emit.call_count == 1


def test_fetch_blocked_domain(context, mocker, httpbin_url):
    rules = {"pattern": f"{httpbin_url}/*"}
    context.params["rules"] = rules
    mocker.patch.object(context, "emit")
    fetch(context, {"url": "https://occrp.org/"})
    assert context.emit.call_count == 0


def test_fetch_error_status(context, mocker, httpbin_url):
    rules = {"pattern": f"{httpbin_url}/*"}
    context.params["rules"] = rules
    mocker.patch.object(context, "emit")
    fetch(context, {"url": f"{httpbin_url}/status/418"})
    assert context.emit.call_count == 0


def test_session(context, mocker, httpbin_url):
    context.params["user"] = "user"
    context.params["password"] = "password"
    context.params["user_agent"] = "Godzilla Firehose 0.1"
    context.params["url"] = f"{httpbin_url}/get"
    data = {"hello": "world"}
    mocker.patch.object(context.http, "save")
    mocker.patch.object(context, "emit")

    session(context, data)

    assert context.http.save.called_one_with()
    assert context.emit.called_one_with(data=data)
    assert context.http.client.headers["User-Agent"] == "Godzilla Firehose 0.1"
    assert context.http.client.headers["Referer"] == f"{httpbin_url}/get"
    # httpx uses BasicAuth object instead of tuple
    assert context.http.client.auth is not None


def test_parse(context, mocker, httpbin_url):
    url = "http://example.org/"
    result = context.http.get(url)
    data = result.serialize()

    mocker.patch.object(context, "emit")

    rules = {"pattern": f"{httpbin_url}/*"}
    context.params["store"] = rules
    context.params["meta"] = {"title": ".//h1", "description": ".//p"}
    parse(context, data)
    assert context.emit.call_count == 1
    context.emit.assert_called_once_with(rule="fetch", data=ANY)

    # cleanup tags
    context.tags.delete()

    context.http.result = None
    context.params["store"] = None
    parse(context, data)
    # Check emitted data (parse no longer mutates input data)
    # Find the fetch emit (last one with rule="fetch")
    fetch_calls = [
        c for c in context.emit.call_args_list if c.kwargs.get("rule") == "fetch"
    ]
    emitted_data = fetch_calls[-1].kwargs["data"]
    assert emitted_data["url"] == "https://iana.org/domains/example"
    assert data["title"] == "Example Domain"
    assert data["description"].startswith("This domain is for")
    assert context.emit.call_count == 3


def test_parse_ftm(context, mocker):
    url = "https://www.occrp.org/en/daily/14082-riviera-maya-gang-members-sentenced-in-romania"
    result = context.http.get(url)
    data = result.serialize()
    context.params["schema"] = "Article"
    context.params["properties"] = {
        "title": './/meta[@property="og:title"]/@content',
        "publishedAt": './/*[@class="date"]/text()',
        "description": './/meta[@property="og:description"]/@content',
    }

    parse(context, data)

    props = data["properties"]

    assert "Riviera Maya Gang Members Sentenced in Romania" in props["title"]
    assert props["description"][0].startswith("A Bucharest court")


def test_seed(context, mocker, httpbin_url):
    context.params["url"] = None
    context.params["urls"] = [f"{httpbin_url}/status/%(status)s"]
    mocker.patch.object(context, "emit")
    seed(context, data={"status": 404})
    assert context.emit.call_count == 1
    context.emit.assert_called_once_with(data={"url": f"{httpbin_url}/status/404"})


def test_sequence(context, mocker):
    mocker.patch.object(context, "emit")

    context.params["start"] = 2
    context.params["stop"] = 11
    context.params["step"] = 3
    sequence(context, data={})
    assert context.emit.call_count == 3

    context.params["start"] = 7
    context.params["stop"] = 1
    context.params["step"] = -3
    sequence(context, data={})
    assert context.emit.call_count == 5


def test_dates(context, mocker):
    mocker.patch.object(context, "emit")
    mocker.patch.object(context, "recurse")
    context.params["format"] = "%d-%m-%Y"
    context.params["days"] = 3
    context.params["begin"] = "10-12-2012"
    context.params["end"] = "20-12-2012"
    dates(context, data={})
    assert context.emit.call_count == 1
    context.emit.assert_called_once_with(
        data={"date": "20-12-2012", "date_iso": "2012-12-20T00:00:00"}
    )
    assert context.recurse.call_count == 1
    context.recurse.assert_called_once_with(data={"current": "17-12-2012"})


def test_enumerate(context, mocker):
    mocker.patch.object(context, "emit")
    context.params["items"] = [1, 2, 3]
    enumerate(context, data={})
    assert context.emit.call_count == 3
    # expected_calls = [
    #     mocker.call(data={"item": 1}),
    #     mocker.call(data={"item": 2}),
    #     mocker.call(data={"item": 3}),
    # ]
    # assert context.emit.mock_calls == expected_calls
    # Ideally this should work, but currently it doesn't; because we pass
    # the reference to data dict around and then mutate it.


def test_directory(context, httpbin_url):
    file_path = os.path.realpath(__file__)
    store_dir = os.path.normpath(
        os.path.join(file_path, "../testdata/data/store/occrp_web_site")
    )
    shutil.rmtree(store_dir, ignore_errors=True)

    # echo user-agent - URL path is /user-agent, stored as user_agent.json (safe_filename)
    url = f"{httpbin_url}/user-agent"
    result = context.http.get(url, headers={"User-Agent": "Memorious Test"})
    data = result.serialize()
    directory(context, data)

    content_hash = data.get("content_hash")

    # With url_path default, file is stored by URL path (user_agent.json after safe_filename)
    raw_file_path = os.path.join(store_dir, "user_agent.json")
    meta_file_path = os.path.join(store_dir, content_hash + ".json")
    assert os.path.exists(meta_file_path)
    assert os.path.exists(raw_file_path)

    with open(meta_file_path, "rb") as fh:
        assert json.load(fh)["content_hash"] == data["content_hash"]
    with open(raw_file_path, "rb") as fh:
        raw_content = json.load(fh)
        assert raw_content["user-agent"] == "Memorious Test"


def test_directory_collision(context, mocker, httpbin_url):
    """Test that files with same path but different content get unique names."""
    file_path = os.path.realpath(__file__)
    store_dir = os.path.normpath(
        os.path.join(file_path, "../testdata/data/store/occrp_web_site")
    )
    shutil.rmtree(store_dir, ignore_errors=True)

    mocker.patch.object(context, "emit")
    mocker.patch.object(context, "mark_emit_complete")

    # First request - creates user_agent.json
    url = f"{httpbin_url}/user-agent"
    result1 = context.http.get(url, headers={"User-Agent": "First Request"})
    data1 = result1.serialize()
    directory(context, data1)

    first_hash = data1.get("content_hash")
    first_file_path = os.path.join(store_dir, "user_agent.json")
    assert os.path.exists(first_file_path)

    # Second request with different content - should create user_agent_<hash>.json
    result2 = context.http.get(url, headers={"User-Agent": "Second Request"})
    data2 = result2.serialize()
    directory(context, data2)

    second_hash = data2.get("content_hash")
    assert first_hash != second_hash, "Content hashes should differ"

    # Second file should have hash suffix
    expected_suffix = second_hash[:8]
    second_file_path = os.path.join(store_dir, f"user_agent_{expected_suffix}.json")
    assert os.path.exists(
        second_file_path
    ), f"Expected collision file at {second_file_path}"

    # Verify both files have correct content
    with open(first_file_path, "rb") as fh:
        assert json.load(fh)["user-agent"] == "First Request"
    with open(second_file_path, "rb") as fh:
        assert json.load(fh)["user-agent"] == "Second Request"

    # Verify metadata files exist for both
    assert os.path.exists(os.path.join(store_dir, f"{first_hash}.json"))
    assert os.path.exists(os.path.join(store_dir, f"{second_hash}.json"))

    # Verify _file_name in data reflects the actual path used
    assert data1["_file_name"] == "user_agent.json"
    assert data2["_file_name"] == f"user_agent_{expected_suffix}.json"


def test_directory_same_content(context, mocker, httpbin_url):
    """Test that storing the same content twice doesn't create duplicates."""
    file_path = os.path.realpath(__file__)
    store_dir = os.path.normpath(
        os.path.join(file_path, "../testdata/data/store/occrp_web_site")
    )
    shutil.rmtree(store_dir, ignore_errors=True)

    mocker.patch.object(context, "emit")
    mocker.patch.object(context, "mark_emit_complete")

    # First request
    url = f"{httpbin_url}/user-agent"
    result1 = context.http.get(url, headers={"User-Agent": "Same Content"})
    data1 = result1.serialize()
    directory(context, data1)

    first_hash = data1.get("content_hash")
    first_file_path = os.path.join(store_dir, "user_agent.json")
    assert os.path.exists(first_file_path)

    # Second request with same content (same headers = same response)
    result2 = context.http.get(url, headers={"User-Agent": "Same Content"})
    data2 = result2.serialize()
    directory(context, data2)

    second_hash = data2.get("content_hash")
    assert first_hash == second_hash, "Content hashes should be identical"

    # Should use same file path, no suffix added
    assert data2["_file_name"] == "user_agent.json"

    # Only one content file should exist (plus two metadata files)
    json_files = list(
        f
        for f in os.listdir(store_dir)
        if f.endswith(".json") and not f.startswith(first_hash)
    )
    assert len(json_files) == 1, "Should only have one content file"


def test_lakehouse_default(context, mocker, httpbin_url):
    """Test lakehouse store with default archive."""
    from ftm_lakehouse import get_lakehouse

    url = f"{httpbin_url}/user-agent"
    result = context.http.get(url, headers={"User-Agent": "Memorious Test"})
    data = result.serialize()

    mocker.patch.object(context, "emit")
    lakehouse(context, data)

    # Verify file is in the default archive
    # With url_path default, name comes from URL path (user-agent, no safe_filename)
    content_hash = data.get("content_hash")
    files = list(context.archive.get_all_files(content_hash))
    assert len(files) >= 1
    file_names = [f.name for f in files]
    assert "user-agent" in file_names
    assert context.emit.call_count == 1

    # Verify entity was created with origin=crawl
    dataset = get_lakehouse().get_dataset(context.crawler.name)
    entities = [
        e
        for e in dataset.entities.query(origin="crawl")
        if content_hash in e.get("contentHash", [])
    ]
    assert len(entities) == 1
    assert entities[0].schema.name == "Document"


def test_lakehouse_make_entities_disabled(context, mocker, httpbin_url):
    """Test lakehouse store with entity generation disabled."""
    from ftm_lakehouse import get_lakehouse

    url = f"{httpbin_url}/html"
    result = context.http.get(url)
    data = result.serialize()

    # Disable entity generation
    context.params["make_entities"] = False

    mocker.patch.object(context, "emit")
    lakehouse(context, data)

    # Verify file is in the archive
    content_hash = data.get("content_hash")
    files = list(context.archive.get_all_files(content_hash))
    assert len(files) >= 1
    assert context.emit.call_count == 1

    # Verify no entity was created for this file
    dataset = get_lakehouse().get_dataset(context.crawler.name)
    entities = [
        e
        for e in dataset.entities.query(origin="crawl")
        if content_hash in e.get("contentHash")
    ]
    assert len(entities) == 0

    # Clean up param
    del context.params["make_entities"]


# Tests for _compute_file_path helper function


def test_compute_file_path_default(context):
    """Test default behavior: url_path method."""
    data = {"url": "https://example.com/path/to/document.pdf", "headers": {}}
    path = _compute_file_path(context, data, "abc123hash", "ignored.pdf")
    # Default uses url_path method
    assert str(path) == "path/to/document.pdf"
    assert path.name == "document.pdf"


def test_compute_file_path_url_path_explicit(context):
    """Test url_path method when explicitly configured."""
    context.params["compute_path"] = {"method": "url_path", "params": {}}
    data = {"url": "https://example.com/path/to/document.pdf", "headers": {}}
    path = _compute_file_path(context, data, "abc123hash", "document.pdf")
    assert str(path) == "path/to/document.pdf"
    assert path.name == "document.pdf"
    del context.params["compute_path"]


def test_compute_file_path_url_path_extracts_name(context):
    """Test url_path extracts filename from URL path."""
    data = {"url": "https://example.com/path/to/file.txt", "headers": {}}
    path = _compute_file_path(context, data, "abc123hash", "ignored.pdf")
    # URL basename takes precedence
    assert str(path) == "path/to/file.txt"
    assert path.name == "file.txt"


def test_compute_file_path_url_path(context):
    """Test url_path method."""
    context.params["compute_path"] = {"method": "url_path", "params": {}}
    data = {"url": "https://example.com/api/v1/documents/report.pdf", "headers": {}}
    path = _compute_file_path(context, data, "abc123hash", "fallback.pdf")
    assert str(path) == "api/v1/documents/report.pdf"
    assert path.name == "report.pdf"
    del context.params["compute_path"]


def test_compute_file_path_url_path_include_domain(context):
    """Test url_path method with include_domain."""
    context.params["compute_path"] = {
        "method": "url_path",
        "params": {"include_domain": True},
    }
    data = {"url": "https://example.com/api/v1/documents/report.pdf", "headers": {}}
    path = _compute_file_path(context, data, "abc123hash", "fallback.pdf")
    assert str(path) == "example.com/api/v1/documents/report.pdf"
    assert path.name == "report.pdf"
    del context.params["compute_path"]


def test_compute_file_path_url_path_strip_prefix(context):
    """Test url_path method with strip_prefix."""
    context.params["compute_path"] = {
        "method": "url_path",
        "params": {"strip_prefix": "/api/v1"},
    }
    data = {"url": "https://example.com/api/v1/documents/report.pdf", "headers": {}}
    path = _compute_file_path(context, data, "abc123hash", "fallback.pdf")
    assert str(path) == "documents/report.pdf"
    assert path.name == "report.pdf"
    del context.params["compute_path"]


def test_compute_file_path_url_path_strip_prefix_and_domain(context):
    """Test url_path method with both strip_prefix and include_domain."""
    context.params["compute_path"] = {
        "method": "url_path",
        "params": {
            "strip_prefix": "/api/v1",
            "include_domain": True,
        },
    }
    data = {"url": "https://example.com/api/v1/documents/report.pdf", "headers": {}}
    path = _compute_file_path(context, data, "abc123hash", "fallback.pdf")
    assert str(path) == "example.com/documents/report.pdf"
    assert path.name == "report.pdf"
    del context.params["compute_path"]


def test_compute_file_path_file_name(context):
    """Test file_name method (flat structure)."""
    context.params["compute_path"] = {"method": "file_name", "params": {}}
    data = {"url": "https://example.com/deep/nested/path/file.pdf", "headers": {}}
    path = _compute_file_path(context, data, "abc123hash", "my_file.pdf")
    assert str(path) == "my_file.pdf"
    assert path.name == "my_file.pdf"
    del context.params["compute_path"]


def test_compute_file_path_template(context):
    """Test template method with Jinja2."""
    context.params["compute_path"] = {
        "method": "template",
        "params": {"template": "{{ meta.category }}/{{ meta.id }}_{{ file_name }}"},
    }
    data = {
        "url": "https://example.com/doc.pdf",
        "meta": {"category": "reports", "id": "12345"},
        "headers": {},
    }
    path = _compute_file_path(context, data, "abc123hash", "document.pdf")
    assert str(path) == "reports/12345_document.pdf"
    # safe_filename normalizes the result
    assert path.name == "12345_document.pdf"
    del context.params["compute_path"]


def test_compute_file_path_template_complex(context):
    """Test template with complex nested data access."""
    context.params["compute_path"] = {
        "method": "template",
        "params": {"template": "{{ headers.Server }}.pdf"},
    }
    data = {
        "url": "https://example.com/doc.pdf",
        "headers": {"Server": "nginx"},
    }
    path = _compute_file_path(context, data, "abc123hash", "fallback.pdf")
    assert str(path) == "nginx.pdf"
    assert path.name == "nginx.pdf"
    del context.params["compute_path"]


def test_compute_file_path_url_path_error_no_url(context):
    """Test url_path raises error when no URL in data."""
    import pytest

    data = {"headers": {}}
    with pytest.raises(ValueError, match="requires 'url' in data"):
        _compute_file_path(context, data, "abc123hash", "file.pdf")


def test_compute_file_path_url_path_error_no_filename(context):
    """Test url_path raises error when URL has no filename."""
    import pytest

    data = {"url": "https://example.com/", "headers": {}}
    with pytest.raises(ValueError, match="Could not extract file name"):
        _compute_file_path(context, data, "abc123hash", "file.pdf")


def test_compute_file_path_template_error_no_template(context):
    """Test template raises error when template not provided."""
    import pytest

    context.params["compute_path"] = {"method": "template", "params": {}}
    data = {"url": "https://example.com/doc.pdf", "headers": {}}
    with pytest.raises(ValueError, match="template is required"):
        _compute_file_path(context, data, "abc123hash", "file.pdf")
    del context.params["compute_path"]


def test_compute_file_path_unknown_method_error(context):
    """Test unknown method raises error."""
    import pytest

    context.params["compute_path"] = {"method": "unknown_method", "params": {}}
    data = {"url": "https://example.com/doc.pdf", "headers": {}}
    with pytest.raises(ValueError, match="Unknown compute_path method"):
        _compute_file_path(context, data, "abc123hash", "file.pdf")
    del context.params["compute_path"]
