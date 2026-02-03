import logging
import warnings

# Suppress pydantic_settings warning about missing /run/secrets directory
warnings.filterwarnings("ignore", message='directory "/run/secrets" does not exist')

import urllib3  # noqa: E402

from memorious.logic.fetch import FetchClient, create_fetch_client, fetch  # noqa: E402

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Silence noisy third-party loggers
for logger_name in (
    "httpx",
    "httpcore",
    "zeep",
    "httpstream",
    "urllib3",
    "rdflib",
    "chardet",
):
    logging.getLogger(logger_name).setLevel(logging.WARNING)


# Public API for standalone fetching

__all__ = ["fetch", "create_fetch_client", "FetchClient"]
