import logging

import urllib3

from memorious.logic.fetch import FetchClient, create_fetch_client, fetch

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
