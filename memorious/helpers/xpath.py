"""XPath extraction utilities for HTML/XML parsing.

This module provides helper functions for extracting values from
HTML and XML documents using XPath expressions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lxml.html import HtmlElement


def extract_xpath(html: HtmlElement, path: str) -> Any:
    """Extract value from HTML/XML element using XPath.

    Handles common cases like single-element lists and text extraction.

    Args:
        html: The lxml HTML/XML element to query.
        path: XPath expression to evaluate.

    Returns:
        The extracted value. If the result is a single-element list,
        returns just that element. If the element has a text attribute,
        returns the stripped text.

    Example:
        >>> extract_xpath(html, './/title/text()')
        'Page Title'
        >>> extract_xpath(html, './/a/@href')
        'https://example.com'
    """
    result = html.xpath(path)
    if isinstance(result, list) and len(result) == 1:
        result = result[0]
    if hasattr(result, "text"):
        result = result.text
    if isinstance(result, str):
        return result.strip()
    return result
