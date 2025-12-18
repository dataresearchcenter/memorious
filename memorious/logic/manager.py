import os
from fnmatch import fnmatch
from pathlib import Path

from anystore.logging import get_logger

from memorious.logic.crawler import Crawler

log = get_logger(__name__)


class CrawlerManager(object):
    """Crawl a directory of YAML files to load a set of crawler specs."""

    def __init__(self):
        self.crawlers = {}

    def load_path(self, path):
        path = Path(path).resolve()  # Convert to absolute path
        if not path.is_dir():
            log.warning("Crawler config path not found", path=str(path))
            return

        for root, _, file_names in os.walk(path):
            for file_name in file_names:
                if not (fnmatch(file_name, "*.yaml") or fnmatch(file_name, "*.yml")):
                    continue
                source_file = Path(root) / file_name
                try:
                    crawler = Crawler(self, source_file)
                except ValueError:
                    log.exception("Skipping crawler due to error", file=file_name)
                    continue
                self.crawlers[crawler.name] = crawler

    def load_crawler(self, path: str | Path) -> Crawler | None:
        path = Path(path)
        if path.is_file():
            if fnmatch(path.name, "*.yaml") or fnmatch(path.name, "*.yml"):
                try:
                    crawler = Crawler(self, path)
                    self.crawlers[crawler.name] = crawler
                    return crawler
                except ValueError:
                    log.exception("Could not load crawler due to error", file=path.name)
            log.warning("Crawler path is not a yaml file", path=str(path))
        else:
            log.warning("Crawler path is not a valid file path", path=str(path))
        return None

    def __getitem__(self, name):
        return self.crawlers.get(name)

    def __iter__(self):
        crawlers = list(self.crawlers.values())
        crawlers.sort(key=lambda c: c.name)
        return iter(crawlers)

    def __len__(self):
        return len(self.crawlers)

    def get(self, name):
        return self.crawlers.get(name)
