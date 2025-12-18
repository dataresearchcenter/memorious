"""Pagination utilities for web crawlers.

This module provides helper functions for handling pagination in crawlers,
including URL manipulation and next-page detection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from banal import ensure_dict
from furl import furl

from memorious.helpers.regex import regex_first
from memorious.helpers.xpath import extract_xpath

if TYPE_CHECKING:
    from lxml.html import HtmlElement

    from memorious.logic.context import Context


def get_paginated_url(url: str, page: int, param: str = "page") -> str:
    """Apply page number to URL query parameter.

    Args:
        url: The base URL.
        page: Page number to set.
        param: Query parameter name for the page number.

    Returns:
        URL with the page parameter set.

    Example:
        >>> get_paginated_url("https://example.com/search", 2)
        'https://example.com/search?page=2'
        >>> get_paginated_url("https://example.com/search?q=test", 3, "p")
        'https://example.com/search?q=test&p=3'
    """
    f = furl(url)
    f.args[param] = page
    return f.url


def _get_int(html: HtmlElement, value: int | str) -> int:
    """Get integer value from direct value or XPath extraction."""
    if isinstance(value, int):
        return value
    extracted = extract_xpath(html, value)
    return int(regex_first(r"\d+", str(extracted)))


def calculate_next_page(
    html: HtmlElement, current: int, config: dict[str, Any]
) -> int | None:
    """Determine next page number from pagination config.

    Args:
        html: HTML element containing pagination info.
        current: Current page number.
        config: Pagination configuration with total/per_page or total_pages.

    Returns:
        Next page number, or None if no more pages.
    """
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


def paginate(context: Context, data: dict[str, Any], html: HtmlElement) -> None:
    """Emit next page if pagination indicates more pages.

    Examines pagination configuration and HTML content to determine
    if there are more pages, and emits the next page data.

    Args:
        context: The crawler context with pagination params.
        data: Current data dict (used to get current page).
        html: HTML element containing pagination info.

    Example YAML configuration::

        pipeline:
          parse:
            method: parse
            params:
              pagination:
                total: './/span[@class="total"]/text()'
                per_page: 20
                param: page
            handle:
              next_page: fetch
              store: store
    """
    config = context.params.get("pagination")
    if not config:
        return

    config = ensure_dict(config)
    current = data.get("page", 1)
    next_page = calculate_next_page(html, current, config)

    if next_page:
        context.log.info("Next page", page=next_page)
        next_data = {**data, "page": next_page}
        param = config.get("param", "page")
        if "url" in next_data:
            next_data["url"] = get_paginated_url(next_data["url"], next_page, param)
        context.emit(rule="next_page", data=next_data)
