"""Crawler configuration as pydantic model."""

import re
from typing import Any

from ftmq.model import Dataset
from pydantic import BaseModel, Field, field_validator

from memorious.model.stage import StageConfig


class AggregatorConfig(BaseModel):
    """Configuration for crawler aggregator."""

    method: str = Field(..., description="Method name or module:function path")
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}


class CrawlerConfig(Dataset):
    """
    Crawler configuration model.

    Inherits from ftmq.model.Dataset for FTM ecosystem integration.
    Loaded from YAML files and validated with pydantic.
    """

    # Override title to accept 'description' alias from YAML for backwards compat
    title: str = Field(..., validation_alias="description")

    init: str = Field(default="init", description="Initial stage name")
    delay: int = Field(
        default=0, ge=0, description="Delay between operations in seconds"
    )
    expire: int = Field(
        default=1, ge=0, description="Days until incremental crawl expires"
    )
    max_runtime: int = Field(
        default=0, ge=0, description="Max runtime in seconds (0 = unlimited)"
    )
    stealthy: bool = Field(default=False, description="Use random user agents")

    # Pipeline definition - stage name -> stage config
    pipeline: dict[str, StageConfig] = Field(default_factory=dict)

    # Optional aggregator
    aggregator: AggregatorConfig | None = Field(default=None)

    model_config = {"extra": "ignore", "populate_by_name": True}

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[A-Za-z0-9_-]+$", v):
            raise ValueError(
                f"Invalid crawler name: {v}. Allowed characters: A-Za-z0-9_-"
            )
        return v

    @property
    def init_stage(self) -> str:
        """Alias for init to maintain backwards compatibility."""
        return self.init

    @property
    def expire_seconds(self) -> int:
        """Expire time in seconds."""
        return self.expire * 86400

    def get_stage(self, name: str) -> StageConfig | None:
        """Get stage config by name."""
        return self.pipeline.get(name)
