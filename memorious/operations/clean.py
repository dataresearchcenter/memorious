"""Data cleaning and validation operations.

This module provides operations for cleaning, transforming, and
validating scraped data before storage or further processing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from banal import ensure_dict, ensure_list, is_mapping
from lxml import html

from memorious.exc import MetaDataError
from memorious.helpers.casting import cast_dict
from memorious.helpers.template import render_template
from memorious.operations import register

if TYPE_CHECKING:
    from memorious.logic.context import Context


@register("clean_html")
def clean_html(context: Context, data: dict[str, Any]) -> None:
    """Clean HTML by removing specified elements.

    Removes HTML elements matching the given XPath expressions and
    stores the cleaned HTML.

    Args:
        context: The crawler context.
        data: Must contain cached HTTP response data.

    Params:
        remove_paths (optional): List of XPath expressions for elements to remove.

    Example:
        ```yaml
        pipeline:
          clean:
            method: clean_html
            params:
              remove_paths:
                - './/script'
                - './/style'
                - './/nav'
                - './/footer'
            handle:
              pass: parse
        ```
    """
    with context.http.rehash(data) as result:
        if not result.ok or result.html is None:
            context.emit(data=data)
            return
        doc = result.html
        for path in ensure_list(context.params.get("remove_paths")):
            for el in doc.xpath(path):
                el.drop_tree()
        content_hash = context.store_data(html.tostring(doc, pretty_print=True))
        data["content_hash"] = content_hash
        context.emit(data=data)


@register("clean")
def clean(context: Context, data: dict[str, Any]) -> None:
    """Clean and validate metadata in the data dict.

    Performs various data transformations including dropping keys,
    setting defaults, rewriting values, validating required fields,
    and type casting.

    Args:
        context: The crawler context.
        data: Data dict to clean (modified in place).

    Params:
        drop (optional): List of keys to remove from data.
        defaults (optional): Dict of default values for missing keys.
        values (optional): Dict for value rewriting (mapping or format string).
        required (optional): List of required keys (raises MetaDataError if missing).
        typing (optional): Type casting configuration with ignore list and date kwargs.

    Example:
        ```yaml
        pipeline:
          clean:
            method: clean
            params:
              drop:
                - page
                - formdata
                - session_id
              defaults:
                source: "web"
                language: "en"
              values:
                foreign_id: "{publisher[id]}-{reference}"
                status:
                  draft: unpublished
                  live: published
              required:
                - title
                - url
                - published_at
              typing:
                ignore:
                  - reference
                  - phone_number
                dateparserkwargs:
                  dayfirst: true
            handle:
              pass: store
        ```
    """
    # Drop keys
    for key in ensure_list(context.params.get("drop")):
        data.pop(key, None)

    # Set defaults
    for key, value in ensure_dict(context.params.get("defaults")).items():
        if key not in data:
            data[key] = value

    # Rewrite values
    for key, values in ensure_dict(context.params.get("values")).items():
        if is_mapping(values) and data.get(key) in values:
            data[key] = values[data[key]]
        elif isinstance(values, str):
            data[key] = render_template(values, data)

    # Validate required
    for key in ensure_list(context.params.get("required")):
        if key not in data:
            context.emit_warning(MetaDataError(f"`{key}` required but missing"))

    # Type casting
    typing_config = ensure_dict(context.params.get("typing"))
    if typing_config:
        ignore_keys = ensure_list(typing_config.get("ignore"))
        datekwargs = ensure_dict(typing_config.get("dateparserkwargs"))
        data.update(cast_dict(data, ignore_keys, **datekwargs))

    context.emit(data=data)
