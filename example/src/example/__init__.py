import os

from memorious.logic.manager import CrawlerManager

# Example plugin init function - can be registered via memorious.plugins entry point


def init():
    """Load example crawlers from the config directory."""
    manager = CrawlerManager()
    file_path = os.path.dirname(__file__)
    config_path = os.path.join(file_path, "..", "..", "config")
    manager.load_path(config_path)
    return manager
