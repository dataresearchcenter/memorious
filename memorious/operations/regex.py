"""Regex extraction operations for data parsing.

This module provides operations for extracting structured data from
string values using regular expressions with named capture groups.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from banal import clean_dict, ensure_dict, ensure_list, is_mapping

from memorious.operations import register

if TYPE_CHECKING:
    from memorious.logic.context import Context


def _extract_regex_groups(
    key: str,
    value: Any,
    patterns: list[str],
    log_fn: Any,
) -> dict[str, Any]:
    """Extract named groups from value using regex patterns."""
    if is_mapping(value):
        value = value.get(key)
    if value is None:
        log_fn(f"No data found in `{key}`")
        return {}
    for pattern in patterns:
        compiled = re.compile(pattern)
        match = re.match(compiled, str(value))
        if match is not None:
            return {k: v.strip() for k, v in clean_dict(match.groupdict()).items()}
        log_fn("Can't extract data for `%s`: [%s] %s" % (key, pattern, value))
    return {}


@register("regex_groups")
def regex_groups(context: Context, data: dict[str, Any]) -> None:
    """Extract named regex groups from data values.

    Uses regex named capture groups to extract structured data from
    string values. Supports both simple single-pattern extraction and
    advanced multi-pattern extraction with splitting.

    Args:
        context: The crawler context.
        data: Data dict to extract from (modified in place).

    Params:
        <key>: Regex pattern with named groups, or config dict.
        Config dict supports:
            pattern/patterns: Single pattern or list of patterns.
            store_as: Key name for storing the result.
            split: Separator to split value before matching.

    Example:
        ```yaml
        pipeline:
          extract:
            method: regex_groups
            params:
              # Simple extraction: source key -> named groups added to data
              full_name: '(?P<first_name>\\w+)\\s(?P<last_name>\\w+)'

              # From "John Doe" extracts: first_name="John", last_name="Doe"

              # Advanced extraction with splitting
              originators_raw:
                store_as: originators
                split: ","
                patterns:
                  - '(?P<name>.*),\\s*(?P<party>\\w+)'
                  - '(?P<name>.*)'

              # From "John Doe, SPD, Jane Smith" extracts:
              # originators = [
              #   {name: "John Doe", party: "SPD"},
              #   {name: "Jane Smith"}
              # ]

              # Metadata extraction
              meta_raw: >-
                .*Drucksache\\s+(?P<reference>\\d+/\\d+)
                .*vom\\s+(?P<published_at>\\d{2}\\.\\d{2}\\.\\d{4}).*
            handle:
              pass: clean
        ```
    """
    for key, patterns in ensure_dict(context.params).items():
        log_fn = context.log.warning

        if is_mapping(patterns):
            # Advanced extraction configuration
            config = dict(patterns)

            if key not in data:
                continue

            pattern_list = ensure_list(
                config.get("pattern", config.get("patterns", []))
            )
            store_key = config.get("store_as", key)
            separator = config.get("split")

            if separator:
                # Split value and extract from each part
                values = str(data[key]).split(separator)
                result = [
                    _extract_regex_groups(key, v.strip(), pattern_list, log_fn)
                    for v in values
                ]
                # Filter out empty results
                result = [r for r in result if r]
            else:
                # Single extraction
                result = _extract_regex_groups(key, data, pattern_list, log_fn)

            data[store_key] = result

        else:
            # Simple extraction: pattern(s) directly as value
            data.update(_extract_regex_groups(key, data, ensure_list(patterns), log_fn))

    context.emit(data=data)
