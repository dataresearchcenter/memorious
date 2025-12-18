"""Regex extraction utilities for data parsing.

This module provides helper functions for extracting data from strings
using regular expressions.
"""

from __future__ import annotations

import re

from memorious.exc import RegexError


def regex_first(pattern: str, string: str) -> str:
    """Extract the first regex match from a string.

    Args:
        pattern: Regular expression pattern.
        string: String to search.

    Returns:
        The first match, stripped of whitespace.

    Raises:
        RegexError: If no match is found.

    Example:
        >>> regex_first(r"\\d+", "Page 42 of 100")
        '42'
    """
    matches = re.findall(pattern, string)
    if matches:
        return str(matches[0]).strip()
    raise RegexError(f"No match for pattern: {pattern}", string)
