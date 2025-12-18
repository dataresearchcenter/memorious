import logging

import urllib3

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
