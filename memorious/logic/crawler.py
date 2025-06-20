import io
import logging
import os
import re
from datetime import timedelta
from importlib import import_module

import yaml
from servicelayer.cache import make_key
from servicelayer.extensions import get_entry_point
from servicelayer.jobs import Dataset, Job

from memorious import settings
from memorious.core import conn, tags
from memorious.logic.stage import CrawlerStage
from memorious.model import Crawl, Queue

log = logging.getLogger(__name__)


class Crawler(object):
    """A processing graph that constitutes a crawler."""

    SCHEDULES = {
        "disabled": None,
        "hourly": timedelta(hours=1),
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1),
        "monthly": timedelta(weeks=4),
    }

    def __init__(self, manager, source_file):
        self.manager = manager
        self.source_file = source_file
        with io.open(source_file, encoding="utf-8") as fh:
            self.config_yaml = fh.read()
            self.config = yaml.safe_load(self.config_yaml)

        self.name = os.path.basename(source_file)
        # YAML keys with undefined values will be parsed as `None`.
        # eg: with the yaml definition `name: `, `config.get("name", "default_value")`
        # will evaluate to `None` instead of `default_value`.
        # So in order to avoid setting `self.name` to `None`, we use `or` to
        # set the default instead of passing it to `config.get()`
        self.name = self.config.get("name") or self.name
        self.validate_name()
        self.description = self.config.get("description") or self.name
        self.category = self.config.get("category") or "scrape"
        self.init_stage = self.config.get("init") or "init"
        self.delay = int(self.config.get("delay") or 0)
        self.expire = int(self.config.get("expire") or settings.EXPIRE) * 84600
        self.stealthy = self.config.get("stealthy") or False
        self.queue = Dataset(conn, self.name)
        self.aggregator_config = self.config.get("aggregator") or {}

        self.stages = {}
        for name, stage in self.config.get("pipeline", {}).items():
            self.stages[name] = CrawlerStage(self, name, stage)

    def validate_name(self):
        if not re.match(r"^[A-Za-z0-9_-]+$", self.name):
            raise ValueError(
                "Invalid crawler name: %s. "
                "Allowed characters: A-Za-z0-9_-" % self.name
            )

    @property
    def aggregator_method(self):
        if self.aggregator_config:
            method = self.aggregator_config.get("method")
            if not method:
                return
            # method A: via a named Python entry point
            func = get_entry_point("memorious.operations", method)
            if func is not None:
                return func
            # method B: direct import from a module
            if ":" in method:
                package, method = method.rsplit(":", 1)
                module = import_module(package)
                return getattr(module, method)
            raise ValueError("Unknown method: %s", self.method_name)

    def aggregate(self, context):
        if self.aggregator_method:
            log.info("Running aggregator for %s" % self.name)
            params = self.aggregator_config.get("params", {})
            self.aggregator_method(context, params)

    def flush(self):
        """Delete all run-time data generated by this crawler."""
        self.queue.cancel()
        Crawl.flush(self)
        self.flush_tags()

    def flush_tags(self):
        tags.delete(prefix=make_key(self, "tag"))

    def cancel(self):
        Crawl.abort_all(self)
        self.queue.cancel()

    def run(self, incremental=None, run_id=None):
        """Queue the execution of a particular crawler."""
        state = {
            "crawler": self.name,
            "run_id": run_id or Job.random_id(),
            "incremental": settings.INCREMENTAL,
            "continue_on_error": settings.CONTINUE_ON_ERROR,
        }
        if incremental is not None:
            state["incremental"] = incremental

        # Cancel previous runs:
        self.cancel()
        init_stage = self.get(self.init_stage)
        Queue.queue(init_stage, state, {})

    @property
    def is_running(self):
        """Is the crawler currently running?"""
        for job in self.queue.get_jobs():
            if not job.is_done():
                return True
        return False

    @property
    def last_run(self):
        return Crawl.last_run(self)

    @property
    def op_count(self):
        """Total operations performed for this crawler"""
        return Crawl.op_count(self)

    @property
    def runs(self):
        return Crawl.runs(self)

    @property
    def latest_runid(self):
        return Crawl.latest_runid(self)

    @property
    def pending(self):
        status = self.queue.get_status()
        return status.get("pending")

    def get(self, name):
        return self.stages.get(name)

    def __str__(self):
        return self.name

    def __iter__(self):
        return iter(self.stages.values())

    def __repr__(self):
        return "<Crawler(%s)>" % self.name
