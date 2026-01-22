"""Jinja2 templating utilities for URL and string generation.

This module provides functions for rendering Jinja2 templates with data,
useful for dynamic URL construction in crawlers.
"""

from __future__ import annotations

from typing import Any

from jinja2 import BaseLoader, Environment, StrictUndefined


def render_template(template: str, data: dict[str, Any]) -> str:
    """Render a Jinja2 template string with data.

    Uses StrictUndefined mode, which raises an error if a template
    variable is missing from the data dict.

    Args:
        template: Jinja2 template string.
        data: Dictionary of values to substitute.

    Returns:
        The rendered string.

    Raises:
        jinja2.UndefinedError: If a template variable is not found in data.

    Example:
        >>> render_template("https://example.com/page/{{ page }}", {"page": 1})
        'https://example.com/page/1'
        >>> render_template("{{ missing }}", {})
        Traceback (most recent call last):
            ...
        jinja2.exceptions.UndefinedError: 'missing' is undefined
    """
    env = Environment(loader=BaseLoader(), undefined=StrictUndefined)
    return env.from_string(template).render(**data)
