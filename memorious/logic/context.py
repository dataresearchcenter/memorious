"""Execution context for crawler operations."""

from __future__ import annotations

import os
import random
import shutil
import uuid
from copy import deepcopy
from pathlib import Path
from tempfile import mkdtemp
from typing import IO, TYPE_CHECKING, Any, ContextManager

from anystore.logging import get_logger
from anystore.store.base import BaseStore
from anystore.store.virtual import get_virtual
from anystore.tags import Tags
from anystore.util import ensure_uuid
from anystore.util import join_relpaths as make_key
from ftm_lakehouse import get_archive
from ftm_lakehouse.service.archive import DatasetArchive
from servicelayer.rate_limit import RateLimit
from structlog.stdlib import BoundLogger

from memorious.core import get_cache, get_tags, settings
from memorious.logic.check import ContextCheck
from memorious.logic.crawler import Crawler
from memorious.logic.http import ContextHttp
from memorious.model.stage import CrawlerStage
from memorious.settings import Settings

if TYPE_CHECKING:
    from memorious.logic.manager import CrawlerManager


DEFAULT_ORIGIN = "memorious"
CACHE_ORIGIN = "memorious-cache"


class Context:
    """Provides state tracking and methods for operation interactions."""

    crawler: Crawler
    stage: CrawlerStage
    state: dict[str, Any]
    params: dict[str, Any]
    incremental: bool | None
    continue_on_error: bool | None
    run_id: str
    work_path: str
    log: BoundLogger
    http: ContextHttp
    check: ContextCheck
    settings: Settings
    tags: Tags
    archive: DatasetArchive
    cache: BaseStore

    def __init__(self, crawler: Crawler, stage: CrawlerStage, state: dict[str, Any]):
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

        self.settings = settings
        self.archive = get_archive(self.crawler.name)
        self.tags = get_tags(self.crawler.name)
        self.cache = get_cache()

        self.http = ContextHttp(self)
        self.check = ContextCheck(self)

    def get(self, name: str, default: Any = None) -> Any:
        """Get a configuration value and expand environment variables."""
        value = self.params.get(name, default)
        if isinstance(value, str):
            value = os.path.expandvars(value)
        return value

    def emit(
        self,
        rule: str = "pass",
        stage: str | None = None,
        data: dict[str, Any] | None = None,
        delay: int | None = None,
        optional: bool = False,
    ) -> None:
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
            self.log.info("No next stage", stage=stage, rule=rule)
            return

        # Debug sampling
        if self.settings.debug:
            sampling_rate = self.get("sampling_rate")
            if sampling_rate and random.random() > float(sampling_rate):
                self.log.info("Skipping emit due to sampling rate", rate=sampling_rate)
                return

        # Log delay warning (procrastinate supports scheduled_at, but we simplify)
        if delay and delay > 0:
            self.log.debug("Delay requested but not applied", delay=delay)

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

    def recurse(
        self, data: dict[str, Any] | None = None, delay: int | None = None
    ) -> None:
        """Have a stage invoke itself with a modified set of arguments."""
        if data is None:
            data = {}
        return self.emit(stage=self.stage.name, data=data, delay=delay)

    def execute(self, data: dict[str, Any]) -> Any:
        """Execute the stage method with the given data."""
        try:
            self.log.info(
                "Executing stage",
                method=self.stage.method_name,
            )
            return self.stage.method(self, data)
        except Exception as exc:
            self.emit_exception(exc)
            if not self.continue_on_error:
                raise exc
        finally:
            shutil.rmtree(self.work_path)

    def emit_warning(self, message: str, **kwargs: Any) -> None:
        self.log.warning(message, **kwargs)

    def emit_exception(self, exc: Exception) -> None:
        self.log.exception(str(exc))

    def set_tag(self, key: str, value: Any) -> None:
        key = make_key(self.crawler.name, key)
        self.tags.put(key, value)

    def get_tag(self, key: str) -> Any:
        return self.tags.get(make_key(self.crawler.name, key))

    def check_tag(self, key: str) -> bool:
        return self.tags.exists(make_key(self.crawler.name, key))

    def skip_incremental(self, *criteria: str) -> bool:
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

    def store_file(
        self,
        file_path: str | Path,
        origin: str | None = DEFAULT_ORIGIN,
        checksum: str | None = None,
    ) -> str:
        """Put a file into permanent storage so it can be visible to other stages."""
        file_info = self.archive.archive_file(
            file_path, checksum=checksum, origin=origin or DEFAULT_ORIGIN
        )
        return file_info.checksum

    def store_data(self, data: Any, checksum: str | None = None) -> str:
        key = ensure_uuid()
        with get_virtual() as v:
            v.store.put(key, data, serialization_mode="auto")
            return self.store_file(
                v.store.get_key(key), origin=CACHE_ORIGIN, checksum=checksum
            )

    def open(self, content_hash: str) -> ContextManager[IO[bytes]]:
        file_info = self.archive.lookup_file(content_hash)
        return self.archive.open_file(file_info)

    def local_path(self, content_hash: str) -> ContextManager[Path]:
        file_info = self.archive.lookup_file(content_hash)
        return self.archive.local_path(file_info)

    def dump_state(self) -> dict[str, Any]:
        state = deepcopy(self.state)
        state["dataset"] = self.crawler.name
        state["run_id"] = self.run_id
        return state

    @classmethod
    def from_state(
        cls, state: dict[str, Any], stage: str, manager: CrawlerManager
    ) -> Context:
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
        stage_obj = crawler.get(stage)
        if stage_obj is None:
            raise RuntimeError("[%r] has no stage: %s" % (crawler, stage))
        return cls(crawler, stage_obj, state)

    def enforce_rate_limit(self, rate_limit: RateLimit) -> None:
        """
        Enforce rate limit for a resource.

        Updates the rate limit counter and blocks if limit exceeded.
        """
        rate_limit.update()
        if not rate_limit.check():
            rate_limit.comply()

    def __repr__(self) -> str:
        return "<Context(%r, %r)>" % (self.crawler, self.stage)
