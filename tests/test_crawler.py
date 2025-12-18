import os

from memorious.logic.crawler import Crawler
from memorious.model import CrawlerStage


class TestCrawler(object):
    def test_crawler(self, crawler_dir):
        source_file = os.path.join(crawler_dir, "simple_web_scraper.yml")
        crawler = Crawler(source_file)
        assert crawler.name == "occrp_web_site"
        names = crawler.stages.keys()
        assert set(names) == {"init", "fetch", "parse", "store"}
        stages = crawler.stages.values()
        assert all(isinstance(s, CrawlerStage) for s in stages)
