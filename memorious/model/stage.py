"""Stage configuration as pydantic model."""

import re
from importlib import import_module
from typing import Any

from pydantic import BaseModel, Field
from servicelayer.extensions import get_entry_point


class StageConfig(BaseModel):
    """Configuration for a single pipeline stage."""

    method: str = Field(..., description="Method name or module:function path")
    params: dict[str, Any] = Field(default_factory=dict)
    handle: dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}

    @property
    def handlers(self) -> dict[str, str]:
        """Alias for handle to maintain backwards compatibility."""
        return self.handle


class CrawlerStage:
    """A single step in a data processing crawler.

    Wraps StageConfig with runtime state (crawler reference, resolved method).
    """

    def __init__(self, crawler, name: str, config: dict[str, Any] | StageConfig):
        self.crawler = crawler
        self.name = name
        self._validate_name()

        # Accept either dict or StageConfig
        if isinstance(config, dict):
            self.config = StageConfig(**config)
        else:
            self.config = config

    def _validate_name(self) -> None:
        if not re.match(r"^[A-Za-z0-9_-]+$", self.name):
            raise ValueError(
                f"Invalid stage name: {self.name}. Allowed characters: A-Za-z0-9_-"
            )

    @property
    def method_name(self) -> str:
        return self.config.method

    @property
    def params(self) -> dict[str, Any]:
        return self.config.params

    @property
    def handlers(self) -> dict[str, str]:
        return self.config.handle

    @property
    def method(self):
        """Resolve and return the method callable."""
        # method A: via a named Python entry point
        func = get_entry_point("memorious.operations", self.method_name)
        if func is not None:
            return func
        # method B: direct import from a module
        if ":" not in self.method_name:
            raise ValueError(f"Unknown method: {self.method_name}")
        package, method = self.method_name.rsplit(":", 1)
        module = import_module(package)
        return getattr(module, method)

    @property
    def op_count(self):
        """Total operations performed for this stage."""
        from memorious.model import Crawl

        return Crawl.op_count(self.crawler, self)

    @property
    def namespaced_name(self) -> str:
        return f"{self.crawler}.{self.name}"

    @classmethod
    def detach_namespace(cls, namespaced_name: str) -> str:
        return namespaced_name.split(".")[-1]

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<CrawlerStage({self.crawler!r}, {self.name})>"
