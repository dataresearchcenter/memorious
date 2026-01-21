"""Execution context for crawler operations."""

from __future__ import annotations

import os
import random
import shutil
from copy import deepcopy
from datetime import datetime
from io import BytesIO
from pathlib import Path
from tempfile import mkdtemp
from typing import IO, Any, ContextManager, overload

from anystore.logging import get_logger
from anystore.serialize import to_store
from anystore.store.base import BaseStore
from anystore.tags import Tags
from anystore.util import ensure_uuid
from anystore.util import join_relpaths as make_key
from ftm_lakehouse import get_archive, get_entities
from ftm_lakehouse.repository import ArchiveRepository, EntityRepository
from servicelayer.rate_limit import RateLimit
from structlog.stdlib import BoundLogger

from memorious.core import get_cache, get_tags, settings
from memorious.logic.check import ContextCheck
from memorious.logic.crawler import Crawler
from memorious.logic.http import ContextHttp
from memorious.model.stage import CrawlerStage
from memorious.settings import Settings
from memorious.util import make_url_key

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
    archive: ArchiveRepository
    entities: EntityRepository
    cache: BaseStore

    def __init__(self, crawler: Crawler, stage: CrawlerStage, state: dict[str, Any]):
        self.crawler = crawler
        self.stage = stage
        self.state = state
        self.params = stage.params
        self.incremental = state.get("incremental")
        self.continue_on_error = state.get("continue_on_error")
        self.run_id = state.get("run_id") or ensure_uuid()
        self.work_path = mkdtemp()
        self.log = get_logger(
            "%s.%s" % (crawler.name, stage.name),
            dataset=crawler.name,
            stage=stage.name,
            run_id=self.run_id,
        )

        self.settings = settings
        self.archive = get_archive(self.crawler.name)
        self.entities = get_entities(self.crawler.name)
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

    @overload
    def make_key(self, __part1: str, *parts: str, prefix: str | None = ...) -> str: ...

    @overload
    def make_key(self, *, prefix: str | None = ...) -> None: ...

    def make_key(self, *parts: str, prefix: str | None = None) -> str | None:
        """Create a namespaced key with the crawler name prefix.

        Args:
            *parts: Key parts to join. If empty/None, returns None.
            prefix: Optional prefix added after crawler name but not part
                of the None check. Useful for categorizing keys (e.g. "inc", "emit").

        Returns:
            Namespaced key string, or None if parts are empty.
        """
        key = make_key(*parts)
        if key is None:
            return None
        if key.startswith(self.crawler.name):  # erf
            key = key[len(self.crawler.name) + 1 :]
        if prefix:
            key = make_key(prefix, key)
        return make_key(self.crawler.name, key)

    def _make_emit_cache_key(self, data: dict[str, Any]) -> str | None:
        """Generate a cache key for incremental emit tracking.

        Uses content_hash if available, otherwise url, otherwise None.
        """
        cache_key = data.get("emit_cache_key")
        if cache_key:
            return self.make_key(cache_key, prefix="emit")
        foreign_id = data.get("foreign_id")
        if foreign_id:
            return self.make_key(foreign_id, prefix="emit")
        content_hash = data.get("content_hash")
        if content_hash:
            return self.make_key(content_hash, prefix="emit")
        url = data.get("url")
        if url:
            return self.make_key(make_url_key(url), prefix="emit")
        return None

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

        # Incremental: skip if already processed (cache key exists)
        if self.incremental:
            cache_key = self._make_emit_cache_key(data)
            if cache_key and self.check_tag(cache_key):
                self.log.info("Skipping emit (incremental)", cache_key=cache_key)
                return
            # Store cache key in data for marking complete at store stage
            data["_emit_cache_key"] = cache_key

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

    def mark_emit_complete(self, data: dict[str, Any]) -> None:
        """Mark an emit cache key as complete.

        Called by store operations after successful storage to enable
        incremental skipping on future runs.
        """
        cache_key = data.get("_emit_cache_key")
        if cache_key:
            self.set_tag(cache_key, datetime.now())
            self.log.debug("Marked emit complete", cache_key=cache_key)

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
        if not key or not key.strip():
            self.log.warning("Ignoring empty tag key")
            return
        self.tags.put(self.make_key(key), value)

    def get_tag(self, key: str) -> Any:
        if not key or not key.strip():
            self.log.warning("Ignoring empty tag key")
            return None
        return self.tags.get(self.make_key(key))

    def check_tag(self, key: str) -> bool:
        if not key or not key.strip():
            self.log.warning("Ignoring empty tag key")
            return False
        return self.tags.exists(self.make_key(key))

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

        key = self.make_key(*criteria, prefix="inc")
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
        file_info = self.archive.store(
            file_path, checksum=checksum, origin=origin or DEFAULT_ORIGIN
        )
        return file_info.checksum

    def store_data(self, data: Any, checksum: str | None = None) -> str:
        fh = BytesIO(to_store(data))
        return self.archive.write_blob(fh, checksum=checksum)

    def open(self, content_hash: str) -> ContextManager[IO[bytes]]:
        return self.archive.open(content_hash)

    def local_path(self, content_hash: str) -> ContextManager[Path]:
        return self.archive.local_path(content_hash)

    def dump_state(self) -> dict[str, Any]:
        state = deepcopy(self.state)
        state["dataset"] = self.crawler.name
        state["run_id"] = self.run_id
        return state

    @classmethod
    def from_state(
        cls, state: dict[str, Any], stage: str, config_file: str
    ) -> "Context":
        """Create a Context from serialized state.

        Args:
            state: Serialized state dict containing dataset name and run_id
            stage: Stage name to execute
            config_file: Path or URI to crawler config file
        """
        from memorious.logic.crawler import get_crawler

        crawler = get_crawler(config_file)
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
