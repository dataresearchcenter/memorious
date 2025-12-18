"""Debugging operations for crawler development.

This module provides operations useful during crawler development
and debugging, including data inspection and interactive debugging.
"""

from __future__ import annotations

from pprint import pformat
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from memorious.logic.context import Context


def inspect(context: Context, data: dict[str, Any]) -> None:
    """Log the current data dict for inspection.

    Prints the data dictionary in a formatted way for debugging.
    Passes data through to the next stage unchanged.

    Args:
        context: The crawler context.
        data: Data to inspect.

    Example:
        ```yaml
        pipeline:
          debug:
            method: inspect
            handle:
              pass: store
        ```
    """
    context.log.info("Inspect data", data=pformat(data))
    context.emit(data=data, optional=True)


def ipdb(context: Context, data: dict[str, Any]) -> None:
    """Drop into an interactive ipdb debugger session.

    Pauses execution and opens an interactive Python debugger,
    allowing inspection of the context and data at runtime.

    Args:
        context: The crawler context (available as `context` and `cn`).
        data: Current stage data (available as `data`).

    Note:
        Requires ipdb to be installed (`pip install ipdb`).
        Only useful during local development, not in production.

    Example:
        ```yaml
        pipeline:
          debug:
            method: ipdb
            handle:
              pass: store
        ```
    """
    cn = context  # noqa: F841 - available in debugger
    import ipdb

    ipdb.set_trace()
