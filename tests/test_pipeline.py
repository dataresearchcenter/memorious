"""Test complete pipeline execution using procrastinate in sync mode."""

import shutil
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CONFIG_DIR = Path(__file__).parent / "testdata" / "config"


@pytest.fixture
def output_dir():
    """Create and cleanup output directory."""
    path = Path("./tests/testdata/data/httpbin_output").resolve()
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def httpbin_crawler(httpbin):
    """Copy httpbin crawler config to testdata/config with correct URL."""
    # Read template and substitute HTTPBIN_URL
    template = (FIXTURES_DIR / "httpbin_crawler.yml").read_text()
    config = template.replace("${HTTPBIN_URL}", httpbin.url)

    # Write to testdata/config so the task can find it
    config_file = CONFIG_DIR / "httpbin_crawler.yml"
    config_file.write_text(config)

    yield config_file

    # Cleanup
    config_file.unlink(missing_ok=True)


@pytest.fixture
def auth_output_dir():
    """Create and cleanup output directory for auth test."""
    path = Path("./tests/testdata/data/httpbin_auth_output").resolve()
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def httpbin_auth_crawler(httpbin):
    """Copy httpbin auth crawler config to testdata/config with correct URL."""
    template = (FIXTURES_DIR / "httpbin_auth_crawler.yml").read_text()
    config = template.replace("${HTTPBIN_URL}", httpbin.url)

    config_file = CONFIG_DIR / "httpbin_auth_crawler.yml"
    config_file.write_text(config)

    yield config_file

    config_file.unlink(missing_ok=True)


def test_pipeline_full(httpbin_crawler, output_dir):
    """Test a complete crawler pipeline: seed -> fetch -> store."""
    from memorious.logic.crawler import Crawler

    # Verify output dir is empty before running
    assert list(output_dir.glob("**/*")) == [], "Output dir should be empty before run"

    # Load and run crawler just like the CLI does
    crawler = Crawler(httpbin_crawler)
    assert crawler is not None
    assert crawler.name == "httpbin_test"

    # Run the crawler - with PROCRASTINATE_SYNC=1 and memory:, this executes synchronously
    crawler.run(incremental=False)

    # Check that files were stored
    output_files = list(output_dir.glob("**/*"))
    assert len(output_files) > 0, "Expected output files from crawler"


def test_pipeline_auth(httpbin_auth_crawler, auth_output_dir):
    """Test session persistence with basic auth across pipeline stages.

    This tests that:
    1. session() operation sets up basic auth on the HTTP client
    2. Auth is serialized via SessionModel when session is saved
    3. Auth is restored in subsequent stage (fetch_auth)
    4. The authenticated request succeeds (httpbin returns 401 without valid auth)
    """
    import json

    from memorious.logic.crawler import Crawler

    # Verify output dir is empty before running
    assert list(auth_output_dir.glob("**/*")) == [], "Output dir should be empty"

    # Load and run crawler
    crawler = Crawler(httpbin_auth_crawler)
    assert crawler is not None
    assert crawler.name == "httpbin_auth_test"

    # Run the crawler
    crawler.run(incremental=False)

    # Check that files were stored
    output_files = list(auth_output_dir.glob("**/*.json"))
    assert len(output_files) > 0, "Expected JSON metadata files from crawler"

    # Find and verify the response content
    # The directory store creates <hash>.<filename>.json metadata files
    json_files = [f for f in auth_output_dir.glob("**/*.json")]
    assert len(json_files) > 0, "Expected metadata JSON file"

    # Read metadata to get content_hash
    with open(json_files[0]) as f:
        metadata = json.load(f)

    # Verify the request was authenticated (status_code 200, not 401)
    assert (
        metadata.get("status_code") == 200
    ), f"Expected 200 for authenticated request, got {metadata.get('status_code')}"
