import os

from memorious.logic.crawler import Crawler, get_crawler


class TestCrawlerLoading(object):
    def test_load_crawler(self):
        file_path = os.path.realpath(__file__)
        config_file = os.path.normpath(
            os.path.join(file_path, "../testdata/config/simple_web_scraper.yml")
        )
        crawler = get_crawler(config_file)
        assert isinstance(crawler, Crawler)
        assert crawler.name == "occrp_web_site"

    def test_crawler_cached(self):
        file_path = os.path.realpath(__file__)
        config_file = os.path.normpath(
            os.path.join(file_path, "../testdata/config/simple_web_scraper.yml")
        )
        crawler1 = get_crawler(config_file)
        crawler2 = get_crawler(config_file)
        assert crawler1 is crawler2
