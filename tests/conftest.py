import os
import uuid

import pytest

from memorious.logic.context import Context
from memorious.logic.http import ContextHttp
from memorious.logic.manager import CrawlerManager


def get_crawler_dir():
    file_path = os.path.realpath(__file__)
    crawler_dir = os.path.normpath(os.path.join(file_path, "../testdata/config"))
    return crawler_dir


# Module-level manager singleton for tests
_test_manager: CrawlerManager | None = None


def get_manager():
    global _test_manager
    if _test_manager is None:
        _test_manager = CrawlerManager()
        _test_manager.load_path(get_crawler_dir())
    return _test_manager


@pytest.fixture(scope="module")
def crawler_dir():
    return get_crawler_dir()


@pytest.fixture(scope="module")
def manager():
    return get_manager()


def get_crawler():
    return get_manager().get("occrp_web_site")


@pytest.fixture(scope="module")
def crawler():
    return get_crawler()


def get_stage():
    cr = get_crawler()
    return cr.get(cr.init_stage)


@pytest.fixture(scope="module")
def stage():
    return get_stage()


def get_context():
    ctx = Context(get_crawler(), get_stage(), {"foo": "bar"})
    ctx.run_id = str(uuid.uuid4())
    return ctx


@pytest.fixture(scope="function")
def context():
    """Fresh context for each test function to avoid state leakage."""
    return get_context()


@pytest.fixture(scope="function")
def http():
    """Fresh HTTP client for each test function."""
    return ContextHttp(get_context())


@pytest.fixture(scope="session")
def httpbin_url(httpbin):
    """Provide httpbin URL from pytest-httpbin fixture.

    pytest-httpbin automatically starts a local httpbin server in a separate
    thread - no Docker required.
    """
    return httpbin.url


@pytest.fixture(scope="session")
def httpbin_secure_url(httpbin_secure, httpbin_ca_bundle):
    """Provide HTTPS httpbin URL from pytest-httpbin fixture."""
    return httpbin_secure.url
