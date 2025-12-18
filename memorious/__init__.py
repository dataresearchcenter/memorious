import logging

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("zeep").setLevel(logging.WARNING)
logging.getLogger("httpstream").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("rdflib").setLevel(logging.WARNING)
logging.getLogger("chardet").setLevel(logging.WARNING)
