# Memorious Refactoring Plan

This document outlines a comprehensive refactoring plan to modernize memorious using pydantic-settings, openaleph-procrastinate, anystore, and ftm_lakehouse.

## Overview

### Current Architecture
```
memorious/
├── settings.py          # Module-level variables using servicelayer.env
├── core.py              # LocalProxy singletons (manager, tags, conn, storage)
├── worker.py            # servicelayer.Worker subclass
├── model/
│   ├── queue.py         # servicelayer.jobs queue wrapper
│   └── crawl.py         # Redis-based crawl state tracking
├── logic/
│   ├── crawler.py       # YAML config loader → Crawler object
│   ├── stage.py         # Stage definition with method resolution
│   ├── context.py       # Execution context passed to operations
│   ├── manager.py       # CrawlerManager loads YAML files
│   ├── http.py          # HTTP client with caching
│   └── check.py         # URL validation
├── operations/          # Built-in stage methods
└── helpers/             # Utility functions
```

### Target Architecture
```
memorious/
├── settings.py          # Pydantic Settings class
├── model/
│   ├── crawler.py       # CrawlerConfig(ftmq.model.Dataset) pydantic model
│   ├── stage.py         # StageConfig pydantic model
│   └── job.py           # CrawlerJob(openaleph_procrastinate.model.Job)
├── tasks.py             # Single procrastinate task definition
├── logic/
│   ├── context.py       # Execution context (with Tags/Archive initialized directly)
│   ├── crawler.py       # Crawler orchestration
│   ├── http.py          # HTTP client with caching
│   └── operations.py    # Operation registry/resolution
├── operations/          # Built-in stage methods (unchanged)
├── helpers/             # Utility functions (unchanged)
└── cli.py               # Click CLI (adapted for procrastinate)
```

---

## Phase 1: Settings Migration

### 1.1 Convert settings to pydantic-settings

**Current** (`memorious/settings.py`):
```python
import os
import pkg_resources
from servicelayer import env

VERSION = pkg_resources.get_distribution("memorious").version
DEBUG = env.to_bool("MEMORIOUS_DEBUG", default=False)
BASE_PATH = env.get("MEMORIOUS_BASE_PATH", os.path.join(os.getcwd(), "data"))
# ... more module-level variables
```

**Target** (`memorious/settings.py`):
```python
from functools import cached_property
from pathlib import Path
from typing import Literal

from anystore.settings import BaseSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    """
    Memorious configuration using pydantic-settings.

    All settings can be set via environment variables with MEMORIOUS_ prefix.
    """

    model_config = SettingsConfigDict(
        env_prefix="memorious_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    # Core configuration
    app_name: str = Field(default="memorious", alias="app_name")
    base_path: Path = Field(default=Path.cwd() / "data")
    config_path: Path | None = Field(default=None)

    # Crawl behavior
    incremental: bool = Field(default=True)
    continue_on_error: bool = Field(default=False)
    expire_days: int = Field(default=1)

    # Rate limiting
    db_rate_limit: int = Field(default=6000)
    http_rate_limit: int = Field(default=120)
    max_queue_length: int = Field(default=50000)

    # HTTP configuration
    http_cache: bool = Field(default=True)
    http_timeout: float = Field(default=30.0)
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US; rv:1.1) aleph.memorious"
    )

    # Storage - uses ftm_lakehouse conventions
    lakehouse_uri: str = Field(default=".lake")

    # Tags storage - defaults to procrastinate database
    tags_uri: str | None = Field(default=None)

    @cached_property
    def archive_path(self) -> Path:
        return self.base_path / "archive"

    @cached_property
    def tags_store_uri(self) -> str:
        """Tags store URI, defaults to procrastinate database."""
        if self.tags_uri:
            return self.tags_uri
        # Reuse procrastinate database for tags
        from openaleph_procrastinate.settings import OpenAlephSettings
        return OpenAlephSettings().procrastinate_db_uri
```

### 1.2 Migration Steps

1. Create new `memorious/settings.py` with pydantic model
2. Add `@cached_property` for derived paths
3. Update all imports from `from memorious import settings` to use `from memorious.settings import Settings` and then use `settings = Settings()`
4. Remove servicelayer.env dependency for settings

---

## Phase 2: Crawler Configuration as Pydantic Model

### 2.1 Create CrawlerConfig model inheriting from ftmq.model.Dataset

**Target** (`memorious/model/crawler.py`):
```python
from datetime import timedelta
from typing import Any, Literal

from ftmq.model import Dataset
from pydantic import Field, field_validator

from memorious.model.stage import StageConfig


Schedule = Literal["disabled", "hourly", "daily", "weekly", "monthly"]

SCHEDULE_INTERVALS: dict[Schedule, timedelta | None] = {
    "disabled": None,
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "monthly": timedelta(weeks=4),
}


class CrawlerConfig(Dataset):
    """
    Crawler configuration model.

    Inherits from ftmq.model.Dataset to integrate with the FTM ecosystem.
    The `name` field from Dataset serves as the crawler identifier.
    """

    # Crawler-specific fields
    schedule: Schedule = Field(default="disabled")
    init_stage: str = Field(default="init", alias="init")
    delay: int = Field(default=0, ge=0)
    expire: int = Field(default=1, ge=0)  # days
    stealthy: bool = Field(default=False)

    # Pipeline definition
    pipeline: dict[str, StageConfig] = Field(default_factory=dict)

    # Optional aggregator
    aggregator: dict[str, Any] | None = Field(default=None)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        import re
        if not re.match(r"^[A-Za-z0-9_-]+$", v):
            raise ValueError(
                f"Invalid crawler name: {v}. Allowed characters: A-Za-z0-9_-"
            )
        return v

    @property
    def schedule_interval(self) -> timedelta | None:
        return SCHEDULE_INTERVALS.get(self.schedule)

    @property
    def expire_seconds(self) -> int:
        return self.expire * 86400

    def get_stage(self, name: str) -> StageConfig | None:
        return self.pipeline.get(name)

    @classmethod
    def from_yaml_file(cls, path: str) -> "CrawlerConfig":
        """Load crawler config from a YAML file."""
        import yaml
        from pathlib import Path

        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        # Use filename as default name
        if "name" not in data or data["name"] is None:
            data["name"] = Path(path).stem

        return cls(**data)
```

### 2.2 Create StageConfig model

**Target** (`memorious/model/stage.py`):
```python
from typing import Any

from pydantic import BaseModel, Field, field_validator


class StageConfig(BaseModel):
    """Configuration for a single pipeline stage."""

    method: str = Field(..., description="Method name or module:function path")
    params: dict[str, Any] = Field(default_factory=dict)
    handle: dict[str, str] = Field(default_factory=dict)

    # Runtime-populated fields
    name: str | None = Field(default=None, exclude=True)
    crawler_name: str | None = Field(default=None, exclude=True)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        import re
        if not re.match(r"^[A-Za-z0-9_-]+$", v):
            raise ValueError(
                f"Invalid stage name: {v}. Allowed characters: A-Za-z0-9_-"
            )
        return v

    @property
    def namespaced_name(self) -> str:
        return f"{self.crawler_name}.{self.name}"

    def get_handler(self, rule: str) -> str | None:
        """Get the target stage for a given handler rule."""
        return self.handle.get(rule)
```

### 2.3 Migration Steps

1. Create `memorious/model/` package with `__init__.py`
2. Create `crawler.py` and `stage.py` models
3. Update `CrawlerManager` to use `CrawlerConfig.from_yaml_file()`
4. Update all code that accesses crawler/stage attributes

---

## Phase 3: Replace Worker/Queue with openaleph-procrastinate

This is the most significant change. The current architecture uses servicelayer's Redis-based job queue. We'll replace it with procrastinate (PostgreSQL-backed).

### 3.1 Create Job Model

**Target** (`memorious/model/job.py`):
```python
from typing import Any

from openaleph_procrastinate.model import Job
from pydantic import Field


class CrawlerJob(Job):
    """
    A memorious crawler task job.

    Inherits from openaleph_procrastinate.Job to integrate with the task queue.
    """

    crawler: str = Field(..., description="Crawler name")
    stage: str = Field(..., description="Stage name to execute")
    run_id: str = Field(..., description="Unique run identifier")
    incremental: bool = Field(default=True)
    continue_on_error: bool = Field(default=False)

    # Stage input data
    data: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        crawler: str,
        stage: str,
        run_id: str,
        data: dict[str, Any],
        queue: str = "memorious",
        task: str = "memorious.tasks.execute_stage",
        **context: Any,
    ) -> "CrawlerJob":
        """Create a new crawler job."""
        return cls(
            queue=queue,
            task=task,
            crawler=crawler,
            stage=stage,
            run_id=run_id,
            data=data,
            payload={
                "crawler": crawler,
                "stage": stage,
                "run_id": run_id,
                "data": data,
                **context,
            },
        )
```

### 3.2 Create Tasks Module

**Target** (`memorious/tasks.py`):
```python
"""
Memorious procrastinate task definitions.

This module defines a single task that handles all crawler stage executions.
The task receives the stage payload, executes the appropriate operation,
and defers new tasks for subsequent stages.
"""
from typing import Any

from anystore.logging import get_logger
from openaleph_procrastinate.app import App, make_app
from openaleph_procrastinate.tasks import task

from memorious.logic.context import Context
from memorious.logic.crawler import get_crawler
from memorious.model.job import CrawlerJob
from memorious.settings import get_settings

log = get_logger(__name__)

# Create the procrastinate app
app = make_app(tasks_module="memorious.tasks")


@task(app=app, retry=3)
def execute_stage(job: CrawlerJob) -> None:
    """
    Execute a single crawler stage.

    This is the main entry point for all crawler operations. It:
    1. Loads the crawler configuration
    2. Creates an execution context
    3. Executes the stage method
    4. The context.emit() calls will defer new jobs for subsequent stages
    """
    settings = get_settings()

    log.info(
        "Executing stage",
        crawler=job.crawler,
        stage=job.stage,
        run_id=job.run_id,
    )

    # Load crawler and stage configuration
    crawler = get_crawler(job.crawler)
    if crawler is None:
        log.error(f"Crawler not found: {job.crawler}")
        return

    stage_config = crawler.get_stage(job.stage)
    if stage_config is None:
        log.error(f"Stage not found: {job.stage} in crawler {job.crawler}")
        return

    # Create execution context
    context = Context(
        app=app,
        crawler=crawler,
        stage=stage_config,
        run_id=job.run_id,
        incremental=job.incremental,
        continue_on_error=job.continue_on_error,
    )

    # Execute the stage
    try:
        context.execute(job.data)
    except Exception as exc:
        log.exception(f"Stage execution failed: {exc}")
        if not job.continue_on_error:
            raise


def defer_stage(
    crawler: str,
    stage: str,
    run_id: str,
    data: dict[str, Any],
    priority: int | None = None,
) -> None:
    """
    Defer a new stage execution job.

    This is called by Context.emit() to queue subsequent stages.
    """
    job = CrawlerJob.create(
        crawler=crawler,
        stage=stage,
        run_id=run_id,
        data=data,
    )
    job.defer(app, priority=priority or 50)
    log.debug(
        "Deferred stage",
        crawler=crawler,
        stage=stage,
        run_id=run_id,
    )
```

### 3.3 Refactor Context to use procrastinate

**Target** (`memorious/logic/context.py`) - Key changes:
```python
import logging
import os
import uuid
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from tempfile import mkdtemp
from typing import Any, Generator

from openaleph_procrastinate.app import App

from anystore.store import get_store
from anystore.tags import Tags

from ftm_lakehouse import get_archive

from memorious.model.crawler import CrawlerConfig
from memorious.model.stage import StageConfig
from memorious.logic.http import ContextHttp
from memorious.settings import get_settings


class Context:
    """
    Provides state tracking and methods for operation interactions.

    Refactored to use:
    - openaleph-procrastinate for task deferral
    - anystore.Tags for tag storage (initialized directly)
    - ftm_lakehouse.DatasetArchive for file storage (initialized directly)
    """

    def __init__(
        self,
        app: App,
        crawler: CrawlerConfig,
        stage: StageConfig,
        run_id: str,
        incremental: bool = True,
        continue_on_error: bool = False,
    ):
        self.app = app
        self.crawler = crawler
        self.stage = stage
        self.params = stage.params
        self.run_id = run_id or uuid.uuid4().hex
        self.incremental = incremental
        self.continue_on_error = continue_on_error

        # Settings
        self.settings = get_settings()

        # Initialize tags storage directly
        tags_store = get_store(self.settings.tags_store_uri, raise_on_nonexist=False)
        self._tags = Tags(tags_store)

        # Initialize archive directly
        self._archive = get_archive(self.crawler.name)

        # Working directory for temporary files
        self.work_path = Path(mkdtemp())

        # Logger with context
        self.log = logging.getLogger(f"{crawler.name}.{stage.name}")

        # HTTP client (lazy initialized)
        self._http: ContextHttp | None = None

    @property
    def http(self) -> ContextHttp:
        if self._http is None:
            self._http = ContextHttp(self)
        return self._http

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
        Defer execution of the next stage via procrastinate.

        Args:
            rule: Handler rule name to determine target stage
            stage: Explicit target stage (overrides rule lookup)
            data: Data to pass to the next stage
            delay: Delay in seconds before execution (not supported, logged as warning)
            optional: If True, silently skip if no target stage found
        """
        from memorious.tasks import defer_stage

        data = deepcopy(data or {})

        # Resolve target stage
        if stage is None:
            stage = self.stage.get_handler(rule)

        if stage is None:
            if optional:
                return
            self.log.info(f"No next stage for rule: {rule}")
            return

        # Verify stage exists in crawler
        if self.crawler.get_stage(stage) is None:
            self.log.warning(f"Target stage not found: {stage}")
            return

        # Log delay warning (procrastinate supports scheduled_at, but we simplify)
        if delay and delay > 0:
            self.log.debug(f"Delay of {delay}s requested but not applied")

        # Defer the job
        defer_stage(
            crawler=self.crawler.name,
            stage=stage,
            run_id=self.run_id,
            data=data,
        )

    def recurse(self, data: dict[str, Any] | None = None, delay: int | None = None) -> None:
        """Have a stage invoke itself with modified arguments."""
        self.emit(stage=self.stage.name, data=data or {}, delay=delay)

    # Tag operations using anystore.Tags
    def set_tag(self, key: str, value: Any) -> None:
        """Set a tag value."""
        tag_key = f"{self.crawler.name}/tag/{key}"
        self._tags.put(tag_key, value)

    def get_tag(self, key: str) -> Any:
        """Get a tag value."""
        tag_key = f"{self.crawler.name}/tag/{key}"
        return self._tags.get(tag_key)

    def check_tag(self, key: str) -> bool:
        """Check if a tag exists."""
        tag_key = f"{self.crawler.name}/tag/{key}"
        return self._tags.exists(tag_key)

    def skip_incremental(self, *criteria: Any) -> bool:
        """
        Perform an incremental check on a set of criteria.

        Returns True if the operation should be skipped (already done).
        """
        if not self.incremental:
            return False

        from anystore.util import make_key
        key = make_key("inc", *criteria)
        if key is None:
            return False

        if self.check_tag(key):
            return True

        self.set_tag(key, "inc")
        return False

    # File storage using ftm_lakehouse.DatasetArchive
    def store_file(self, file_path: str | Path, content_hash: str | None = None) -> str:
        """Archive a file and return its content hash."""
        file = self._archive.archive_file(str(file_path))
        return file.checksum

    def store_data(self, data: str | bytes, encoding: str = "utf-8") -> str:
        """Store data as a file and return its content hash."""
        import tempfile

        if isinstance(data, str):
            data = data.encode(encoding)

        with tempfile.NamedTemporaryFile(
            dir=self.work_path, delete=False
        ) as fh:
            fh.write(data)
            temp_path = fh.name

        try:
            return self.store_file(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @contextmanager
    def load_file(
        self,
        content_hash: str,
        file_name: str | None = None,
        read_mode: str = "rb",
    ) -> Generator[Any, None, None]:
        """Load a file from the archive."""
        from ftm_lakehouse.model import File

        try:
            file = self._archive.lookup_file(content_hash)
            with self._archive.open_file(file) as fh:
                yield fh
        except Exception:
            yield None

    def execute(self, data: dict[str, Any]) -> Any:
        """Execute the stage method with the given data."""
        from memorious.logic.operations import resolve_method

        try:
            self.log.info(
                f"[{self.crawler.name}->{self.stage.name}({self.stage.method})]: {self.run_id}"
            )
            method = resolve_method(self.stage.method)
            return method(self, data)
        except Exception as exc:
            self.log.exception(exc)
            if not self.continue_on_error:
                raise
        finally:
            # Cleanup work directory
            import shutil
            shutil.rmtree(self.work_path, ignore_errors=True)
```

### 3.4 Migration Steps

1. Add `openaleph-procrastinate` to dependencies
2. Create `memorious/model/job.py`
3. Create `memorious/tasks.py` with single task definition
4. Refactor `Context` to use `defer_stage()` instead of `Queue.queue()`
5. Remove `memorious/worker.py`
6. Remove `memorious/model/queue.py`
7. Update CLI to use procrastinate worker commands
8. Update database setup to use procrastinate migrations

---

## Phase 4: Tags Interface Migration

Tags are initialized directly in Context using `anystore.Tags`. No separate service module needed.

### 4.1 API Migration

The `anystore.Tags` interface is similar to servicelayer but uses different method names:

| servicelayer.tags | anystore.Tags |
|-------------------|---------------|
| `tags.set(key, value)` | `tags.put(key, value)` |
| `tags.get(key)` | `tags.get(key)` |
| `tags.exists(key)` | `tags.exists(key)` |
| `tags.delete(prefix=...)` | `tags.delete(prefix=...)` |

### 4.2 Context Integration

Tags are initialized directly in `Context.__init__()`:
```python
from anystore.store import get_store
from anystore.tags import Tags

# In Context.__init__():
tags_store = get_store(self.settings.tags_store_uri, raise_on_nonexist=False)
self._tags = Tags(tags_store)
```

### 4.3 Migration Steps

1. Update `Context.__init__()` to initialize `anystore.Tags` directly
2. Update tag method calls: `set()` → `put()`
3. Remove `servicelayer.tags` dependency

---

## Phase 5: Archive Layer Migration

Archive is initialized directly in Context using `ftm_lakehouse.get_archive()`. No separate service module needed.

### 5.1 Context Integration

Archive is initialized directly in `Context.__init__()`:
```python
from ftm_lakehouse import get_archive

# In Context.__init__():
self._archive = get_archive(self.crawler.name)
```

### 5.2 API Mapping

| servicelayer.archive | ftm_lakehouse.DatasetArchive |
|---------------------|------------------------------|
| `storage.archive_file(path, content_hash)` | `archive.archive_file(uri)` returns `File` |
| `storage.load_file(hash, temp_path)` | `archive.local_path(file)` context manager |
| `storage.cleanup_file(hash)` | Automatic via context manager |

### 5.3 Migration Steps

1. Update `Context.__init__()` to initialize archive via `ftm_lakehouse.get_archive()`
2. Update `Context.store_file()` and `Context.load_file()` to use new API
3. Update `ContextHttpResponse` to use new archive
4. Remove `servicelayer.archive` dependency

---

## Phase 6: Additional Refactoring Suggestions

### 6.1 Layered Architecture

Recommended package structure for clearer separation of concerns:

```
memorious/
├── model/              # Pydantic data models (no business logic)
│   ├── crawler.py      # CrawlerConfig
│   ├── stage.py        # StageConfig
│   ├── job.py          # CrawlerJob
│   └── rules.py        # URL/content filtering rules as pydantic models
│
├── logic/              # Business logic / orchestration
│   ├── context.py      # Execution context (Tags/Archive initialized here)
│   ├── crawler.py      # Crawler loading and management
│   ├── http.py         # HTTP client with caching
│   ├── operations.py   # Operation method resolution
│   └── incremental.py  # Advanced incremental logic
│
├── operations/         # Built-in stage implementations
│   ├── fetch.py
│   ├── parse.py
│   ├── store.py
│   └── ...
│
├── helpers/            # Pure utility functions
│   ├── dates.py
│   ├── ua.py
│   └── ...
│
├── tasks.py            # Procrastinate task definitions
├── settings.py         # Pydantic settings
├── cli.py              # Click CLI
└── __init__.py
```

Note: Tags (`anystore.Tags`) and Archive (`ftm_lakehouse.DatasetArchive`) are initialized directly in `Context.__init__()` rather than through separate service modules, as they require no additional abstraction.

### 6.2 HTTP Client

The HTTP client remains in `memorious/logic/http.py` as `ContextHttp`. It receives the Context instance and uses its `_tags` and `_archive` directly for caching. No separate service module needed.

### 6.3 Operation Registry

Create a cleaner operation resolution system:

**Target** (`memorious/logic/operations.py`):
```python
"""
Operation method registry and resolution.
"""
from importlib import import_module
from typing import Callable, Any

from servicelayer.extensions import get_entry_point


# Type for operation functions
OperationFunc = Callable[["Context", dict[str, Any]], Any]

# Local registry for programmatic registration
_REGISTRY: dict[str, OperationFunc] = {}


def register(name: str):
    """Decorator to register an operation."""
    def decorator(func: OperationFunc) -> OperationFunc:
        _REGISTRY[name] = func
        return func
    return decorator


def resolve_method(method_name: str) -> OperationFunc:
    """
    Resolve an operation method by name.

    Resolution order:
    1. Local registry
    2. Entry point (memorious.operations)
    3. Direct module import (module:function)
    """
    # Check local registry
    if method_name in _REGISTRY:
        return _REGISTRY[method_name]

    # Check entry points
    func = get_entry_point("memorious.operations", method_name)
    if func is not None:
        return func

    # Direct import
    if ":" in method_name:
        package, function = method_name.rsplit(":", 1)
        module = import_module(package)
        return getattr(module, function)

    raise ValueError(f"Unknown operation method: {method_name}")
```

### 6.4 Rules as Pydantic Models

Convert rules to pydantic for validation:

**Target** (`memorious/model/rules.py`):
```python
"""
URL/content filtering rules as Pydantic models.
"""
import re
from typing import Annotated, Literal, Union
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from rigour.mime import normalize_mimetype

from memorious.logic.mime import GROUPS


class BaseRule(BaseModel):
    """Base class for all rules."""

    def apply(self, response: "HttpResponse") -> bool:
        raise NotImplementedError


class OrRule(BaseRule):
    """Any nested rule must match."""
    any_of: list["AnyRule"] = Field(alias="or")

    def apply(self, response) -> bool:
        return any(rule.apply(response) for rule in self.any_of)


class AndRule(BaseRule):
    """All nested rules must match."""
    all_of: list["AnyRule"] = Field(alias="and")

    def apply(self, response) -> bool:
        return all(rule.apply(response) for rule in self.all_of)


class NotRule(BaseRule):
    """Invert a nested rule."""
    negate: "AnyRule" = Field(alias="not")

    def apply(self, response) -> bool:
        return not self.negate.apply(response)


class MatchAllRule(BaseRule):
    """Always matches."""
    match_all: dict = {}

    def apply(self, response) -> bool:
        return True


class DomainRule(BaseRule):
    """Match URLs from a specific domain."""
    domain: str

    def apply(self, response) -> bool:
        parsed = urlparse(response.url)
        hostname = (parsed.hostname or "").lower().strip(".")
        target = self.domain.lower().strip(".")
        return hostname == target or hostname.endswith(f".{target}")


class MimeTypeRule(BaseRule):
    """Match specific MIME type."""
    mime_type: str

    def apply(self, response) -> bool:
        return response.content_type == normalize_mimetype(self.mime_type)


class MimeGroupRule(BaseRule):
    """Match MIME type group (documents, images, etc)."""
    mime_group: str

    def apply(self, response) -> bool:
        ct = response.content_type
        if ct.startswith(f"{self.mime_group}/"):
            return True
        return ct in GROUPS.get(self.mime_group, [])


class PatternRule(BaseRule):
    """Match URL against regex pattern."""
    pattern: str

    def apply(self, response) -> bool:
        regex = re.compile(self.pattern, re.I | re.U)
        return bool(regex.match(response.url))


# Union of all rule types
AnyRule = Annotated[
    Union[OrRule, AndRule, NotRule, MatchAllRule, DomainRule, MimeTypeRule, MimeGroupRule, PatternRule],
    Field(discriminator=None)
]

# Update forward references
OrRule.model_rebuild()
AndRule.model_rebuild()
NotRule.model_rebuild()


def parse_rule(spec: dict) -> AnyRule:
    """Parse a rule specification dict into a Rule model."""
    if "or" in spec or "any" in spec:
        rules = spec.get("or") or spec.get("any")
        return OrRule(any_of=[parse_rule(r) for r in rules])
    if "and" in spec or "all" in spec:
        rules = spec.get("and") or spec.get("all")
        return AndRule(all_of=[parse_rule(r) for r in rules])
    if "not" in spec:
        return NotRule(negate=parse_rule(spec["not"]))
    if "match_all" in spec:
        return MatchAllRule()
    if "domain" in spec:
        return DomainRule(domain=spec["domain"])
    if "mime_type" in spec:
        return MimeTypeRule(mime_type=spec["mime_type"])
    if "mime_group" in spec:
        return MimeGroupRule(mime_group=spec["mime_group"])
    if "pattern" in spec:
        return PatternRule(pattern=spec["pattern"])

    raise ValueError(f"Unknown rule specification: {spec}")
```

---

## Phase 7: CLI Updates

### 7.1 Updated CLI

**Target** (`memorious/cli.py`):
```python
"""
Memorious CLI using Typer and procrastinate.
"""
from pathlib import Path
from typing import Annotated, Optional
from uuid import uuid4

import typer
from rich import print
from rich.console import Console
from rich.table import Table

from memorious.settings import Settings

settings = Settings()
cli = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=settings.debug)
console = Console(stderr=True)


@cli.callback(invoke_without_command=True)
def main(
    version: Annotated[Optional[bool], typer.Option("--version", help="Show version")] = False,
):
    """Crawler framework for documents and structured scrapers."""
    if version:
        from memorious import __version__
        print(__version__)
        raise typer.Exit()


@cli.command("run")
def run_crawler(
    crawler: Annotated[str, typer.Argument(help="Crawler name")],
    incremental: Annotated[bool, typer.Option(help="Run in incremental mode")] = True,
):
    """Queue a crawler for execution."""
    from memorious.logic.crawler import get_crawler
    from memorious.tasks import defer_stage

    config = get_crawler(crawler)
    if config is None:
        console.print(f"[red]Crawler not found: {crawler}[/red]")
        raise typer.Exit(1)

    run_id = uuid4().hex
    console.print(f"Starting crawler [bold]{crawler}[/bold] (run_id: {run_id})")

    defer_stage(
        crawler=crawler,
        stage=config.init_stage,
        run_id=run_id,
        data={},
    )

    console.print(f"Queued initial stage: [green]{config.init_stage}[/green]")


@cli.command("run-file")
def run_file(
    config_path: Annotated[Path, typer.Argument(help="Path to crawler YAML config", exists=True)],
    incremental: Annotated[bool, typer.Option(help="Run in incremental mode")] = True,
):
    """Run a crawler from a YAML config file."""
    from memorious.model.crawler import CrawlerConfig
    from memorious.tasks import defer_stage

    config = CrawlerConfig.from_yaml_file(str(config_path))
    run_id = uuid4().hex

    console.print(f"Starting crawler [bold]{config.name}[/bold] (run_id: {run_id})")

    defer_stage(
        crawler=config.name,
        stage=config.init_stage,
        run_id=run_id,
        data={},
    )


@cli.command("worker")
def worker(
    queues: Annotated[Optional[list[str]], typer.Option("-q", "--queue", help="Queue names")] = None,
    concurrency: Annotated[int, typer.Option("-c", "--concurrency", help="Worker concurrency")] = 1,
):
    """Start a procrastinate worker."""
    from memorious.tasks import app

    queues = queues or ["memorious"]
    console.print(f"Starting worker for queues: [bold]{', '.join(queues)}[/bold]")
    app.run_worker(queues=queues, concurrency=concurrency)


@cli.command("list")
def list_crawlers():
    """List available crawlers."""
    from memorious.logic.crawler import get_all_crawlers

    crawlers = get_all_crawlers()

    table = Table(title="Available Crawlers")
    table.add_column("Name", style="cyan")
    table.add_column("Description")

    for c in crawlers:
        table.add_row(c.name, c.description or c.name)

    console.print(table)


@cli.command("settings")
def show_settings():
    """Show current runtime settings."""
    console.print(settings)
```

---

## Migration Checklist

### Phase 1: Settings
- [ ] Create pydantic Settings class
- [ ] Update all settings imports
- [ ] Remove servicelayer.env usage
- [ ] Update tests

### Phase 2: Crawler Models
- [ ] Create CrawlerConfig model
- [ ] Create StageConfig model
- [ ] Update CrawlerManager
- [ ] Update YAML loading
- [ ] Update tests

### Phase 3: Procrastinate Integration
- [ ] Add openaleph-procrastinate dependency
- [ ] Create CrawlerJob model
- [ ] Create tasks.py module
- [ ] Refactor Context.emit()
- [ ] Remove worker.py
- [ ] Remove model/queue.py
- [ ] Update CLI
- [ ] Setup procrastinate migrations
- [ ] Update tests

### Phase 4: Tags Migration
- [ ] Update Context to initialize anystore.Tags directly
- [ ] Update tag method calls: `set()` → `put()`
- [ ] Remove servicelayer.tags usage
- [ ] Update tests

### Phase 5: Archive Migration
- [ ] Update Context to initialize ftm_lakehouse archive directly
- [ ] Update Context.store_file() and Context.load_file()
- [ ] Update ContextHttpResponse
- [ ] Remove servicelayer.archive usage
- [ ] Update tests

### Phase 6: Additional Refactoring
- [ ] Reorganize package structure
- [ ] Create operations registry
- [ ] Convert rules to pydantic
- [ ] Update tests

### Phase 7: CLI & Documentation
- [ ] Update CLI commands
- [ ] Update CLAUDE.md
- [ ] Update README
- [ ] Update documentation

---

## Dependency Changes

### Remove
```toml
# Remove from dependencies
# servicelayer (most functionality replaced)
```

### Add/Update
```toml
[project.dependencies]
# Core
pydantic = ">=2.0"
pydantic-settings = ">=2.0"

# Task queue
openaleph-procrastinate = ">=5.0"

# Storage
anystore = ">=0.4"
ftm-lakehouse = ">=0.1"
ftmq = ">=4.0"

# CLI and utilities
typer = ">=0.9"
rich = ">=13.0"

# Keep existing
requests = ">=2.0"
lxml = ">=5.0"
pyyaml = ">=6.0"
```

---

## Testing Strategy

1. **Unit tests**: Test each model and Context methods in isolation
2. **Integration tests**: Test task execution with in-memory procrastinate
3. **Migration tests**: Verify backward compatibility with existing YAML configs
4. **E2E tests**: Run sample crawlers against test fixtures

Example test setup for procrastinate:
```python
import pytest
from openaleph_procrastinate.app import make_app

@pytest.fixture
def app():
    """Create in-memory procrastinate app for testing."""
    import os
    os.environ["OPENALEPH_DB_URI"] = "memory://"
    return make_app(tasks_module="memorious.tasks", sync=True)
```

---

## Phase 8: Inline memorious_extended Module

The `memorious_extended` module contains valuable helper functions and enhanced operations that should be integrated into the core library.

### 8.1 Module Overview

| Source File | Target Location | Description |
|-------------|-----------------|-------------|
| `yaml.py` | `memorious/helpers/yaml.py` | YAML loader with `!include` support |
| `exceptions.py` | `memorious/exc.py` | Custom exceptions (merge) |
| `util.py` | `memorious/helpers/` | Split into template, xpath, casting, regex |
| `forms.py` | `memorious/helpers/forms.py` | HTML form extraction |
| `pagination.py` | `memorious/helpers/pagination.py` | Pagination utilities |
| `incremental.py` | `memorious/logic/incremental.py` | Advanced incremental logic |
| `operations/http.py` | `memorious/operations/fetch.py` | POST operations (merge) |
| `operations/parse.py` | `memorious/operations/parse.py` | Listing, jq, csv, xml parsing (merge) |
| `operations/clean.py` | `memorious/operations/clean.py` | Data cleaning (replace) |
| `operations/extract.py` | `memorious/operations/extract.py` | regex_groups (merge) |
| `operations/store.py` | `memorious/operations/store.py` | Incremental marking (extend) |
| `operations/debug.py` | `memorious/operations/debug.py` | ipdb debugger (extend) |
| `operations/db.py` | `memorious/operations/db.py` | Database operations (merge) |

### 8.2 Exceptions Integration

**Add to** `memorious/exc.py`:
```python
class MetaDataError(Exception):
    """Raised when required metadata is missing or invalid."""
    pass

class RegexError(Exception):
    """Raised when regex extraction fails."""
    pass

class XPathError(Exception):
    """Raised when XPath extraction fails."""
    pass
```

### 8.3 YAML Loader with !include

**Create** `memorious/helpers/yaml.py`:
```python
"""YAML loader with !include constructor support."""
import json
import os
from pathlib import Path
from typing import IO, Any

import yaml


class IncludeLoader(yaml.SafeLoader):
    """YAML Loader with !include constructor."""

    def __init__(self, stream: IO) -> None:
        try:
            self._root = Path(stream.name).parent
        except AttributeError:
            self._root = Path.cwd()
        super().__init__(stream)


def _construct_include(loader: IncludeLoader, node: yaml.Node) -> Any:
    """Include file referenced at node."""
    filename = (loader._root / loader.construct_scalar(node)).resolve()
    ext = filename.suffix.lstrip(".")

    with open(filename) as f:
        if ext in ("yaml", "yml"):
            return yaml.load(f, IncludeLoader)
        elif ext == "json":
            return json.load(f)
        return f.read()


yaml.add_constructor("!include", _construct_include, IncludeLoader)


def load_yaml(path: str | Path) -> dict:
    """Load YAML file with !include support."""
    with open(path, encoding="utf-8") as fh:
        return yaml.load(fh, IncludeLoader)
```

### 8.4 Utility Helpers

**Create** `memorious/helpers/template.py`:
```python
"""Jinja2 templating utilities."""
from jinja2 import BaseLoader, Environment

def render_template(template: str, data: dict) -> str:
    """Render a Jinja2 template string with data."""
    env = Environment(loader=BaseLoader())
    return env.from_string(template).render(**data)
```

**Create** `memorious/helpers/xpath.py`:
```python
"""XPath extraction utilities."""
from typing import Any
from memorious.exc import XPathError

def extract_xpath(html, path: str) -> Any:
    """Extract value from HTML using XPath."""
    result = html.xpath(path)
    if isinstance(result, list) and len(result) == 1:
        result = result[0]
    if hasattr(result, "text"):
        result = result.text
    if isinstance(result, str):
        return result.strip()
    return result
```

**Create** `memorious/helpers/casting.py`:
```python
"""Type casting utilities for scraped data."""
from datetime import datetime
from typing import Any
from memorious.helpers.dates import ensure_date

def cast_value(value: Any, with_date: bool = False, **datekwargs) -> Any:
    """Cast value to int/float/date as appropriate."""
    if not isinstance(value, (str, float, int)):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        f = float(value)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        pass
    if with_date:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return ensure_date(value, **datekwargs) or value
    return value

def cast_dict(data: dict, ignore_keys: list[str] | None = None, **kwargs) -> dict:
    """Cast all values in a dictionary."""
    ignore = ignore_keys or []
    return {k: cast_value(v, with_date=True, **kwargs) if k not in ignore else v
            for k, v in data.items()}
```

**Create** `memorious/helpers/regex.py`:
```python
"""Regex extraction utilities."""
import re
from memorious.exc import RegexError

def regex_first(pattern: str, string: str) -> str:
    """Extract first regex match or raise RegexError."""
    matches = re.findall(pattern, string)
    if matches:
        return matches[0].strip()
    raise RegexError(f"No match for: {pattern}", string)
```

### 8.5 Forms Helper

**Create** `memorious/helpers/forms.py`:
```python
"""HTML form extraction utilities."""
from typing import Any

def extract_form(html, xpath: str) -> tuple[str | None, dict[str, Any]]:
    """Extract form action and field values."""
    form = html.find(xpath)
    if form is None:
        return None, {}

    action = form.xpath("@action")
    action = action[0] if action else None

    data = {}
    for el in form.findall(".//input"):
        if el.name:
            data[el.name] = el.value
    for el in form.findall(".//select"):
        if el.name:
            data[el.name] = el.value

    return action, data
```

### 8.6 Pagination Helper

**Create** `memorious/helpers/pagination.py`:
```python
"""Pagination utilities for web crawlers."""
from banal import ensure_dict
from furl import furl
from memorious.helpers.xpath import extract_xpath
from memorious.helpers.regex import regex_first

def get_paginated_url(url: str, page: int, param: str = "page") -> str:
    """Apply page number to URL query parameter."""
    f = furl(url)
    f.args[param] = page
    return f.url

def calculate_next_page(html, current: int, config: dict) -> int | None:
    """Determine next page number from config."""
    config = ensure_dict(config)

    if "total" in config and "per_page" in config:
        total = _get_int(html, config["total"])
        per_page = _get_int(html, config["per_page"])
        if current * per_page < total:
            return current + 1

    if "total_pages" in config:
        total_pages = _get_int(html, config["total_pages"])
        if current < total_pages:
            return current + 1

    return None

def _get_int(html, value) -> int:
    if isinstance(value, int):
        return value
    extracted = extract_xpath(html, value)
    return int(regex_first(r"\d+", str(extracted)))

def paginate(context, data: dict, html) -> None:
    """Emit next page if pagination indicates more pages."""
    config = context.params.get("pagination")
    if not config:
        return

    config = ensure_dict(config)
    current = data.get("page", 1)
    next_page = calculate_next_page(html, current, config)

    if next_page:
        context.log.info(f"Next page: {next_page}")
        next_data = {**data, "page": next_page}
        param = config.get("param", "page")
        if "url" in next_data:
            next_data["url"] = get_paginated_url(next_data["url"], next_page, param)
        context.emit(rule="next_page", data=next_data)
```

### 8.7 Advanced Incremental Logic

**Create** `memorious/logic/incremental.py`:
```python
"""Advanced incremental crawling with target-based skipping."""
import re
from banal import ensure_dict, ensure_list
from memorious.helpers.xpath import extract_xpath
from memorious.settings import get_settings

def should_skip_incremental(context, data: dict, config: dict | None = None) -> bool:
    """
    Check if stage should be skipped based on target completion.

    Config:
        key:
            data: [list of data keys to use as identifier]
            xpath: XPath to extract identifier
            urlpattern: Regex to match URL
        target: Target stage name (default: "store")
    """
    settings = get_settings()
    if not settings.incremental:
        return False

    config = config or context.params.get("skip_incremental")
    if not config:
        return False

    config = ensure_dict(config)
    key_config = ensure_dict(config.get("key"))
    identifier = None

    # Try data keys
    for key in ensure_list(key_config.get("data")):
        if key in data:
            identifier = data[key]
            break

    # Try URL pattern
    if identifier is None and key_config.get("urlpattern"):
        url = data.get("url", "")
        if re.match(key_config["urlpattern"], url):
            identifier = url

    # Try XPath
    if identifier is None and key_config.get("xpath"):
        result = context.http.rehash(data)
        if hasattr(result, "html") and result.html is not None:
            identifier = extract_xpath(result.html, key_config["xpath"])

    # Default to URL
    identifier = identifier or data.get("url")

    if identifier:
        target = config.get("target", "store")
        target_key = f"skip_incremental:{identifier}:{target}"
        data["skip_incremental"] = {"target": target, "key": target_key}

        if context.check_tag(target_key):
            context.log.info(f"Skipping (incremental): {target_key}")
            return True

    return False

def mark_incremental_complete(context, data: dict) -> None:
    """Mark incremental target as complete."""
    incremental = ensure_dict(data.get("skip_incremental"))
    if incremental.get("target") == context.stage.name:
        key = incremental.get("key")
        if key:
            context.set_tag(key, True)
```

### 8.8 Enhanced Operations

#### HTTP Operations (extend `fetch.py`)

Add to `memorious/operations/fetch.py`:
```python
from memorious.helpers.forms import extract_form
from memorious.helpers.template import render_template
from memorious.logic.incremental import should_skip_incremental

def post(context, data: dict) -> None:
    """HTTP POST with form data."""
    url = context.params.get("url", data.get("url"))
    post_data = ensure_dict(context.params.get("data"))
    for k, v in ensure_dict(context.params.get("use_data")).items():
        if v in data:
            post_data[k] = data[v]
    result = context.http.post(url, data=clean_dict(post_data))
    context.emit(data={**data, **result.serialize()})

def post_json(context, data: dict) -> None:
    """HTTP POST with JSON body."""
    url = context.params.get("url", data.get("url"))
    json_data = ensure_dict(context.params.get("data"))
    for k, v in ensure_dict(context.params.get("use_data")).items():
        if v in data:
            json_data[k] = data[v]
    result = context.http.post(url, json=clean_dict(json_data))
    context.emit(data={**data, **result.serialize()})

def post_form(context, data: dict) -> None:
    """HTTP POST to HTML form with extracted values."""
    form_xpath = context.params.get("form")
    result = context.http.rehash(data)
    action, form_data = extract_form(result.html, form_xpath)
    if action is None:
        context.log.error(f"Form not found: {form_xpath}")
        return
    url = furl(data.get("url", "")).join(action).url
    form_data.update(ensure_dict(context.params.get("data")))
    result = context.http.post(url, data=form_data)
    context.emit(data={**data, **result.serialize()})
```

#### Parse Operations (extend `parse.py`)

Add to `memorious/operations/parse.py`:
```python
import csv
import jq
from memorious.helpers.pagination import paginate
from memorious.logic.incremental import should_skip_incremental

def parse_listing(context, data: dict) -> None:
    """Parse HTML listing with multiple items."""
    if should_skip_incremental(context, data):
        return
    items_xpath = context.params.get("items")
    with context.http.rehash(data) as result:
        if result.html is not None:
            for item in result.html.xpath(items_xpath):
                item_data = {**data}
                parse_for_metadata(context, item_data, item)
                if not should_skip_incremental(context, item_data):
                    context.emit(rule="item", data=item_data)
            paginate(context, data, result.html)

def parse_jq(context, data: dict) -> None:
    """Parse JSON using jq patterns."""
    result = context.http.rehash(data)
    pattern = context.params["pattern"]
    for item in jq.compile(pattern).input(result.json).all():
        context.emit(data={**data, **item})

def parse_csv(context, data: dict) -> None:
    """Parse CSV file."""
    result = context.http.rehash(data)
    kwargs = ensure_dict(context.params)
    skiprows = kwargs.pop("skiprows", 0)
    rows = []
    with open(result.file_path) as fh:
        reader = csv.DictReader(fh, **kwargs)
        for _ in range(skiprows):
            next(reader, None)
        for row in reader:
            context.emit(rule="row", data=row, optional=True)
            rows.append(row)
    context.emit(rule="rows", data={**data, "rows": rows})

def parse_xml(context, data: dict) -> None:
    """Parse XML and extract metadata."""
    result = context.http.rehash(data)
    if result.xml is not None:
        parse_for_metadata(context, data, result.xml)
    context.emit(data=data)
```

#### Clean Operation (replace `clean.py`)

Replace `memorious/operations/clean.py`:
```python
"""Data cleaning and validation operations."""
from banal import ensure_dict, ensure_list, is_mapping
from lxml import html
from memorious.exc import MetaDataError
from memorious.helpers.casting import cast_dict

def clean_html(context, data: dict) -> None:
    """Clean HTML by removing elements."""
    with context.http.rehash(data) as result:
        if not result.ok or result.html is None:
            context.emit(data=data)
            return
        doc = result.html
        for path in ensure_list(context.params.get("remove_paths")):
            for el in doc.xpath(path):
                el.drop_tree()
        content_hash = context.store_data(html.tostring(doc, pretty_print=True))
        data["content_hash"] = content_hash
        context.emit(data=data)

def clean(context, data: dict) -> None:
    """Clean and validate metadata."""
    # Drop keys
    for key in ensure_list(context.params.get("drop")):
        data.pop(key, None)

    # Set defaults
    for key, value in ensure_dict(context.params.get("defaults")).items():
        if key not in data:
            data[key] = value

    # Rewrite values
    for key, values in ensure_dict(context.params.get("values")).items():
        if is_mapping(values) and data.get(key) in values:
            data[key] = values[data[key]]
        elif isinstance(values, str):
            data[key] = values.format(**data)

    # Validate required
    for key in ensure_list(context.params.get("required")):
        if key not in data:
            raise MetaDataError(f"`{key}` required but missing")

    # Type casting
    typing = ensure_dict(context.params.get("typing"))
    if typing:
        data = cast_dict(data, ensure_list(typing.get("ignore")))

    context.emit(data=data)
```

#### Regex Groups Operation (add to `extract.py`)

Add to `memorious/operations/extract.py`:
```python
import re
from banal import clean_dict, ensure_dict, ensure_list, is_mapping

def regex_groups(context, data: dict) -> None:
    """Extract named regex groups from data values."""
    for key, patterns in ensure_dict(context.params).items():
        if is_mapping(patterns):
            config = dict(patterns)
            if key not in data:
                continue
            pattern_list = ensure_list(config.get("pattern", config.get("patterns")))
            store_key = config.get("store_as", key)
            separator = config.get("split")

            if separator:
                result = [_extract(key, v, pattern_list) for v in data[key].split(separator)]
            else:
                result = _extract(key, data, pattern_list)
            data[store_key] = result
        else:
            data.update(_extract(key, data, ensure_list(patterns)))
    context.emit(data=data)

def _extract(key, value, patterns):
    if is_mapping(value):
        value = value.get(key)
    if value is None:
        return {}
    for p in patterns:
        m = re.match(p, str(value))
        if m:
            return {k: v.strip() for k, v in clean_dict(m.groupdict()).items()}
    return {}
```

#### Store Operation (extend)

Add to `memorious/operations/store.py`:
```python
from memorious.logic.incremental import mark_incremental_complete

def store(context, data: dict) -> None:
    """Store with incremental completion marking."""
    from memorious.logic.operations import resolve_method
    method = resolve_method(context.params.get("operation", "directory"))
    method(context, data)
    mark_incremental_complete(context, data)
```

#### Debug Operation (extend)

Add to `memorious/operations/debug.py`:
```python
def ipdb(context, data: dict) -> None:
    """Drop into ipdb debugger."""
    cn = context  # noqa
    import ipdb
    ipdb.set_trace()
```

### 8.9 Entry Points Update

Add to `pyproject.toml`:
```toml
[project.entry-points."memorious.operations"]
# New operations from memorious_extended
post = "memorious.operations.fetch:post"
post_json = "memorious.operations.fetch:post_json"
post_form = "memorious.operations.fetch:post_form"
parse_listing = "memorious.operations.parse:parse_listing"
parse_jq = "memorious.operations.parse:parse_jq"
parse_csv = "memorious.operations.parse:parse_csv"
parse_xml = "memorious.operations.parse:parse_xml"
clean = "memorious.operations.clean:clean"
regex_groups = "memorious.operations.extract:regex_groups"
store = "memorious.operations.store:store"
ipdb = "memorious.operations.debug:ipdb"
```

### 8.10 New Dependencies

Add to `pyproject.toml`:
```toml
jq = ">=1.6"
furl = ">=2.1"
jinja2 = ">=3.0"
```

### 8.11 Migration Checklist

- [ ] Create `memorious/helpers/yaml.py`
- [ ] Add exceptions to `memorious/exc.py`
- [ ] Create `memorious/helpers/template.py`
- [ ] Create `memorious/helpers/xpath.py`
- [ ] Create `memorious/helpers/casting.py`
- [ ] Create `memorious/helpers/regex.py`
- [ ] Extend `memorious/helpers/dates.py`
- [ ] Create `memorious/helpers/forms.py`
- [ ] Create `memorious/helpers/pagination.py`
- [ ] Create `memorious/logic/incremental.py`
- [ ] Extend `memorious/operations/fetch.py`
- [ ] Extend `memorious/operations/parse.py`
- [ ] Replace `memorious/operations/clean.py`
- [ ] Extend `memorious/operations/extract.py`
- [ ] Extend `memorious/operations/store.py`
- [ ] Extend `memorious/operations/debug.py`
- [ ] Update entry points in `pyproject.toml`
- [ ] Add dependencies (jq, furl, jinja2)
- [ ] Remove `memorious_extended/` directory
- [ ] Update tests
