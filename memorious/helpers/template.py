"""Jinja2 templating utilities for URL and string generation.

This module provides functions for rendering Jinja2 templates with data,
useful for dynamic URL construction in crawlers.
"""

from __future__ import annotations

from typing import Any

from jinja2 import BaseLoader, ChainableUndefined, Environment, UndefinedError


class StrictChainableUndefined(ChainableUndefined):
    """Undefined that allows filters (like `default`) but raises on render.

    This combines the behavior of:
    - ChainableUndefined: allows `{{ foo | default("bar") }}` to work
    - StrictUndefined: raises error if undefined value is rendered directly

    Examples:
        >>> env = Environment(undefined=StrictChainableUndefined)
        >>> env.from_string("{{ foo | default('bar') }}").render()
        'bar'
        >>> env.from_string("{{ foo }}").render()
        Traceback (most recent call last):
            ...
        jinja2.exceptions.UndefinedError: 'foo' is undefined
    """

    def __str__(self) -> str:
        raise UndefinedError(f"'{self._undefined_name}' is undefined")

    def __iter__(self) -> Any:
        raise UndefinedError(f"'{self._undefined_name}' is undefined")

    def __bool__(self) -> bool:
        raise UndefinedError(f"'{self._undefined_name}' is undefined")


def render_template(template: str, data: dict[str, Any]) -> str:
    """Render a Jinja2 template string with data.

    Uses StrictChainableUndefined mode, which raises an error if a template
    variable is missing from the data dict, but allows the `default` filter
    to provide fallback values.

    Args:
        template: Jinja2 template string.
        data: Dictionary of values to substitute.

    Returns:
        The rendered string.

    Raises:
        jinja2.UndefinedError: If a template variable is not found in data
            and no default is provided.

    Example:
        >>> render_template("https://example.com/page/{{ page }}", {"page": 1})
        'https://example.com/page/1'
        >>> render_template("{{ foo | default('bar') }}", {})
        'bar'
        >>> render_template("{{ missing }}", {})
        Traceback (most recent call last):
            ...
        jinja2.exceptions.UndefinedError: 'missing' is undefined
    """
    env = Environment(loader=BaseLoader(), undefined=StrictChainableUndefined)
    return env.from_string(template).render(**data)
