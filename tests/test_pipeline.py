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


def test_full_pipeline(httpbin_crawler, output_dir):
    """Test a complete crawler pipeline: seed -> fetch -> store."""
    from memorious.logic.manager import CrawlerManager

    # Verify output dir is empty before running
    assert list(output_dir.glob("**/*")) == [], "Output dir should be empty before run"

    # Load and run crawler just like the CLI does
    manager = CrawlerManager()
    crawler = manager.load_crawler(httpbin_crawler)
    assert crawler is not None
    assert crawler.name == "httpbin_test"

    # Run the crawler - with PROCRASTINATE_SYNC=1 and memory:, this executes synchronously
    crawler.run(incremental=False)

    # Check that files were stored
    output_files = list(output_dir.glob("**/*"))
    assert len(output_files) > 0, "Expected output files from crawler"
