"""Type casting utilities for scraped data.

This module provides functions for automatically casting scraped string
values to appropriate Python types (int, float, date, datetime).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from dateparser import parse as dateparse2
from dateutil.parser import parse as dateparse


def ensure_date(
    value: str | date | datetime | None,
    raise_on_error: bool = False,
    **parserkwargs: Any,
) -> date | None:
    """Parse a value into a date object.

    Tries multiple parsing strategies: datetime.date, dateutil.parse,
    and dateparser.parse.

    Args:
        value: The value to parse (string, date, datetime, or None).
        raise_on_error: If True, raise exception on parse failure.
        **parserkwargs: Additional arguments passed to date parsers.

    Returns:
        A date object, or None if parsing fails and raise_on_error is False.

    Raises:
        Exception: If parsing fails and raise_on_error is True.

    Example:
        >>> ensure_date("2024-01-15")
        datetime.date(2024, 1, 15)
        >>> ensure_date("January 15, 2024")
        datetime.date(2024, 1, 15)
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    value_str = str(value)
    try:
        return dateparse(value_str, **parserkwargs).date()
    except Exception:
        try:
            parsed = dateparse2(value_str, **parserkwargs)
            return parsed.date() if parsed else None
        except Exception as e:
            if raise_on_error:
                raise e
            return None


def cast_value(
    value: Any,
    with_date: bool = False,
    **datekwargs: Any,
) -> int | float | date | datetime | Any:
    """Cast a value to its appropriate type.

    Attempts to convert strings to int, float, or date as appropriate.

    Args:
        value: The value to cast.
        with_date: If True, attempt to parse strings as dates.
        **datekwargs: Additional arguments for date parsing.

    Returns:
        The cast value (int, float, date, datetime, or original type).

    Example:
        >>> cast_value("42")
        42
        >>> cast_value("3.14")
        3.14
        >>> cast_value("2024-01-15", with_date=True)
        datetime.date(2024, 1, 15)
    """
    if not isinstance(value, (str, float, int)):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        f = float(value)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        pass
    if with_date:
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            result = ensure_date(str(value), **datekwargs)
            return result if result else value
    return value


def cast_dict(
    data: dict[str, Any],
    ignore_keys: list[str] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Cast all values in a dictionary to appropriate types.

    Args:
        data: Dictionary to process.
        ignore_keys: Keys to skip during casting.
        **kwargs: Additional arguments for date parsing.

    Returns:
        New dictionary with cast values.

    Example:
        >>> cast_dict({"count": "42", "date": "2024-01-15"})
        {'count': 42, 'date': datetime.date(2024, 1, 15)}
    """
    ignore = ignore_keys or []
    return {
        k: cast_value(v, with_date=True, **kwargs) if k not in ignore else v
        for k, v in data.items()
    }
