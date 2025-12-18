"""Jinja2 templating utilities for URL and string generation.

This module provides functions for rendering Jinja2 templates with data,
useful for dynamic URL construction in crawlers.
"""

from __future__ import annotations

from typing import Any

from jinja2 import BaseLoader, Environment


def render_template(template: str, data: dict[str, Any]) -> str:
    """Render a Jinja2 template string with data.

    Args:
        template: Jinja2 template string.
        data: Dictionary of values to substitute.

    Returns:
        The rendered string.

    Example:
        >>> render_template("https://example.com/page/{{ page }}", {"page": 1})
        'https://example.com/page/1'
    """
    env = Environment(loader=BaseLoader())
    return env.from_string(template).render(**data)
