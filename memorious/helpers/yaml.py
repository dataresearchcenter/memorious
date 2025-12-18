"""YAML loader with !include constructor support.

This module provides a custom YAML loader that supports including external
files using the `!include` directive.

Example:
    ```yaml
    # main.yml
    settings:
      database: !include database.yml

    # database.yml
    host: localhost
    port: 5432
    ```
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import IO, Any

import yaml


class IncludeLoader(yaml.SafeLoader):
    """YAML Loader with !include constructor for file inclusion."""

    def __init__(self, stream: IO) -> None:
        """Initialize the loader with the root directory from the stream."""
        try:
            self._root = Path(stream.name).parent
        except AttributeError:
            self._root = Path.cwd()
        super().__init__(stream)


def _construct_include(loader: IncludeLoader, node: yaml.Node) -> Any:
    """Include file referenced at node.

    Args:
        loader: The YAML loader instance.
        node: The YAML node containing the file path.

    Returns:
        The parsed content of the included file.
    """
    filename = (loader._root / loader.construct_scalar(node)).resolve()
    ext = filename.suffix.lstrip(".")

    with open(filename, encoding="utf-8") as f:
        if ext in ("yaml", "yml"):
            return yaml.load(f, IncludeLoader)
        elif ext == "json":
            return json.load(f)
        return f.read()


yaml.add_constructor("!include", _construct_include, IncludeLoader)


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load YAML file with !include support.

    Args:
        path: Path to the YAML file.

    Returns:
        Parsed YAML content as a dictionary.

    Example:
        >>> config = load_yaml("crawler.yml")
    """
    with open(path, encoding="utf-8") as fh:
        return yaml.load(fh, IncludeLoader)
