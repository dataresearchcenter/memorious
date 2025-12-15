"""Execution context for crawler operations."""

import os
import random
import shutil
import uuid
from contextlib import contextmanager
from copy import deepcopy
from tempfile import mkdtemp
from typing import Any

from anystore.logging import get_logger
from anystore.util import join_relpaths as make_key

from memorious.core import settings, storage, tags
from memorious.logic.check import ContextCheck
from memorious.logic.crawler import Crawler
from memorious.logic.http import ContextHttp
from memorious.model.stage import CrawlerStage
from memorious.util import random_filename


class Context:
    """Provides state tracking and methods for operation interactions."""

    def __init__(self, crawler: Crawler, stage: CrawlerStage, state):
        self.crawler = crawler
        self.stage = stage
        self.state = state
        self.params = stage.params
        self.incremental = state.get("incremental")
        self.continue_on_error = state.get("continue_on_error")
        self.run_id = state.get("run_id") or uuid.uuid1().hex
        self.work_path = mkdtemp()
        self.log = get_logger(
            "%s.%s" % (crawler.name, stage.name),
            dataset=crawler.name,
            stage=stage.name,
            run_id=self.run_id,
        )

        self.http = ContextHttp(self)
        self.check = ContextCheck(self)

        self.settings = settings
        self.tags = tags
        self.storage = storage

    def get(self, name, default=None):
        """Get a configuration value and expand environment variables."""
        value = self.params.get(name, default)
        if isinstance(value, str):
            value = os.path.expandvars(value)
        return value

    def emit(self, rule="pass", stage=None, data=None, delay=None, optional=False):
        """
        Invoke the next stage via procrastinate task queue.

        Args:
            rule: Handler rule name to determine target stage
            stage: Explicit target stage (overrides rule lookup)
            data: Data to pass to the next stage
            delay: Delay in seconds (logged but not applied - use scheduled_at for delays)
            optional: If True, silently skip if no target stage found
        """
        data = data or {}

        # Resolve target stage
        if stage is None:
            stage = self.stage.handlers.get(rule)
        if optional and stage is None:
            return
        if stage is None or stage not in self.crawler.stages:
            self.log.info("No next stage: %s (%s)" % (stage, rule))
            return

        # Debug sampling
        if self.settings.debug:
            sampling_rate = self.get("sampling_rate")
            if sampling_rate and random.random() > float(sampling_rate):
                self.log.info("Skipping emit due to sampling rate")
                return

        # Log delay warning (procrastinate supports scheduled_at, but we simplify)
        if delay and delay > 0:
            self.log.debug("Delay of %ds requested but not applied" % delay)

        # Make a copy of the data to avoid mutation when in-memory connector
        data = deepcopy(data)

        # Defer the job via procrastinate
        self.crawler.defer(
            stage=stage,
            data=data,
            run_id=self.run_id,
            incremental=self.incremental or True,
            continue_on_error=self.continue_on_error or False,
        )

    def recurse(self, data=None, delay=None):
        """Have a stage invoke itself with a modified set of arguments."""
        if data is None:
            data = {}
        return self.emit(stage=self.stage.name, data=data, delay=delay)

    def execute(self, data: dict[str, Any]) -> Any:
        """Execute the stage method with the given data."""
        try:
            self.log.info(
                "[%s->%s(%s)]: %s"
                % (
                    self.crawler.name,
                    self.stage.name,
                    self.stage.method_name,
                    self.run_id,
                )
            )
            return self.stage.method(self, data)
        except Exception as exc:
            self.emit_exception(exc)
            if not self.continue_on_error:
                raise exc
        finally:
            shutil.rmtree(self.work_path)

    def emit_warning(self, message, *args):
        self.log.warning(message, *args)

    def emit_exception(self, exc):
        self.log.exception(exc)

    def set_tag(self, key: str, value: Any):
        key = make_key(self.crawler, "tag", key)
        return self.tags.put(key, value)

    def get_tag(self, key: str) -> Any:
        return self.tags.get(make_key(self.crawler, "tag", key))

    def check_tag(self, key):
        return self.tags.exists(make_key(self.crawler, "tag", key))

    def skip_incremental(self, *criteria):
        """Perform an incremental check on a set of criteria.

        This can be used to execute a part of a crawler only once per an
        interval (which is specified by the ``expire`` setting). If the
        operation has already been performed (and should thus be skipped),
        this will return ``True``. If the operation needs to be executed,
        the returned value will be ``False``.
        """
        if not self.incremental:
            return False

        key = make_key("inc", *criteria)
        if key is None:
            return False

        if self.check_tag(key):
            return True

        self.set_tag(key, "inc")
        return False

    def store_file(self, file_path, content_hash=None):
        """Put a file into permanent storage so it can be visible to other stages."""
        return self.storage.archive_file(file_path, content_hash=content_hash)

    def store_data(self, data, encoding="utf-8"):
        """Put the given content into a file, possibly encoding it as UTF-8."""
        path = random_filename(self.work_path)
        try:
            with open(path, "wb") as fh:
                if isinstance(data, str):
                    data = data.encode(encoding)
                if data is not None:
                    fh.write(data)
            return self.store_file(path)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    @contextmanager
    def load_file(self, content_hash, file_name=None, read_mode="rb"):
        file_path = self.storage.load_file(
            content_hash, file_name=file_name, temp_path=self.work_path
        )
        if file_path is None:
            yield None
        else:
            try:
                with open(file_path, mode=read_mode) as fh:
                    yield fh
            finally:
                self.storage.cleanup_file(content_hash, temp_path=self.work_path)

    def dump_state(self):
        state = deepcopy(self.state)
        state["dataset"] = self.crawler.name
        state["run_id"] = self.run_id
        return state

    @classmethod
    def from_state(cls, state, stage, manager):
        """Create a Context from serialized state.

        Args:
            state: Serialized state dict containing dataset name and run_id
            stage: Stage name to execute
            manager: CrawlerManager instance to look up crawler
        """
        dataset = state.get("dataset")
        crawler = manager.get(dataset)
        if crawler is None:
            raise RuntimeError("Missing dataset: [%s]" % dataset)
        stage = crawler.get(stage)
        if stage is None:
            raise RuntimeError("[%r] has no stage: %s" % (crawler, stage))
        return cls(crawler, stage, state)

    def enforce_rate_limit(self, rate_limit):
        """
        Enforce rate limit for a resource.

        Updates the rate limit counter and blocks if limit exceeded.
        """
        rate_limit.update()
        if not rate_limit.check():
            rate_limit.comply()

    def __repr__(self):
        return "<Context(%r, %r)>" % (self.crawler, self.stage)
