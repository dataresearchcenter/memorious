"""HTML form extraction utilities.

This module provides helper functions for extracting form data from
HTML documents, useful for form submission in crawlers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lxml.html import HtmlElement


def extract_form(html: HtmlElement, xpath: str) -> tuple[str | None, dict[str, Any]]:
    """Extract form action URL and field values from an HTML form.

    Args:
        html: HTML element containing the form.
        xpath: XPath expression to locate the form element.

    Returns:
        Tuple of (action_url, form_data_dict). Returns (None, {}) if
        the form is not found.

    Example:
        >>> action, data = extract_form(html, './/form[@id="login"]')
        >>> action
        '/login'
        >>> data
        {'username': '', 'password': '', 'csrf_token': 'abc123'}
    """
    form = html.find(xpath)
    if form is None:
        return None, {}

    action = form.xpath("@action")
    action_url = action[0] if action else None

    data: dict[str, Any] = {}
    for el in form.findall(".//input"):
        if el.name:
            data[el.name] = el.value
    for el in form.findall(".//select"):
        if el.name:
            data[el.name] = el.value

    return action_url, data
